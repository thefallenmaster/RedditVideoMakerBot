import json
import re
from os.path import exists

from playwright.sync_api import sync_playwright

from utils import settings
from utils.ai_methods import sort_by_similarity
from utils.console import print_step, print_substep
from utils.playwright import ensure_reddit_session
from utils.posttextparser import posttextparser
from utils.subreddit import _contains_blocked_words
from utils.voice import sanitize_text
from reddit.local_generator import get_local_thread


def _fetch_json_in_context(page, path: str):
    """Fetches a Reddit JSON endpoint using the active authenticated browser page."""
    url = f"https://www.reddit.com{path}"
    result = page.evaluate(
        """async (targetUrl) => {
            const resp = await fetch(targetUrl, {
                credentials: "include",
                headers: { "Accept": "application/json" }
            });
            const text = await resp.text();
            return {
                status: resp.status,
                url: resp.url,
                contentType: resp.headers.get("content-type") || "",
                text: text
            };
        }""",
        url,
    )

    if "/login" in (result.get("url") or ""):
        raise RuntimeError(
            f"Reddit redirected {url} to a login page. Please re-run and sign in manually."
        )
    if result.get("status") != 200:
        raise RuntimeError(f"Reddit returned HTTP {result.get('status')} for {url}")
    if "json" not in (result.get("contentType") or "").lower():
        raise RuntimeError(
            f"Reddit returned non-JSON response ({result.get('contentType')}) for {url}. "
            "If verification is required, complete it in the browser window."
        )
    return json.loads(result["text"])


def _load_done_ids() -> set:
    if not exists("./video_creation/data/videos.json"):
        with open("./video_creation/data/videos.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return set()
    with open("./video_creation/data/videos.json", "r", encoding="utf-8") as f:
        try:
            return {video.get("id") for video in json.load(f) if isinstance(video, dict)}
        except json.JSONDecodeError:
            return set()


def _select_post(posts: list, done_ids: set):
    storymode = bool(settings.config["settings"]["storymode"])
    allow_nsfw = bool(settings.config["settings"]["allow_nsfw"])
    min_comments = int(settings.config["reddit"]["thread"]["min_comments"] or 0)
    storymode_max_length = int(settings.config["settings"]["storymode_max_length"] or 2000)

    for post in posts:
        if post.get("id") in done_ids:
            continue
        if post.get("over_18") and not allow_nsfw:
            print_substep("NSFW Post Detected. Skipping...")
            continue
        if post.get("stickied"):
            print_substep("This post was pinned by moderators. Skipping...")
            continue
        title = post.get("title", "")
        selftext = post.get("selftext", "") or ""
        if _contains_blocked_words(f"{title} {selftext}"):
            print_substep("Post contains a blocked word. Skipping...")
            continue
        if post.get("num_comments", 0) <= min_comments and not storymode:
            print_substep(
                f"This post has under the specified minimum of comments ({min_comments}). Skipping..."
            )
            continue
        if storymode:
            if not post.get("is_self", True) or not selftext:
                print_substep("You are trying to use story mode on post with no post text")
                continue
            if len(selftext) > storymode_max_length:
                print_substep(
                    f"Post is too long ({len(selftext)}), try with a different post. ({storymode_max_length} character limit)"
                )
                continue
            if len(selftext) < 30:
                continue
        return post
    return None


def get_subreddit_threads(POST_ID: str = None):
    """Fetches a thread and comments locally or via authenticated browser session."""
    if settings.config["reddit"]["thread"].get("use_local_stories", True):
        return get_local_thread(POST_ID)

    print_step("Getting subreddit threads...")
    subreddit = settings.config["reddit"]["thread"]["subreddit"] or "AskReddit"
    subreddit = re.sub(r"^r/", "", str(subreddit).strip(), flags=re.IGNORECASE) or "AskReddit"
    print_substep(f"Using subreddit: r/{subreddit}")

    if not POST_ID:
        cfg_post_id = str(settings.config["reddit"]["thread"].get("post_id") or "").strip()
        if cfg_post_id and len(cfg_post_id.split("+")) == 1:
            POST_ID = cfg_post_id

    def _load_thread_with_session(force_visible: bool):
        with sync_playwright() as p:
            context, page = ensure_reddit_session(
                p,
                target_url=f"https://www.reddit.com/r/{subreddit}/",
                force_visible=force_visible,
            )
            try:
                if POST_ID:
                    data = _fetch_json_in_context(page, f"/comments/{POST_ID}.json?raw_json=1")
                    return data[0]["data"]["children"][0]["data"], data[1]["data"]["children"]

                listing = _fetch_json_in_context(
                    page, f"/r/{subreddit}/hot.json?limit=25&raw_json=1"
                )
                posts = [
                    child["data"]
                    for child in listing.get("data", {}).get("children", [])
                    if child.get("kind") == "t3"
                ]
                if settings.config["ai"].get("ai_similarity_enabled"):
                    keywords_raw = settings.config["ai"].get("ai_similarity_keywords") or ""
                    keywords = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]
                    if keywords:
                        print(
                            f"Sorting threads by similarity to the given keywords: {', '.join(keywords)}"
                        )

                        class _PostObj:
                            def __init__(self, d):
                                self.data = d
                                self.title = d.get("title", "")
                                self.selftext = d.get("selftext", "") or ""

                        wrapped, _ = sort_by_similarity([_PostObj(p) for p in posts], keywords)
                        posts = [w.data for w in wrapped]

                done_ids = _load_done_ids()
                selected = _select_post(posts, done_ids)
                if selected is None:
                    raise RuntimeError(f"No eligible posts found in r/{subreddit}.")

                thread_json = _fetch_json_in_context(
                    page, f"{selected['permalink'].rstrip('/')}.json?raw_json=1"
                )
                return thread_json[0]["data"]["children"][0]["data"], thread_json[1]["data"]["children"]
            finally:
                context.close()

    try:
        post, comments_data = _load_thread_with_session(force_visible=False)
    except RuntimeError as err:
        if "No eligible posts found" in str(err):
            raise
        # If headless profile was still gated by Reddit, retry in a visible browser window once
        post, comments_data = _load_thread_with_session(force_visible=True)

    thread_url = f"https://www.reddit.com{post['permalink']}"
    upvotes = post.get("score", 0)
    ratio = round(float(post.get("upvote_ratio", 0)) * 100, 1)
    num_comments = post.get("num_comments", 0)

    print_substep(f"Video will be: {post['title']} :thumbsup:", style="bold green")
    print_substep(f"Thread url is: {thread_url} :thumbsup:", style="bold green")
    print_substep(f"Thread has {upvotes} upvotes", style="bold blue")
    print_substep(f"Thread has a upvote ratio of {ratio}%", style="bold blue")
    print_substep(f"Thread has {num_comments} comments", style="bold blue")

    content = {
        "thread_url": thread_url,
        "thread_title": post["title"],
        "thread_id": post["id"],
        "is_nsfw": bool(post.get("over_18", False)),
        "comments": [],
    }

    if settings.config["settings"]["storymode"]:
        selftext = post.get("selftext", "") or ""
        if settings.config["settings"]["storymodemethod"] == 1:
            content["thread_post"] = posttextparser(selftext)
        else:
            content["thread_post"] = selftext
    else:
        max_len = int(settings.config["reddit"]["thread"]["max_comment_length"])
        min_len = int(settings.config["reddit"]["thread"]["min_comment_length"])
        for c in comments_data:
            if c.get("kind") != "t1":
                continue
            cdata = c.get("data", {})
            body = cdata.get("body")
            if not body or body in ("[removed]", "[deleted]"):
                continue
            if cdata.get("stickied"):
                continue
            if cdata.get("author") in (None, "[deleted]"):
                continue
            if _contains_blocked_words(body):
                continue
            sanitised = sanitize_text(body)
            if not sanitised or sanitised == " ":
                continue
            if min_len <= len(body) <= max_len:
                content["comments"].append(
                    {
                        "comment_body": body,
                        "comment_url": cdata["permalink"],
                        "comment_id": cdata["id"],
                    }
                )

    print_substep("Received subreddit threads Successfully.", style="bold green")
    return content
