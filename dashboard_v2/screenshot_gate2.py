"""Gate 2 screenshot script — real data, desktop + mobile.

All targeting done via URL query params so we don't need to click
Streamlit's headless-unfriendly selectbox. Element-level screenshots via
.block-container (full-page returns blank in this env).
"""
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

PORT = 8509
URL = f"http://localhost:{PORT}"


def wait_for_server(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def click_tab(page, name: str) -> None:
    """Click a tab via JS — sidebar hit-tests block .click() on the second tab."""
    page.evaluate(
        """(name) => {
            const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
            const t = tabs.find(b => b.textContent.trim() === name);
            if (t) t.click();
        }""",
        name,
    )


def main():
    out = "/Users/kevin/Desktop/new_statistics/xFTA/dashboard_v2/screenshots/gate2"
    os.makedirs(out, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---- DESKTOP ----------------------------------------------------
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1) Leaderboard default (All seasons, All positions, 300+)
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        page.wait_for_selector('.lb-wrap', timeout=15000)
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/leaderboard_desktop.png"
        )
        print("  leaderboard_desktop.png")

        # 2) Player hero — Embiid (default)
        click_tab(page, "Player")
        page.wait_for_selector('.hero-grid', timeout=10000)
        time.sleep(2.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_embiid_desktop.png"
        )
        print("  player_embiid_desktop.png")

        # 3) Player hero — Klay (negative delta) via URL param
        page.goto(f"{URL}/?player=Klay+Thompson", wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        click_tab(page, "Player")
        page.wait_for_selector('.hero-grid', timeout=10000)
        time.sleep(2.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_klay_desktop.png"
        )
        print("  player_klay_desktop.png")

        # 4) Player hero — Luka
        page.goto(f"{URL}/?player=Luka+Doncic", wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        click_tab(page, "Player")
        page.wait_for_selector('.hero-grid', timeout=10000)
        time.sleep(2.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_luka_desktop.png"
        )
        print("  player_luka_desktop.png")

        # 5) Player hero — Giannis (extreme positive)
        page.goto(f"{URL}/?player=Giannis+Antetokounmpo", wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        click_tab(page, "Player")
        page.wait_for_selector('.hero-grid', timeout=10000)
        time.sleep(2.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_giannis_desktop.png"
        )
        print("  player_giannis_desktop.png")

        # 6) 2024-25 Centers filter — capture the leaderboard in cohort
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        page.wait_for_selector('.lb-wrap', timeout=15000)
        time.sleep(2.0)
        # Set state directly: set query params the app reads at boot.
        # We approximate by using JS to dispatch a change event — easier path:
        # we add a "?season=2024-25&position=Center" hook below in app.
        page.evaluate("""
            () => {
                const url = new URL(window.location);
                url.searchParams.set('season', '2024-25');
                url.searchParams.set('position', 'Center');
                window.location.href = url.toString();
            }
        """)
        time.sleep(4.0)
        page.wait_for_selector('.lb-wrap', timeout=10000)
        time.sleep(1.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/leaderboard_2024-25_centers_desktop.png"
        )
        print("  leaderboard_2024-25_centers_desktop.png")

        ctx.close()

        # ---- MOBILE -----------------------------------------------------
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = ctx.new_page()

        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        page.wait_for_selector('.lb-wrap', timeout=15000)
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/leaderboard_mobile.png"
        )
        print("  leaderboard_mobile.png")

        page.goto(f"{URL}/?player=Joel+Embiid", wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        click_tab(page, "Player")
        page.wait_for_selector('.hero-grid', timeout=10000)
        time.sleep(2.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_mobile.png"
        )
        print("  player_mobile.png")

        ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
