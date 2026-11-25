from pathlib import Path

from utils.console import print_step, print_substep

REDDIT_PROFILE_DIR = Path("video_creation/data/browser_profile")


def clear_cookie_by_name(context, cookie_cleared_name):
    cookies = context.cookies()
    filtered_cookies = [cookie for cookie in cookies if cookie["name"] != cookie_cleared_name]
    context.clear_cookies()
    context.add_cookies(filtered_cookies)


def has_reddit_session(context) -> bool:
    """Returns True if the browser context has an authenticated Reddit session cookie."""
    try:
        cookies = context.cookies("https://www.reddit.com")
        return any(c.get("name") == "reddit_session" and c.get("value") for c in cookies)
    except Exception:
        return False


def is_reddit_gated(page) -> bool:
    """Returns True if Reddit redirected to login or presented an anti-bot challenge."""
    try:
        title = page.title() or ""
        url = page.url or ""
        if "/login" in url or "Prove your humanity" in title:
            return True
        snippet = page.content()[:4000]
        if "Prove your humanity" in snippet or "whoa there" in snippet.lower():
            return True
    except Exception:
        pass
    return False


def launch_reddit_context(playwright, headless: bool = True, **context_kwargs):
    """Launches a persistent Chromium context backed by REDDIT_PROFILE_DIR."""
    REDDIT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(REDDIT_PROFILE_DIR),
        headless=headless,
        **context_kwargs,
    )


def ensure_reddit_session(
    playwright,
    target_url: str = "https://www.reddit.com/",
    require_auth: bool = True,
    force_visible: bool = False,
    **context_kwargs,
):
    """Returns an open (context, page) using the persistent Reddit browser profile.

    Tries headless first when a profile already exists (unless force_visible=True).
    If Reddit gates headless access or no authenticated session exists yet, opens a
    visible browser window so the user can sign in manually once, and keeps that
    verified context open for immediate use.
    """
    profile_exists = REDDIT_PROFILE_DIR.exists() and any(REDDIT_PROFILE_DIR.iterdir())

    if profile_exists and not force_visible:
        context = launch_reddit_context(playwright, headless=True, **context_kwargs)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        if not is_reddit_gated(page) and (not require_auth or has_reddit_session(context)):
            return context, page
        context.close()

    context = launch_reddit_context(playwright, headless=False, **context_kwargs)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    if is_reddit_gated(page) or (require_auth and not has_reddit_session(context)):
        if "Prove your humanity" not in (page.title() or "") and "/login" not in (page.url or ""):
            page.goto("https://www.reddit.com/login", wait_until="domcontentloaded", timeout=30000)
        print_step("Manual Reddit Sign-In Required (One-Time)")
        print_substep(
            "A browser window has been opened. Please sign in to Reddit (and complete any verification if shown), then press Enter here to continue...",
            style="bold yellow",
        )
        input()
        page.wait_for_timeout(1000)
        if page.url != target_url:
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)

    return context, page
