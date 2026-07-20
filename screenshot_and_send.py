"""
Opens the deployed Streamlit app, wakes it up if asleep, waits for the
script to FINISH computing (detected purely by the top-right "running/stop"
status widget -- the one next to the "Fork" button -- appearing then
disappearing), then walks through the page section-by-section and sends
each section as its OWN Telegram photo (never combined/stitched).

- Screenshot 1 is always the very top of the page.
- Every screenshot excludes the sidebar (cropped, not scaled -- full native
  resolution of the main content column only).
- Subsequent screenshots are triggered by scrolling to + locating each
  keyword/heading in SECTION_KEYWORDS, in page order. Each keyword is
  RETRIED for a few seconds in case the section hasn't rendered yet.
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

TV_EMAIL     = os.environ.get("TRADINGVIEW_EMAIL")
TV_PASSWORD  = os.environ.get("TRADINGVIEW_PASSWORD")
TV_CHART_URL = os.environ.get("TRADINGVIEW_CHART_URL") 

TV_LOGIN_TIMEOUT_MS = 30000
TV_CHART_SETTLE_SECONDS = 10

VIEWPORT_WIDTH  = 1600
VIEWPORT_HEIGHT = 1200

MAX_RUNTIME_SECONDS   = 25 * 60   # hard cutoff for the ENTIRE run
SCROLL_SETTLE_SECONDS = 3         # let charts / custom HTML components re-render after a scroll

# How long (seconds) to keep retrying to find a single section keyword
# before giving up on it. Content can still be streaming in even after
# the "stop" widget has cleared.
SECTION_SEARCH_TIMEOUT = 160
SECTION_SEARCH_POLL    = 3

# How long to wait, at the very start, for the "running/stop" status widget
# to actually appear at least once. If it never appears within this window
# we assume the app was already idle/awake and move on (rather than
# treating "widget not found yet" as "already finished").
RUNNING_WIDGET_APPEAR_TIMEOUT = 45

# Once the widget has appeared, how long to wait for it to disappear again
# (i.e. the run to actually finish) before giving up and proceeding anyway.
FINISH_TIMEOUT_SECONDS = 8 * 60

SECTION_TOP_OFFSET_PX = 20

# Extra external (non-Streamlit) sites to screenshot AFTER all Streamlit
# sections above are done -- walked through IN ORDER, each just the top of
# the page (landing view, full width -- no sidebar to crop here), sent as
# its own separate Telegram photo. Heavier JS-rendered sites get a longer
# settle time since they keep rendering well after domcontentloaded.
# Tuple: (url, caption, settle_seconds, use_stealth)
# use_stealth applies the realistic-UA / webdriver-hiding mitigation below
# -- only turned on for sites running bot-verification checks (Finviz),
# everything else keeps Playwright's plain default page behavior.
EXTRA_SCREENSHOTS = [
    ("https://stockbee.blogspot.com/p/mm.html",
     "Stockbee", 3, False, "Primary Breadth Indicators"),
    ("https://docs.google.com/spreadsheets/d/1ZkNk5A5nPQGGSK00eAOlroGmJi2wVHPwdz3LAYAVb7U/edit?gid=0#gid=0",
     "Market Monitor Traffic Light", 8, False, None),
    ("https://stockcharts.com/sc3/ui/?s=%24USHL5",
     "$USHL5", 8, False, None),
    ("https://fullstackinvestor.co/dashboard",
     "Market Dashboard", 8, False, None),
    ("https://stockcharts.com/freecharts/candleglance.html?SPY,XLY,XLC,XLK,XLI,XLB,XLE,XLP,XLV,XLU,XLF|C|B14|1",
     "Sector RS", 8, False, None),
    ("https://aistockbubbleindex.com/",
     "AI Bubble", 8, False, None),
    ("https://finviz.com/map",
     "S&P 500 Map", 12, True, None),
]
EXTRA_PAGE_LOAD_TIMEOUT  = 30000  # ms

# Realistic desktop Chrome UA + a small init script that hides the
# "navigator.webdriver" flag Playwright's headless Chromium exposes by
# default. Some sites (e.g. Finviz) run Cloudflare-style bot-verification
# challenges that key off exactly this kind of automation fingerprint --
# this doesn't guarantee a pass, but it's the standard mitigation.
STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
STEALTH_INIT_SCRIPT = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"

WAKE_BUTTON_TEXTS = [
    "Yes, get this app back up!",
    "Get this app back up",
    "Wake app up",
    "Wake up",
]

# Order matters -- should match the order these sections physically appear
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
    "Early Bull = buyable",
    "Two Botak = Short term Group burst",
    "Engulfing = HL",
    "3x Engulfing",
    "PowerTrend = Thematic Extended",
    "Volatility",
    "Value Trap",
    "Pie Chart",
    "ETF Ratio",
    "Quant Sentiment",
    "Setup Quality",    
]

# The very last section to appear on the page. Its presence anywhere in the
# DOM (main frame or iframes) is used as the "whole page has fully loaded"
# signal -- we hold off on ALL screenshots (including the top-of-page one)
# until this is found, so we never capture a section that's still streaming in.
FINAL_SECTION_KEYWORD = SECTION_KEYWORDS[-1]

# How long to wait for FINAL_SECTION_KEYWORD to show up before giving up and
# capturing anyway (falls back gracefully rather than blocking forever).
# Quant Sentiment has been observed to take up to ~8 minutes to appear, so
# this is set with some buffer above that.
FULL_LOAD_TIMEOUT_SECONDS = 10 * 60
FULL_LOAD_POLL_SECONDS    = 3


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
    frame by default.
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


def is_app_running(page):
    """
    Streamlit shows a status widget (spinner + "Stop" button, next to the
    "Fork" button) in the top-right corner while the script is actively
    executing. It disappears once the run fully completes. This is the
    ONLY signal we use to decide the app has finished rendering.
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
    Wait for the "stop" indicator to show up at least once. Prevents
    mistaking "hasn't started yet" for "already finished".
    Returns True if it appeared, False if it never showed (app was
    probably already idle/awake).
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        if is_app_running(page):
            print(f"Detected app actively running after {time.monotonic() - start:.0f}s")
            return True
        time.sleep(2)
    print("Running indicator never appeared -- assuming app was already idle.")
    return False


def wait_for_app_to_finish(page, timeout_seconds):
    """
    Poll until the "stop" widget disappears (script finished), confirming
    twice in a row to avoid a brief gap between reruns being mistaken for
    "done", or until timeout.
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        if not is_app_running(page):
            time.sleep(2)
            if not is_app_running(page):
                print(f"App finished computing after {time.monotonic() - start:.0f}s")
                return True
        time.sleep(3)
    print("Timed out waiting for the app to finish computing -- proceeding anyway.")
    return False


def wait_for_full_content_loaded(page, timeout_seconds):
    """
    Wait until the LAST section keyword (FINAL_SECTION_KEYWORD, e.g.
    "Quant Sentiment") is found anywhere on the page (main frame or any
    iframe). Since sections render top-to-bottom, this being present means
    everything above it has also finished streaming in -- so it's safe to
    start taking screenshots from the top of the page onward.
    Falls back to proceeding anyway if it never appears within the timeout.
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        if find_text_anywhere(page, FINAL_SECTION_KEYWORD) is not None:
            print(f"Final section '{FINAL_SECTION_KEYWORD}' detected after "
                  f"{time.monotonic() - start:.0f}s -- page fully loaded. "
                  f"Waiting 30s for it to fully settle...")
            time.sleep(30)
            return True
        time.sleep(FULL_LOAD_POLL_SECONDS)
    print(f"Timed out after {timeout_seconds:.0f}s waiting for final section "
          f"'{FINAL_SECTION_KEYWORD}' -- proceeding with captures anyway.")
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
    return 240


def screenshot_main_content(page, sidebar_right):
    """
    Screenshot the current viewport, clipped to exclude the sidebar.
    This is a native-resolution crop (via Playwright's clip option) --
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
    still be streaming content in even after the "stop" widget has cleared.
    """
    start = time.monotonic()
    target = None
    while time.monotonic() - start < SECTION_SEARCH_TIMEOUT:
        target = find_text_anywhere(page, keyword)
        if target is not None:
            break
        time.sleep(SECTION_SEARCH_POLL)

    if target is None:
        print(f"Section not found after {SECTION_SEARCH_TIMEOUT}s: '{keyword}' -- skipping.")
        return

    try:
        # scrollIntoView with block:'start' pins the element to the TOP of
        # the viewport (not just "somewhere visible"), so the whole section
        # below it fits in the screenshot instead of being cut off.
        target.evaluate("el => el.scrollIntoView({block: 'start', behavior: 'instant'})")
        # Give some sections extra space above the heading
        offset = 40 if keyword in (
            "New Highs vs New Lows",
            "Refresh Theme Insight",
            "Setup =",
            "Retry AI Analysis",
            "3x Engulfing",
        ) else SECTION_TOP_OFFSET_PX

        if offset:
            page.evaluate(f"window.scrollBy(0, -{offset})")
    except Exception as e:
        print(f"Could not scroll to '{keyword}': {e} -- skipping.")
        return

    time.sleep(SCROLL_SETTLE_SECONDS)
    img_bytes = screenshot_main_content(page, sidebar_right)
    send_photo(img_bytes, keyword)


def capture_and_send_external_top(browser, url, caption, settle_seconds=SCROLL_SETTLE_SECONDS,
                                    use_stealth=False, wait_text=None, max_attempts=2):
    try:
        if use_stealth:
            ext_page = browser.new_page(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                user_agent=STEALTH_USER_AGENT,
                locale="en-US",
            )
            ext_page.add_init_script(STEALTH_INIT_SCRIPT)
        else:
            ext_page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        ext_page.goto(url, wait_until="domcontentloaded", timeout=EXTRA_PAGE_LOAD_TIMEOUT)

        for attempt in range(1, max_attempts + 1):
            found = True
            if wait_text:
                found = False
                wait_start = time.monotonic()
                while time.monotonic() - wait_start < 20:
                    if find_text_anywhere(ext_page, wait_text) is not None:
                        found = True
                        break
                    time.sleep(1)

            if found or attempt == max_attempts:
                break

            print(f"'{wait_text}' not found on attempt {attempt} for '{caption}' -- reloading...")
            ext_page.reload(wait_until="domcontentloaded", timeout=EXTRA_PAGE_LOAD_TIMEOUT)

        time.sleep(settle_seconds)
        img_bytes = ext_page.screenshot()
        send_photo(img_bytes, caption)
        ext_page.close()
    except Exception as e:
        print(f"External screenshot failed for '{url}': {e} -- skipping.")

def tradingview_login(browser):
    """
    Logs into TradingView via email/password and returns an authenticated
    Playwright page. Returns None on any failure (never raises) so a login
    problem just results in this one screenshot being skipped.
    """
    if not (TV_EMAIL and TV_PASSWORD):
        print("TradingView credentials not set -- skipping TradingView screenshot.")
        return None

    try:
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        page.goto("https://www.tradingview.com/accounts/signin/",
                   wait_until="domcontentloaded", timeout=TV_LOGIN_TIMEOUT_MS)

        # The signin page shows social-login buttons first; click "Email" to
        # reveal the email/password form.
        email_toggle = page.get_by_text("Email", exact=False)
        if email_toggle.count() > 0:
            email_toggle.first.click()
            time.sleep(1)

        page.fill('input[name="username"]', TV_EMAIL)
        page.fill('input[name="password"]', TV_PASSWORD)
        page.click('button[type="submit"]')

        # Wait for login to complete -- signin form disappears once redirected.
        page.wait_for_selector('input[name="password"]', state="detached", timeout=TV_LOGIN_TIMEOUT_MS)
        time.sleep(3)
        print("TradingView login succeeded.")
        return page
    except Exception as e:
        print(f"TradingView login failed: {e} -- skipping TradingView screenshot.")
        return None


def capture_and_send_tradingview(browser):
    """
    Logs into TradingView and sends one screenshot of a chart. If
    TV_CHART_URL is set, goes straight there. If not, falls back to
    clicking the 'Products' tab in the top nav (which lands directly on
    a chart). Fully self-contained and non-fatal -- any failure just
    skips this photo.
    """
    page = tradingview_login(browser)
    if page is None:
        return

    try:
        if TV_CHART_URL:
            page.goto(TV_CHART_URL, wait_until="domcontentloaded", timeout=EXTRA_PAGE_LOAD_TIMEOUT)
        else:
            print("TRADINGVIEW_CHART_URL not set -- trying 'Products' nav click instead...")
            try:
                products = page.get_by_text("Products", exact=False)
                if products.count() == 0 or not products.first.is_visible():
                    print("Could not find 'Products' tab -- skipping TradingView screenshot.")
                    page.close()
                    return
                products.first.click()
                page.wait_for_load_state("domcontentloaded", timeout=EXTRA_PAGE_LOAD_TIMEOUT)
            except Exception as e:
                print(f"Could not click 'Products': {e} -- skipping TradingView screenshot.")
                page.close()
                return

        time.sleep(TV_CHART_SETTLE_SECONDS)
        img_bytes = page.screenshot()
        send_photo(img_bytes, "TradingView Chart")
        page.close()
    except Exception as e:
        print(f"TradingView chart screenshot failed: {e} -- skipping.")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        print(f"Opening {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        if try_wake_app(page):
            print("Clicked wake-up prompt, app should now start booting...")
            time.sleep(5)
        else:
            print("No wake-up prompt detected, app was likely already awake.")

        hide_fixed_chrome(page)

        # Wait for the "stop" widget (next to "Fork") to appear at least
        # once -- this is the ONLY readiness signal we use now.
        wait_for_running_widget_to_appear(
            page, min(RUNNING_WIDGET_APPEAR_TIMEOUT, max(10, deadline.remaining() // 4))
        )

        # ...then wait for it to disappear again -- that's what confirms the
        # app has fully finished computing/rendering.
        finish_budget = min(FINISH_TIMEOUT_SECONDS, max(30, deadline.remaining() - 60))
        wait_for_app_to_finish(page, finish_budget)

        # One more short settle so any final chart/JS rendering (Plotly,
        # custom components) catches up right after the widget clears.
        time.sleep(5)

        # Extra safety net: the "stop" widget clearing doesn't guarantee every
        # section has actually streamed into the DOM yet. Wait until the last
        # section keyword (Quant Sentiment) is found anywhere on the page --
        # ONLY then do we consider the page fully loaded and start capturing.
        full_load_budget = min(FULL_LOAD_TIMEOUT_SECONDS, max(30, deadline.remaining() - 60))
        wait_for_full_content_loaded(page, full_load_budget)

        hide_fixed_chrome(page)  # re-apply in case a rerun reset it
        sidebar_right = get_sidebar_right_edge(page)
        print(f"Sidebar right edge detected at x={sidebar_right}px")

        # 1. Always capture the very top of the page first
        if not deadline.expired():
            capture_and_send_top(page, sidebar_right)
        else:
            print("Deadline already reached before first capture -- aborting.")
            browser.close()
            return

        # 2. Walk through each section keyword in order, screenshot + send individually
        for keyword in SECTION_KEYWORDS:
            if deadline.expired():
                print("Global 10-minute cutoff reached -- stopping further captures.")
                break
            capture_and_send_section(page, sidebar_right, keyword)

        # 3. After all Streamlit sections are done, walk through each extra
        #    external site IN ORDER, screenshotting its landing view and
        #    sending it as its own photo.
        for url, caption, settle_seconds, use_stealth, wait_text in EXTRA_SCREENSHOTS:
            if deadline.expired():
                print("Global cutoff reached -- stopping further external site captures.")
                break
            capture_and_send_external_top(browser, url, caption, settle_seconds, use_stealth, wait_text)

        if not deadline.expired():
            capture_and_send_tradingview(browser)
        else:
            print("Global cutoff reached -- skipping TradingView screenshot.")

        browser.close()

    print("Done.")


def main():
    try:
        run()
    except Exception:
        print("FATAL ERROR -- run() raised an exception. Full traceback below:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
