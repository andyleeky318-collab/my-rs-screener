"""
Opens the deployed Streamlit app, wakes it up if asleep, waits for the
script to FINISH computing (detected by the top-right "running/stop"
status widget appearing then disappearing), then walks through the page
section-by-section and sends each section as its OWN Telegram photo
(never combined/stitched).

- Screenshot 1 is always the very top of the page.
- Every screenshot excludes the sidebar (cropped, not scaled — full native
  resolution of the main content column only).
- Subsequent screenshots are triggered by scrolling to + locating each
  keyword/heading in SECTION_KEYWORDS, in page order. Each keyword is
  RETRIED for a few seconds in case the section hasn't rendered yet
  (fixes the old bug where a still-loading page caused every section to
  be silently skipped in under a second).
- Hard cutoff: the ENTIRE run (load-wait + all captures) must finish within
  MAX_RUNTIME_SECONDS (10 minutes). If the cutoff hits mid-way, whatever
  hasn't been captured yet is simply skipped.
- The whole run is wrapped in try/except with full traceback logging so a
  single unexpected error can no longer silently kill the script after
  only the first screenshot.

Env vars required (set as GitHub Actions secrets):
  STREAMLIT_APP_URL   e.g. https://your-app-name.streamlit.app
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import os
import time
import traceback
import requests
from playwright.sync_api import sync_playwright

APP_URL   = os.environ["STREAMLIT_APP_URL"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

VIEWPORT_WIDTH  = 1600
VIEWPORT_HEIGHT = 1200

MAX_RUNTIME_SECONDS   = 10 * 60   # hard cutoff for the ENTIRE run
LOAD_WAIT_TIMEOUT_CAP = 8 * 60    # never let the "wait for load" step alone eat the whole budget
SCROLL_SETTLE_SECONDS = 3         # let charts / custom HTML components re-render after a scroll

# How long (seconds) to keep retrying to find a single section keyword
# before giving up on it. Content can still be streaming in even after
# the top-level "running" indicator has cleared.
SECTION_SEARCH_TIMEOUT = 25
SECTION_SEARCH_POLL    = 2

# How long to wait, at the very start, for the "running" status widget to
# actually appear at least once. If it never appears within this window we
# assume the app was already idle/awake and move on (rather than treating
# "widget not found yet" as "already finished").
RUNNING_WIDGET_APPEAR_TIMEOUT = 45

# The status widget alone proved unreliable (it can report "finished" after
# only ~2s on a dashboard that actually takes much longer to compute). As a
# second, authoritative gate we wait for real dashboard content — the first
# few section keywords — to actually show up anywhere on the page,
# including inside iframes (custom HTML/Plotly components often live in an
# <iframe>, which plain page.get_by_text() does NOT search by default).
CONTENT_READY_TIMEOUT = 150
CONTENT_READY_POLL    = 3

WAKE_BUTTON_TEXTS = [
    "Yes, get this app back up!",
    "Get this app back up",
    "Wake app up",
    "Wake up",
]

# Order matters — should match the order these sections physically appear
# top-to-bottom on the page. Each entry is matched against visible text
# (substring, case-sensitive-ish via Playwright's text engine) anywhere on
# the page, including SVG text (e.g. Plotly chart titles).
SECTION_KEYWORDS = [
    "New Highs vs New Lows",
    "Refresh Theme Insight",
    "Setup =",
    "Weekly vs Monthly",
    "Stage",
    "Market Regime",
    "Minervini (Positive Pct",
    "RS Leader = Long term",
    "Retry AI Analysis",
    "RS NH B4 Price = Opportunity",
    "PPP = Opportunity",
    "Gapper Earning Drift = Opportunity",
    "Two Botak = Short term Group burst",
    "Engulfing = HL",
    "3x Engulfing",
    "PowerTrend = Thematic Extended",
    "Volatility",
    "Value Trap",
    "Setup Quality",
    "Quant Sentiment",
]

# Used to confirm the dashboard has actually rendered before we trust
# "the app is done computing". We only need ONE of these to show up.
CONTENT_READY_ANCHORS = SECTION_KEYWORDS[:5]


class Deadline:
    """Simple global stopwatch enforcing the 10-minute hard cutoff."""

    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def remaining(self):
        return self.end - time.monotonic()

    def expired(self):
        return self.remaining() <= 0


deadline = Deadline(MAX_RUNTIME_SECONDS)


def send_photo(image_bytes, caption):
    """Send exactly ONE screenshot to Telegram. Never combine/stitch."""
    if not image_bytes:
        print(f"Skipping empty image for '{caption}'")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption[:1024]},
            files={"photo": ("screenshot.png", image_bytes, "image/png")},
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"Telegram send FAILED for '{caption}': {resp.status_code} {resp.text}")
        else:
            print(f"Sent: {caption}")
    except Exception as e:
        print(f"Telegram send raised an exception for '{caption}': {e}")


def try_wake_app(page):
    """Click through Streamlit Community Cloud's sleep-screen prompt if present."""
    for text in WAKE_BUTTON_TEXTS:
        try:
            btn = page.get_by_text(text, exact=False)
            if btn.count() > 0 and btn.first.is_visible():
                print(f"Found wake-up prompt ('{text}'), clicking it...")
                btn.first.click()
                time.sleep(10)
                return True
        except Exception:
            continue
    return False


def hide_fixed_chrome(page):
    """Hide fixed header/toolbar/deploy-badge elements so they don't appear in slices."""
    try:
        page.add_style_tag(content="""
            header[data-testid="stHeader"] { display: none !important; }
            [data-testid="stToolbar"] { display: none !important; }
            [data-testid="stDecoration"] { display: none !important; }
            [class*="viewerBadge"] { display: none !important; }
            [data-testid*="Badge"] { display: none !important; }
        """)
    except Exception as e:
        print(f"hide_fixed_chrome failed (non-fatal): {e}")


def find_text_anywhere(page, keyword):
    """
    Search for `keyword` in the main page AND in every iframe on the page.
    Custom HTML/Plotly components in Streamlit are often rendered inside an
    <iframe>, and Playwright's page.get_by_text() only searches the main
    frame by default — this is why every section was reported "not found"
    even once the dashboard had actually rendered.
    Returns a Locator you can scroll_into_view_if_needed() on, or None.
    """
    try:
        locator = page.get_by_text(keyword, exact=False)
        if locator.count() > 0:
            return locator.first
    except Exception as e:
        print(f"Main-frame lookup error for '{keyword}': {e}")

    try:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                flocator = frame.get_by_text(keyword, exact=False)
                if flocator.count() > 0:
                    return flocator.first
            except Exception:
                continue
    except Exception as e:
        print(f"Frame enumeration error for '{keyword}': {e}")

    return None


def wait_for_dashboard_content(page, timeout_seconds):
    """
    Authoritative readiness gate: poll (main frame + all iframes) until any
    of CONTENT_READY_ANCHORS actually appears, or timeout. This is what
    decides whether the page is truly ready to screenshot — NOT the
    stStatusWidget, which proved unreliable (it can report the app as
    'finished' within ~2s on a dashboard that genuinely takes much longer).
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        for anchor in CONTENT_READY_ANCHORS:
            if find_text_anywhere(page, anchor) is not None:
                print(f"Dashboard content confirmed ready after {time.monotonic() - start:.0f}s (found '{anchor}')")
                return True
        time.sleep(CONTENT_READY_POLL)
    print(f"Dashboard content never confirmed after {timeout_seconds}s — proceeding anyway (screenshots may be incomplete).")
    return False


def is_app_running(page):
    """
    Streamlit shows a status widget (spinner + Stop button) in the top-right
    corner while the script is actively executing. It disappears once the
    run fully completes. We treat it being absent/invisible as "not running".
    """
    try:
        widget = page.locator('[data-testid="stStatusWidget"]')
        if widget.count() == 0:
            return False
        return widget.first.is_visible()
    except Exception:
        return False


def wait_for_running_widget_to_appear(page, timeout_seconds):
    """
    Wait for the running/stop indicator to show up at least once. This
    prevents the old bug where "widget not found yet" (because the page is
    still booting) was mistaken for "the run already finished".
    Returns True if it appeared, False if it never showed up within the
    timeout (in which case the app was probably already idle/awake).
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        if is_app_running(page):
            print(f"Detected app actively running after {time.monotonic() - start:.0f}s")
            return True
        time.sleep(2)
    print("Running indicator never appeared — assuming app was already idle.")
    return False


def wait_for_app_to_finish(page, timeout_seconds):
    """
    First wait (bounded) for the running indicator to appear at all, then
    poll until it disappears (script finished), or timeout.
    """
    appear_budget = min(RUNNING_WIDGET_APPEAR_TIMEOUT, max(10, timeout_seconds // 3))
    was_running = wait_for_running_widget_to_appear(page, appear_budget)

    remaining_budget = timeout_seconds - appear_budget
    if remaining_budget <= 0:
        remaining_budget = 30

    start = time.monotonic()
    while time.monotonic() - start < remaining_budget:
        if not is_app_running(page):
            # Confirm it's really finished and not just a brief gap between reruns
            time.sleep(2)
            if not is_app_running(page):
                print(f"App finished computing after {time.monotonic() - start:.0f}s (was_running={was_running})")
                return True
        time.sleep(3)
    print("Timed out waiting for the app to finish computing — proceeding anyway.")
    return False


def get_sidebar_right_edge(page):
    """
    Return the x-coordinate (px) where the main content area begins,
    i.e. the right edge of the sidebar (which starts with 'Settings').
    Falls back to 0 (no crop) if the sidebar can't be found.
    """
    try:
        sidebar = page.locator('[data-testid="stSidebar"]')
        if sidebar.count() > 0 and sidebar.first.is_visible():
            box = sidebar.first.bounding_box()
            if box:
                return int(box["x"] + box["width"])
    except Exception:
        pass
    return 0


def screenshot_main_content(page, sidebar_right):
    """
    Screenshot the current viewport, clipped to exclude the sidebar.
    This is a native-resolution crop (via Playwright's clip option) —
    no resizing, scaling, or stitching involved.
    """
    clip = {
        "x": sidebar_right,
        "y": 0,
        "width": max(VIEWPORT_WIDTH - sidebar_right, 1),
        "height": VIEWPORT_HEIGHT,
    }
    try:
        return page.screenshot(clip=clip)
    except Exception as e:
        print(f"Screenshot failed: {e}")
        return None


def capture_and_send_top(page, sidebar_right):
    try:
        page.evaluate("window.scrollTo(0, 0)")
    except Exception as e:
        print(f"scrollTo(0,0) failed (non-fatal): {e}")
    time.sleep(SCROLL_SETTLE_SECONDS)
    img_bytes = screenshot_main_content(page, sidebar_right)
    send_photo(img_bytes, "Top of page")


def capture_and_send_section(page, sidebar_right, keyword):
    """
    Poll for up to SECTION_SEARCH_TIMEOUT seconds looking for the keyword
    (main frame + all iframes), rather than checking once. Streamlit can
    still be streaming content in even after the top-level running
    indicator has cleared.
    """
    start = time.monotonic()
    target = None
    while time.monotonic() - start < SECTION_SEARCH_TIMEOUT:
        target = find_text_anywhere(page, keyword)
        if target is not None:
            break
        time.sleep(SECTION_SEARCH_POLL)

    if target is None:
        print(f"Section not found after {SECTION_SEARCH_TIMEOUT}s: '{keyword}' — skipping.")
        return

    try:
        target.scroll_into_view_if_needed(timeout=15000)
    except Exception as e:
        print(f"Could not scroll to '{keyword}': {e} — skipping.")
        return

    time.sleep(SCROLL_SETTLE_SECONDS)
    img_bytes = screenshot_main_content(page, sidebar_right)
    send_photo(img_bytes, keyword)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        print(f"Opening {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        if try_wake_app(page):
            print("Clicked wake-up prompt, app should now start booting...")
            # Give the rerun a few seconds to actually kick off before we
            # start polling for the running indicator.
            time.sleep(5)
        else:
            print("No wake-up prompt detected, app was likely already awake.")

        hide_fixed_chrome(page)

        # Status widget is used only as an informational signal now — it
        # proved unreliable as the sole gate (reported "finished" after
        # only ~2s on a dashboard that genuinely takes much longer).
        wait_for_running_widget_to_appear(page, min(RUNNING_WIDGET_APPEAR_TIMEOUT, max(10, deadline.remaining() // 4)))

        # Authoritative gate: wait for real dashboard content to actually
        # appear (checked across the main frame AND all iframes).
        content_budget = min(CONTENT_READY_TIMEOUT, max(30, deadline.remaining() - 90))
        wait_for_dashboard_content(page, content_budget)

        # One more short settle so any final chart/JS rendering (Plotly,
        # custom components) catches up after the text anchor appeared.
        time.sleep(5)

        hide_fixed_chrome(page)  # re-apply in case a rerun reset it
        sidebar_right = get_sidebar_right_edge(page)
        print(f"Sidebar right edge detected at x={sidebar_right}px")

        # 1. Always capture the very top of the page first
        if not deadline.expired():
            capture_and_send_top(page, sidebar_right)
        else:
            print("Deadline already reached before first capture — aborting.")
            browser.close()
            return

        # 2. Walk through each section keyword in order, screenshot + send individually
        for keyword in SECTION_KEYWORDS:
            if deadline.expired():
                print("Global 10-minute cutoff reached — stopping further captures.")
                break
            capture_and_send_section(page, sidebar_right, keyword)

        browser.close()

    print("Done.")


def main():
    try:
        run()
    except Exception:
        print("FATAL ERROR — run() raised an exception. Full traceback below:")
        traceback.print_exc()


if __name__ == "__main__":
    main()