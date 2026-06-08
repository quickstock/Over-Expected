"""Screenshot the Gate 1 design shell with Playwright.

Uses element-level screenshots of Streamlit's .block-container — the
full-page screenshot in this headless environment produces blank captures,
but element screenshots work.
"""

import subprocess
import time
import os
import sys

from playwright.sync_api import sync_playwright

STREAMLIT_PORT = 8506
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


def main():
    os.chdir("/Users/kevin/Desktop/new_statistics/xFTA")

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "dashboard_v2/app.py",
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not wait_for_server(BASE_URL, timeout=30):
            print("Server failed to start.")
            return
        print("Server ready.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.goto(BASE_URL)
            page.wait_for_selector('button[role="tab"]', timeout=10000)
            time.sleep(5.0)  # let fonts + tables paint

            out = "/Users/kevin/Desktop/new_statistics/xFTA/dashboard_v2/screenshots/gate1"
            os.makedirs(out, exist_ok=True)

            # ---- Leaderboard: default -------------------------------------
            block = page.locator('.block-container').first
            block.screenshot(path=f"{out}/leaderboard_desktop.png")
            print("  leaderboard_desktop.png")

            # Mobile (390x844) — switch viewport and re-grab
            page.set_viewport_size({"width": 390, "height": 844})
            time.sleep(1.5)
            block = page.locator('.block-container').first
            block.screenshot(path=f"{out}/leaderboard_mobile.png")
            print("  leaderboard_mobile.png")

            # Back to desktop
            page.set_viewport_size({"width": 1440, "height": 900})
            time.sleep(1.0)

            # ---- Player tab ------------------------------------------------
            page.locator('button:has-text("Player")').first.click()
            time.sleep(1.5)
            block = page.locator('.block-container').first
            block.screenshot(path=f"{out}/player_desktop.png")
            print("  player_desktop.png")

            # Mobile player
            page.set_viewport_size({"width": 390, "height": 844})
            time.sleep(1.0)
            block = page.locator('.block-container').first
            block.screenshot(path=f"{out}/player_mobile.png")
            print("  player_mobile.png")
            page.set_viewport_size({"width": 1440, "height": 900})
            time.sleep(1.0)

            # ---- Player hero with Giannis (strong positive) ---------------
            try:
                # Click into the selectbox — it's the first stSelectbox
                page.locator('[data-testid="stSelectbox"]').first.locator('div[role="button"]').first.click()
                time.sleep(0.5)
                # click Giannis option
                page.locator('li:has-text("Giannis Antetokounmpo")').first.click()
                time.sleep(1.5)
                block = page.locator('.block-container').first
                block.screenshot(path=f"{out}/player_giannis_desktop.png")
                print("  player_giannis_desktop.png")
            except Exception as e:
                print(f"  (Giannis failed: {e})")

            # ---- Player hero with Klay (strong negative) ------------------
            try:
                page.locator('[data-testid="stSelectbox"]').first.locator('div[role="button"]').first.click()
                time.sleep(0.5)
                page.locator('li:has-text("Klay Thompson")').first.click()
                time.sleep(1.5)
                block = page.locator('.block-container').first
                block.screenshot(path=f"{out}/player_klay_desktop.png")
                print("  player_klay_desktop.png")
            except Exception as e:
                print(f"  (Klay failed: {e})")

            # ---- Filter: position C ---------------------------------------
            try:
                page.locator('button:has-text("Leaderboard")').first.click()
                time.sleep(1.0)
                # position selectbox is the 2nd stSelectbox
                page.locator('[data-testid="stSelectbox"]').nth(1).locator('div[role="button"]').first.click()
                time.sleep(0.5)
                page.locator('li:has-text("C")').first.click()
                time.sleep(1.5)
                block = page.locator('.block-container').first
                block.screenshot(path=f"{out}/leaderboard_centers_desktop.png")
                print("  leaderboard_centers_desktop.png")
            except Exception as e:
                print(f"  (filter failed: {e})")

            browser.close()
            print("All screenshots saved.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
