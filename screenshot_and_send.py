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
MAX_SCROLL_STEPS = 60       # safety cap

OUTPUT_PATH = "full_screenshot.png"


def get_scroll_metrics(page):
    """Detect whether the window or an inner Streamlit container is the real scroller."""
    return page.evaluate("""
        () => {
            const doc = document.scrollingElement || document.documentElement;
            if (doc.scrollHeight - doc.clientHeight > 5) {
                return { mode: 'window', scrollHeight: doc.scrollHeight, clientHeight: doc.clientHeight };
            }
            const main = document.querySelector('[data-testid="stAppViewContainer"]') ||
                         document.querySelector('section.main') ||
                         document.querySelector('.main');
            if (main) {
                return { mode: 'container', scrollHeight: main.scrollHeight, clientHeight: main.clientHeight };
            }
            return { mode: 'window', scrollHeight: doc.scrollHeight, clientHeight: doc.clientHeight };
        }
    """)


def scroll_to(page, mode, y):
    if mode == "window":
        page.evaluate(f"window.scrollTo(0, {y})")
    else:
        page.evaluate(f"""
            () => {{
                const main = document.querySelector('[data-testid="stAppViewContainer"]') ||
                             document.querySelector('section.main') ||
                             document.querySelector('.main');
                if (main) main.scrollTop = {y};
            }}
        """)


def hide_fixed_chrome(page):
    """Hide Streamlit's fixed top header/toolbar so it doesn't repeat in every slice."""
    page.add_style_tag(content="""
        header[data-testid="stHeader"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
    """)


def capture_full_scroll(page):
    metrics = get_scroll_metrics(page)
    mode = metrics["mode"]
    total_height = metrics["scrollHeight"]
    view_height = metrics["clientHeight"]

    print(f"Scroll mode: {mode} | total height: {total_height}px | viewport height: {view_height}px")

    hide_fixed_chrome(page)

    screenshots = []
    y = 0

    for i in range(MAX_SCROLL_STEPS):
        scroll_to(page, mode, y)
        time.sleep(SCROLL_PAUSE_SECONDS)

        img_bytes = page.screenshot()
        screenshots.append(Image.open(io.BytesIO(img_bytes)))
        print(f"  captured step {i+1}: y={y}")

        # re-check in case content grows as more of it scrolls into view
        metrics = get_scroll_metrics(page)
        total_height = max(total_height, metrics["scrollHeight"])

        if y + view_height >= total_height:
            break
        y += view_height

    print(f"Captured {len(screenshots)} viewport screenshots, total height ~{total_height}px")
    return screenshots, total_height


def stitch(screenshots, total_height):
    width = screenshots[0].width
    stitched = Image.new("RGB", (width, total_height), "white")

    y_offset = 0
    for idx, img in enumerate(screenshots):
        is_last = idx == len(screenshots) - 1
        if is_last:
            remaining = total_height - y_offset
            if 0 < remaining < img.height:
                # crop overlap so the last slice doesn't duplicate already-pasted content
                crop_top = img.height - remaining
                img = img.crop((0, crop_top, img.width, img.height))
        stitched.paste(img, (0, y_offset))
        y_offset += img.height

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
