"""
Opens a deployed Streamlit app, waits for it to fully render, scrolls
through the entire page (detecting whichever element actually scrolls —
window or an inner Streamlit container), stitches every viewport-sized
screenshot into one full image, and sends it to Telegram as a document.

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

SCROLL_PAUSE_SECONDS = 1.5  # let charts/tables re-render after each scroll step
MAX_SCROLL_STEPS = 45       # safety cap — comfortably above your observed ~22-30 needed

OUTPUT_PATH = "full_screenshot.png"


def get_current_scroll_position(page):
    """
    Read whichever scroll position is actually nonzero — the window's or
    an inner Streamlit container's — after a Page Down press.
    """
    return page.evaluate("""
        () => {
            const doc = document.scrollingElement || document.documentElement;
            if (doc.scrollTop > 0) return doc.scrollTop;
            const main = document.querySelector('[data-testid="stAppViewContainer"]') ||
                         document.querySelector('section.main') ||
                         document.querySelector('.main');
            return main ? main.scrollTop : doc.scrollTop;
        }
    """)


def hide_fixed_chrome(page):
    """Hide Streamlit's fixed top header/toolbar so it doesn't repeat in every slice."""
    page.add_style_tag(content="""
        header[data-testid="stHeader"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
    """)


def capture_full_scroll(page):
    hide_fixed_chrome(page)

    # Click into the page body first so keyboard events actually target it
    page.mouse.click(VIEWPORT_WIDTH // 2, VIEWPORT_HEIGHT // 2)
    time.sleep(0.5)

    screenshots = []   # list of (position, PIL.Image)
    pos = get_current_scroll_position(page)
    img_bytes = page.screenshot()
    screenshots.append((pos, Image.open(io.BytesIO(img_bytes))))
    print(f"  captured step 1: pos={pos}")

    for i in range(MAX_SCROLL_STEPS):
        page.keyboard.press("PageDown")
        time.sleep(SCROLL_PAUSE_SECONDS)

        new_pos = get_current_scroll_position(page)
        if new_pos == pos:
            print(f"  no further scroll movement after step {i+1} — reached bottom")
            break

        pos = new_pos
        img_bytes = page.screenshot()
        screenshots.append((pos, Image.open(io.BytesIO(img_bytes))))
        print(f"  captured step {i+2}: pos={pos}")

    total_height = pos + VIEWPORT_HEIGHT
    print(f"Captured {len(screenshots)} viewport screenshots, total height ~{total_height}px")
    return screenshots, total_height


def stitch(screenshots, total_height):
    width = screenshots[0][1].width
    stitched = Image.new("RGB", (width, total_height), "white")

    # Paste in capture order at each screenshot's real recorded position.
    # Later screenshots simply overwrite the overlapping region with the
    # same content and extend further down — no manual crop math needed.
    for pos, img in screenshots:
        stitched.paste(img, (0, pos))

    return stitched


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        print(f"Opening {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)

        print(f"Waiting {FIXED_WAIT_SECONDS}s for the app to finish computing...")
        time.sleep(FIXED_WAIT_SECONDS)

        screenshots, total_height = capture_full_scroll(page)
        browser.close()

    stitched = stitch(screenshots, total_height)
    stitched.save(OUTPUT_PATH)
    print(f"Saved stitched screenshot: {stitched.width}x{stitched.height}")

    # Sent as a document (not sendPhoto) — Telegram photos have a strict
    # dimension/aspect-ratio limit that a very tall stitched image will exceed.
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
