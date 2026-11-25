import json
import os
import re
from pathlib import Path
from typing import Dict, Final

import translators
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import ViewportSize, sync_playwright
from rich.progress import track

from utils import settings
from utils.console import print_step, print_substep
from utils.imagenarator import imagemaker
from utils.playwright import clear_cookie_by_name, ensure_reddit_session, is_reddit_gated
from utils.videos import save_data

__all__ = ["get_screenshots_of_reddit_posts"]

_AVATAR_COLORS = [
    (255, 69, 0),
    (0, 121, 211),
    (70, 209, 96),
    (219, 0, 100),
    (126, 83, 193),
    (255, 165, 0),
    (0, 166, 165),
]


def _format_score(score: int) -> str:
    if score >= 1000:
        return f"{score / 1000:.1f}k".replace(".0k", "k")
    return str(score)


def _wrap_text_px(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _render_card_image(
    author: str,
    age: str,
    body: str,
    score: int,
    is_op: bool,
    dark_mode: bool,
    out_path: str,
) -> None:
    card_w = 900
    pad = 36
    inner_w = card_w - pad * 2

    bold_font = ImageFont.truetype(os.path.join("fonts", "Roboto-Bold.ttf"), 24)
    badge_font = ImageFont.truetype(os.path.join("fonts", "Roboto-Bold.ttf"), 17)
    meta_font = ImageFont.truetype(os.path.join("fonts", "Roboto-Regular.ttf"), 21)
    body_font = ImageFont.truetype(os.path.join("fonts", "Roboto-Regular.ttf"), 28)
    footer_font = ImageFont.truetype(os.path.join("fonts", "Roboto-Bold.ttf"), 21)

    if dark_mode:
        card_bg = (26, 26, 27, 255)
        border_col = (52, 53, 54, 255)
        body_col = (215, 218, 220)
        muted_col = (129, 131, 132)
        author_col = (235, 237, 239)
    else:
        card_bg = (255, 255, 255, 255)
        border_col = (218, 224, 230, 255)
        body_col = (26, 26, 27)
        muted_col = (120, 124, 126)
        author_col = (26, 26, 27)

    measure_img = Image.new("RGBA", (card_w, 200))
    measure_draw = ImageDraw.Draw(measure_img)
    lines = _wrap_text_px(measure_draw, body, body_font, inner_w)
    line_h = 38
    header_h = 46
    footer_h = 34
    body_h = max(1, len(lines)) * line_h
    card_h = pad + header_h + 14 + body_h + 20 + footer_h + pad

    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [(0, 0), (card_w - 1, card_h - 1)],
        radius=18,
        fill=card_bg,
        outline=border_col,
        width=2,
    )

    # Avatar circle
    avatar_size = 40
    avatar_color = _AVATAR_COLORS[sum(ord(ch) for ch in author) % len(_AVATAR_COLORS)]
    draw.ellipse([(pad, pad), (pad + avatar_size, pad + avatar_size)], fill=avatar_color)
    initial = (author[:1] or "R").upper()
    init_bbox = draw.textbbox((0, 0), initial, font=bold_font)
    iw = init_bbox[2] - init_bbox[0]
    ih = init_bbox[3] - init_bbox[1]
    draw.text(
        (pad + (avatar_size - iw) / 2, pad + (avatar_size - ih) / 2 - 2),
        initial,
        font=bold_font,
        fill=(255, 255, 255),
    )

    # Author + optional OP badge + timestamp
    cursor_x = pad + avatar_size + 14
    header_y = pad + 7
    author_text = f"u/{author}"
    draw.text((cursor_x, header_y), author_text, font=bold_font, fill=author_col)
    cursor_x += int(draw.textlength(author_text, font=bold_font)) + 10

    if is_op:
        op_w = int(draw.textlength("OP", font=badge_font)) + 14
        draw.rounded_rectangle(
            [(cursor_x, header_y + 2), (cursor_x + op_w, header_y + 26)],
            radius=6,
            fill=(0, 121, 211),
        )
        draw.text((cursor_x + 7, header_y + 4), "OP", font=badge_font, fill=(255, 255, 255))
        cursor_x += op_w + 10

    draw.text((cursor_x, header_y + 2), f"• {age}", font=meta_font, fill=muted_col)

    # Body text
    y = pad + header_h + 14
    for line in lines:
        draw.text((pad, y), line, font=body_font, fill=body_col)
        y += line_h

    # Footer
    footer_y = y + 16
    score_str = f"▲ {_format_score(score)}"
    draw.text((pad, footer_y), score_str, font=footer_font, fill=(255, 69, 0))
    score_w = int(draw.textlength(score_str, font=footer_font))
    draw.text((pad + score_w + 22, footer_y), "▼   Reply   Share", font=meta_font, fill=muted_col)

    img.save(out_path)


def _render_local_cards(
    reddit_object: dict,
    reddit_id: str,
    screenshot_num: int,
    dark_mode: bool,
    storymode: bool,
    lang: str,
) -> None:
    print_substep("Rendering local Reddit-style cards with Pillow...")
    if storymode:
        body = reddit_object.get("thread_post", "")
        if isinstance(body, list):
            body = " ".join(body)
        if lang and body:
            body = translators.translate_text(body, translator="google", to_language=lang)
        _render_card_image(
            author=reddit_object.get("thread_author", "anonymous_poster"),
            age="OP • 6h ago",
            body=body,
            score=int(reddit_object.get("thread_upvotes", 2400)),
            is_op=True,
            dark_mode=dark_mode,
            out_path=f"assets/temp/{reddit_id}/png/story_content.png",
        )
    else:
        for idx, comment in enumerate(
            track(reddit_object["comments"][:screenshot_num], "Rendering comment cards...")
        ):
            body = comment["comment_body"]
            if lang:
                body = translators.translate_text(body, translator="google", to_language=lang)
            _render_card_image(
                author=comment.get("comment_author", "redditor"),
                age=comment.get("comment_age", "4h ago"),
                body=body,
                score=int(comment.get("comment_score", 850)),
                is_op=bool(comment.get("is_op", False)),
                dark_mode=dark_mode,
                out_path=f"assets/temp/{reddit_id}/png/comment_{idx}.png",
            )
    print_substep("Local cards rendered Successfully.", style="bold green")


def get_screenshots_of_reddit_posts(reddit_object: dict, screenshot_num: int):
    """Downloads screenshots of reddit posts as seen on the web. Downloads to assets/temp/png

    Args:
        reddit_object (Dict): Reddit object received from reddit/subreddit.py
        screenshot_num (int): Number of screenshots to download
    """
    # settings values
    W: Final[int] = int(settings.config["settings"]["resolution_w"])
    H: Final[int] = int(settings.config["settings"]["resolution_h"])
    lang: Final[str] = settings.config["reddit"]["thread"]["post_lang"]
    storymode: Final[bool] = settings.config["settings"]["storymode"]

    print_step("Downloading screenshots of reddit posts...")
    reddit_id = re.sub(r"[^\w\s-]", "", reddit_object["thread_id"])
    # ! Make sure the reddit screenshots folder exists
    Path(f"assets/temp/{reddit_id}/png").mkdir(parents=True, exist_ok=True)

    # set the theme and turn off non-essential cookies
    if settings.config["settings"]["theme"] == "dark":
        cookie_file = open("./video_creation/data/cookie-dark-mode.json", encoding="utf-8")
        bgcolor = (33, 33, 36, 255)
        txtcolor = (240, 240, 240)
        transparent = False
    elif settings.config["settings"]["theme"] == "transparent":
        if storymode:
            # Transparent theme
            bgcolor = (0, 0, 0, 0)
            txtcolor = (255, 255, 255)
            transparent = True
            cookie_file = open("./video_creation/data/cookie-dark-mode.json", encoding="utf-8")
        else:
            # Switch to dark theme
            cookie_file = open("./video_creation/data/cookie-dark-mode.json", encoding="utf-8")
            bgcolor = (33, 33, 36, 255)
            txtcolor = (240, 240, 240)
            transparent = False
    else:
        cookie_file = open("./video_creation/data/cookie-light-mode.json", encoding="utf-8")
        bgcolor = (255, 255, 255, 255)
        txtcolor = (0, 0, 0)
        transparent = False

    if storymode and settings.config["settings"]["storymodemethod"] == 1:
        cookie_file.close()
        print_substep("Generating images...")
        return imagemaker(
            theme=bgcolor,
            reddit_obj=reddit_object,
            txtclr=txtcolor,
            transparent=transparent,
        )

    if reddit_object.get("is_local"):
        cookie_file.close()
        return _render_local_cards(
            reddit_object=reddit_object,
            reddit_id=reddit_id,
            screenshot_num=screenshot_num,
            dark_mode=settings.config["settings"]["theme"] != "light",
            storymode=storymode,
            lang=lang,
        )

    screenshot_num: int
    with sync_playwright() as p:
        print_substep("Launching Browser with saved Reddit session...")
        dsf = (W // 600) + 1
        cookies = json.load(cookie_file)
        cookie_file.close()

        context, page = ensure_reddit_session(
            p,
            target_url=reddit_object["thread_url"],
            require_auth=False,
            locale=lang or "en-CA,en;q=0.9",
            color_scheme="dark",
            viewport=ViewportSize(width=W, height=H),
            device_scale_factor=dsf,
        )
        context.add_cookies(cookies)  # load preference cookies
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        if is_reddit_gated(page):
            context.close()
            raise RuntimeError(
                f"Reddit gated the page ({page.url}) with '{page.title()}'. "
                "Complete verification in the opened browser window or use storymode = true with storymodemethod = 1."
            )

        # Handle the redesign optout cookie if present
        if page.locator("#redesign-beta-optin-btn").is_visible():
            clear_cookie_by_name(context, "redesign_optout")
            page.reload()
            page.wait_for_timeout(2000)

        if page.locator(
            "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r.D3IL3FD0RFy_mkKLPwL4 > div > div > button"
        ).is_visible():
            print_substep("Post is NSFW. You are spicy...")
            page.locator(
                "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r.D3IL3FD0RFy_mkKLPwL4 > div > div > button"
            ).click()
            page.wait_for_load_state()

        if page.locator(
            "#SHORTCUT_FOCUSABLE_DIV > div:nth-child(7) > div > div > div > header > div > div._1m0iFpls1wkPZJVo38-LSh > button > i"
        ).is_visible():
            page.locator(
                "#SHORTCUT_FOCUSABLE_DIV > div:nth-child(7) > div > div > div > header > div > div._1m0iFpls1wkPZJVo38-LSh > button > i"
            ).click()

        if lang:
            print_substep("Translating post...")
            texts_in_tl = translators.translate_text(
                reddit_object["thread_title"],
                to_language=lang,
                translator="google",
            )

            page.evaluate(
                """tl_content => {
                    const el = document.querySelector('[data-adclicklocation="title"] > div > div > h1')
                        || document.querySelector('shreddit-post [slot="title"]');
                    if (el) el.textContent = tl_content;
                }""",
                texts_in_tl,
            )
        else:
            print_substep("Skipping translation...")

        post_locator = page.locator('[data-test-id="post-content"]').first
        if not post_locator.is_visible():
            post_locator = page.locator("shreddit-post").first

        postcontentpath = f"assets/temp/{reddit_id}/png/title.png"
        try:
            if settings.config["settings"]["zoom"] != 1:
                zoom = settings.config["settings"]["zoom"]
                page.evaluate("document.body.style.zoom=" + str(zoom))
                location = post_locator.bounding_box()
                for i in location:
                    location[i] = float("{:.2f}".format(location[i] * zoom))
                page.screenshot(clip=location, path=postcontentpath)
            else:
                post_locator.screenshot(path=postcontentpath)
        except Exception as e:
            print_substep("Something went wrong!", style="red")
            resp = input(
                "Something went wrong with making the screenshots! Do you want to skip the post? (y/n) "
            )

            if resp.casefold().startswith("y"):
                save_data("", "", "skipped", reddit_id, "")
                print_substep(
                    "The post is successfully skipped! You can now restart the program and this post will skipped.",
                    "green",
                )

            resp = input("Do you want the error traceback for debugging purposes? (y/n)")
            if not resp.casefold().startswith("y"):
                exit()

            raise e

        if storymode:
            text_locator = page.locator('[data-click-id="text"]').first
            if not text_locator.is_visible():
                text_locator = page.locator('shreddit-post [slot="text-body"]').first
            text_locator.screenshot(path=f"assets/temp/{reddit_id}/png/story_content.png")
        else:
            for idx, comment in enumerate(
                track(
                    reddit_object["comments"][:screenshot_num],
                    "Downloading screenshots...",
                )
            ):
                if idx >= screenshot_num:
                    break

                if page.locator('[data-testid="content-gate"]').is_visible():
                    page.locator('[data-testid="content-gate"] button').click()

                comment_url = comment["comment_url"]
                if not comment_url.startswith("http"):
                    comment_url = f"https://www.reddit.com/{comment_url.lstrip('/')}"
                page.goto(comment_url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                if settings.config["reddit"]["thread"]["post_lang"]:
                    comment_tl = translators.translate_text(
                        comment["comment_body"],
                        translator="google",
                        to_language=settings.config["reddit"]["thread"]["post_lang"],
                    )
                    page.evaluate(
                        """([tl_content, tl_id]) => {
                            const legacy = document.querySelector(`#t1_${tl_id} > div:nth-child(2) > div > div[data-testid="comment"] > div`);
                            const shreddit = document.querySelector(`shreddit-comment[thingid="t1_${tl_id}"] [slot="comment"]`);
                            if (legacy) legacy.textContent = tl_content;
                            else if (shreddit) shreddit.textContent = tl_content;
                        }""",
                        [comment_tl, comment["comment_id"]],
                    )

                comment_locator = page.locator(f"#t1_{comment['comment_id']}").first
                if not comment_locator.is_visible():
                    comment_locator = page.locator(
                        f'shreddit-comment[thingid="t1_{comment["comment_id"]}"]'
                    ).first

                try:
                    if settings.config["settings"]["zoom"] != 1:
                        zoom = settings.config["settings"]["zoom"]
                        page.evaluate("document.body.style.zoom=" + str(zoom))
                        comment_locator.scroll_into_view_if_needed()
                        location = comment_locator.bounding_box()
                        for i in location:
                            location[i] = float("{:.2f}".format(location[i] * zoom))
                        page.screenshot(
                            clip=location,
                            path=f"assets/temp/{reddit_id}/png/comment_{idx}.png",
                        )
                    else:
                        comment_locator.screenshot(
                            path=f"assets/temp/{reddit_id}/png/comment_{idx}.png"
                        )
                except (PlaywrightTimeoutError, TimeoutError):
                    print("TimeoutError: Skipping screenshot...")
                    continue

        # close browser context when we are done using it
        context.close()

    print_substep("Screenshots downloaded Successfully.", style="bold green")
