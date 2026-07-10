"""
Opens a deployed Streamlit app, wakes it up if Streamlit Community Cloud
shows a "this app is asleep" screen, waits for it to finish computing,
scrolls through the ENTIRE page using real mouse-wheel events (more
reliable than programmatic scrollTop, which some apps don't respond to),
detects the bottom by checking the page's actual scroll position (NOT by
comparing screenshot bytes, since animated/live content like PowerTrend
badges and the Volatility Pickup section can repaint on their own and
falsely look like "the page moved"), stitches every step into one full
image, and sends it to Telegram as a document.

Env vars required (set as GitHub Actions secrets):
  STREAMLIT_APP_URL   e.g. https://your-app-name.streamlit.app
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import os
import sys
import io
import time
import requests
from playwright.sync_api import sync_playwright
from PIL import Image

APP_URL = os.environ["STREAMLIT_APP_URL"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

VIEWPORT_WIDTH = 1600
VIEWPORT_HEIGHT = 1200

# How long to wait for the app to finish computing before scrolling/screenshotting.
FIXED_WAIT_SECONDS = 600  # 10 minutes

SCROLL_PAUSE_SECONDS = 2   # let charts/tables re-render after each scroll step
MAX_SCROLL_STEPS = 45      # safety cap

OUTPUT_PATH = "full_screenshot.png"

WAKE_BUTTON_TEXTS = [
    "Yes, get this app back up!",
    "Get this app back up",
    "Wake app up",
    "Wake up",
]


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
    """Hide fixed header/toolbar/deploy-badge elements so they don't repeat in every slice."""
    page.add_style_tag(content="""
        header[data-testid="stHeader"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        [class*="viewerBadge"] { display: none !important; }
        [data-testid*="Badge"] { display: none !important; }
    """)


def log_diagnostics(page):
    info = page.evaluate("""
        () => {
            const doc = document.scrollingElement || document.documentElement;
            const main = document.querySelector('[data-testid="stAppViewContainer"]');
            return {
                docScrollHeight: doc.scrollHeight,
                docClientHeight: doc.clientHeight,
                mainExists: !!main,
                mainScrollHeight: main ? main.scrollHeight : null,
                mainClientHeight: main ? main.clientHeight : null,
                bodyTextLength: document.body.innerText.length,
                title: document.title,
            };
        }
    """)
    print(f"Diagnostics: {info}")
    return info


def get_scroll_top(page):
    """
    Returns the current scroll offset of whatever element is actually
    scrolling the page. Falls back to the Streamlit app-view container
    if the document itself isn't the scrolling element (common in
    Streamlit layouts where an inner div owns the scroll).
    """
    return page.evaluate("""
        () => {
            const doc = document.scrollingElement || document.documentElement;
            const main = document.querySelector('[data-testid="stAppViewContainer"]');

            // Prefer whichever element actually has scrollable overflow.
            if (main && main.scrollHeight > main.clientHeight + 5) {
                return main.scrollTop;
            }
            return doc.scrollTop;
        }
    """)


def capture_full_scroll(page):
    hide_fixed_chrome(page)

    # Position the mouse over the main content column (not the sidebar)
    # so wheel events target the actual scrollable dashboard area.
    page.mouse.move(VIEWPORT_WIDTH * 0.7, VIEWPORT_HEIGHT / 2)
    time.sleep(0.3)

    screenshots = []
    screenshots.append(Image.open(io.BytesIO(page.screenshot())))
    print("  captured step 1")

    last_scroll_top = get_scroll_top(page)
    print(f"  initial scrollTop={last_scroll_top}")

    for i in range(MAX_SCROLL_STEPS):
        page.mouse.wheel(0, VIEWPORT_HEIGHT)
        time.sleep(SCROLL_PAUSE_SECONDS)

        new_scroll_top = get_scroll_top(page)

        # Use actual scroll position, not screenshot-byte-equality, to
        # decide whether we moved. Animated content (PowerTrend badges,
        # Volatility Pickup Z-score section, mesh-line hover states) can
        # change pixels without the page having scrolled at all, which
        # previously caused duplicated slices.
        if new_scroll_top <= last_scroll_top:
            print(f"  scrollTop unchanged ({new_scroll_top}) after step {i+1} — reached bottom")
            break

        screenshots.append(Image.open(io.BytesIO(page.screenshot())))
        last_scroll_top = new_scroll_top
        print(f"  captured step {i+2} (scrollTop={new_scroll_top})")

    print(f"Captured {len(screenshots)} viewport screenshots")
    return screenshots


def stitch(screenshots):
    """Simple vertical stack — each wheel scroll moves roughly one viewport height,
    so slices are concatenated in order. Minor seam overlap/gap is possible but
    all content will be present."""
    width = screenshots[0].width
    total_height = sum(im.height for im in screenshots)
    stitched = Image.new("RGB", (width, total_height), "white")

    y = 0
    for im in screenshots:
        stitched.paste(im, (0, y))
        y += im.height

    return stitched


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        print(f"Opening {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        woke = try_wake_app(page)
        if woke:
            print("Clicked wake-up prompt, app should now start booting...")
        else:
            print("No wake-up prompt detected, app was likely already awake.")

        print(f"Waiting {FIXED_WAIT_SECONDS}s for the app to finish computing...")
        time.sleep(FIXED_WAIT_SECONDS)

        log_diagnostics(page)

        screenshots = capture_full_scroll(page)
        browser.close()

    stitched = stitch(screenshots)
    stitched.save(OUTPUT_PATH)
    print(f"Saved stitched screenshot: {stitched.width}x{stitched.height}")

    print("Sending to Telegram as document...")
    with open(OUTPUT_PATH, "rb") as f:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data={"chat_id": CHAT_ID, "caption": "Daily RS Screener (full page)"},
            files={"document": f},
            timeout=120,
        )

    if resp.status_code != 200:
        print(f"Telegram send failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    print("Sent successfully.")


if __name__ == "__main__":
    main()