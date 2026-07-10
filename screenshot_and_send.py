"""
Opens a deployed Streamlit app, wakes it up if Streamlit Community Cloud
shows a "this app is asleep" screen, waits for it to finish computing,
scrolls through the ENTIRE page using real mouse-wheel events (more
reliable than programmatic scrollTop, which some apps don't respond to),
detects the bottom by comparing screenshots directly (stop once a scroll
produces no *significant* visual change — a percentage-of-pixels-changed
threshold rather than exact byte equality, since animated/live content
like PowerTrend badges and the Volatility Pickup section repaint a small
part of the page on their own even when nothing actually scrolled, which
previously caused those sections to be captured twice), stitches every
step into one full image, and sends it to Telegram as a document.

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
from PIL import Image, ImageChops

APP_URL = os.environ["STREAMLIT_APP_URL"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

VIEWPORT_WIDTH = 1600
VIEWPORT_HEIGHT = 1200

# How long to wait for the app to finish computing before scrolling/screenshotting.
FIXED_WAIT_SECONDS = 600  # 10 minutes

SCROLL_PAUSE_SECONDS = 2   # let charts/tables re-render after each scroll step
MAX_SCROLL_STEPS = 45      # safety cap

# A real scroll shifts almost the entire viewport, so most pixels change.
# Live/animated widgets (PowerTrend badges, Volatility Pickup Z-scores,
# mesh-line hover states) only repaint a small part of the page. This
# threshold distinguishes "we actually scrolled" from "something on the
# current view just animated" so we don't capture the same section twice.
DIFF_PIXEL_FRACTION_THRESHOLD = 0.05   # >5% of pixels must change to count as "scrolled"
CONSECUTIVE_NO_SCROLL_LIMIT = 2        # confirm bottom twice before stopping (animation-tolerant)

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


def images_differ_significantly(im1, im2, threshold_fraction=DIFF_PIXEL_FRACTION_THRESHOLD):
    """
    True if a meaningfully large portion of the viewport changed between
    two screenshots (i.e. we actually scrolled), False if the difference
    is small enough to just be animated content repainting in place.
    """
    diff = ImageChops.difference(im1.convert("L"), im2.convert("L"))
    hist = diff.histogram()
    # Ignore tiny per-pixel noise (anti-aliasing, JPEG-ish compression
    # artifacts even in PNG re-renders); count pixels with a real change.
    significant_pixels = sum(hist[25:])
    total_pixels = im1.width * im1.height
    return (significant_pixels / total_pixels) > threshold_fraction


def capture_full_scroll(page):
    hide_fixed_chrome(page)

    # Position the mouse over the main content column (not the sidebar)
    # so wheel events target the actual scrollable dashboard area.
    page.mouse.move(VIEWPORT_WIDTH * 0.7, VIEWPORT_HEIGHT / 2)
    time.sleep(0.3)

    screenshots = []
    prev_img = Image.open(io.BytesIO(page.screenshot()))
    screenshots.append(prev_img)
    print("  captured step 1")

    consecutive_no_scroll = 0

    for i in range(MAX_SCROLL_STEPS):
        page.mouse.wheel(0, VIEWPORT_HEIGHT)
        time.sleep(SCROLL_PAUSE_SECONDS)

        new_img = Image.open(io.BytesIO(page.screenshot()))

        # A real scroll changes most of the viewport. Animated widgets
        # (PowerTrend badges, Volatility Pickup Z-scores, mesh-line hover
        # states) only repaint a small part of it. Using a percentage-of-
        # pixels-changed threshold instead of exact byte equality means an
        # animation tick no longer gets mistaken for "we scrolled," which
        # was causing sections to be captured twice.
        if not images_differ_significantly(prev_img, new_img):
            consecutive_no_scroll += 1
            print(f"  no significant change after step {i+1} "
                  f"(likely animation only, not a real scroll) "
                  f"[{consecutive_no_scroll}/{CONSECUTIVE_NO_SCROLL_LIMIT}]")
            if consecutive_no_scroll >= CONSECUTIVE_NO_SCROLL_LIMIT:
                print("  reached bottom")
                break
            # Don't append a duplicate slice, but keep scrolling — this
            # frame may just have landed on an animation tick even though
            # we did move down.
            continue

        consecutive_no_scroll = 0
        screenshots.append(new_img)
        prev_img = new_img
        print(f"  captured step {i+2}")

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
