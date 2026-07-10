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
FIXED_WAIT_SECONDS = 600  # wait exactly 10 minutes after opening the app before screenshotting


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1200})

        print(f"Opening {APP_URL} ...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)

        print(f"Waiting {FIXED_WAIT_SECONDS}s for the app to finish computing...")
        time.sleep(FIXED_WAIT_SECONDS)

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