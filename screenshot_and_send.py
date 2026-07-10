"""
Opens a deployed Streamlit app, waits for it to fully render (including
waking it up if it was asleep), takes a full-page screenshot, and sends
it to a Telegram chat.

Env vars required (set as GitHub Actions secrets):
  STREAMLIT_APP_URL   e.g. https://your-app-name.streamlit.app
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

APP_URL = os.environ["STREAMLIT_APP_URL"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SCREENSHOT_PATH = "screenshot.png"

# How long to wait for the app to finish computing before screenshotting.
# This dashboard downloads a lot of data and runs heavy pandas/numpy work,
# so give it a generous ceiling.
MAX_WAIT_SECONDS = 240
POLL_INTERVAL = 5


def wait_for_app_ready(page):
    """
    Streamlit shows a 'Please wait...' wake-up screen when the app was
    asleep, and a running-man spinner in the top-right while computing.
    Poll until neither is present, up to MAX_WAIT_SECONDS.
    """
    waited = 0
    while waited < MAX_WAIT_SECONDS:
        wake_text = page.locator("text=Please wait")
        spinner = page.locator('[data-testid="stStatusWidget"]')

        wake_visible = wake_text.count() > 0 and wake_text.first.is_visible()
        spinner_visible = spinner.count() > 0 and spinner.first.is_visible()

        if not wake_visible and not spinner_visible:
            # give it one more short pause so the last chart/table settles
            time.sleep(3)
            return True

        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL

    return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1200})

        print(f"Opening {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)

        ready = wait_for_app_ready(page)
        if not ready:
            print("Warning: app may not have fully finished rendering, screenshotting anyway.")

        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        browser.close()

    print("Screenshot saved, sending to Telegram...")

    with open(SCREENSHOT_PATH, "rb") as f:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": "Daily RS Screener"},
            files={"photo": f},
            timeout=60,
        )

    if resp.status_code != 200:
        print(f"Telegram send failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    print("Sent successfully.")


if __name__ == "__main__":
    main()
