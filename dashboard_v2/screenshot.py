"""Screenshot the xFTA dashboard with Playwright."""

import subprocess
import time
import os
import signal
import sys

from typing import Optional
from playwright.sync_api import sync_playwright

STREAMLIT_PORT = 8502  # use a different port to avoid conflicts
BASE_URL = f"http://localhost:{STREAMLIT_PORT}"

def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False

def screenshot_tab(page, tab_name: str, desktop_path: str, mobile_path: str, toggle_text: Optional[str] = None):
    # Click the tab
    tab = page.locator(f'button:has-text("{tab_name}")')
    if tab.count() > 0:
        tab.click()
        time.sleep(1.5)  # let it render
    # Optional toggle (e.g. radio button inside the tab)
    if toggle_text:
        toggle = page.locator(f'label:has-text("{toggle_text}")')
        if toggle.count() > 0:
            toggle.click()
            time.sleep(1.0)
    page.screenshot(path=desktop_path, full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    time.sleep(0.5)
    page.screenshot(path=mobile_path, full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})
    time.sleep(0.5)

def main():
    os.chdir("/Users/kevin/Desktop/new_statistics/xFTA")

    # Start streamlit
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "dashboard_v2/app.py",
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        print("Waiting for Streamlit server...")
        if not wait_for_server(BASE_URL, timeout=30):
            print("Server did not start in time.")
            proc.terminate()
            return
        print("Server ready.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.goto(BASE_URL)
            time.sleep(3)  # initial load

            out_dir = "/Users/kevin/Desktop/new_statistics/xFTA/dashboard_v2/screenshots"
            os.makedirs(out_dir, exist_ok=True)

            tabs = ["What is xFTA?", "Leaderboard", "Shot Chart", "Methodology"]
            for tab in tabs:
                desktop = os.path.join(out_dir, f"{tab.lower().replace(' ', '_')}_desktop.png")
                mobile = os.path.join(out_dir, f"{tab.lower().replace(' ', '_')}_mobile.png")
                screenshot_tab(page, tab, desktop, mobile)
                print(f"Screenshots for '{tab}' saved.")

            # Extra: Foul Rate view inside Shot Chart tab
            foul_desk = os.path.join(out_dir, "shot_chart_foul_rate_desktop.png")
            foul_mob = os.path.join(out_dir, "shot_chart_foul_rate_mobile.png")
            screenshot_tab(page, "Shot Chart", foul_desk, foul_mob, toggle_text="Foul Rate")
            print("Screenshots for 'Shot Chart (Foul Rate)' saved.")

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

if __name__ == "__main__":
    main()
