"""Gate 1 reskin screenshots — desktop + mobile, leaderboard + player + empty.

Element-level screenshots via .block-container (full-page returns blank
in this env). Tab clicks go through JS to bypass the sidebar hit-test
that intercepts the second tab.
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
    page.evaluate(
        """(name) => {
            const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
            const t = tabs.find(b => b.textContent.trim() === name);
            if (t) t.click();
        }""",
        name,
    )


def main():
    out = "/Users/kevin/Desktop/new_statistics/xFTA/dashboard_v2/screenshots/gate3"
    os.makedirs(out, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---- DESKTOP ----------------------------------------------------
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1) Leaderboard default
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_selector('button[role="tab"]', timeout=15000)
        page.wait_for_selector('.gap-table', timeout=15000)
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/leaderboard_desktop.png"
        )
        print("  leaderboard_desktop.png")

        # 2) Player tab — default (Embiid)
        click_tab(page, "Player")
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_embiid_desktop.png"
        )
        print("  player_embiid_desktop.png")

        # 3) Player tab — Klay (cool/negative)
        page.goto(f"{URL}/?hero_player=Klay+Thompson", wait_until="domcontentloaded")
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_klay_desktop.png"
        )
        print("  player_klay_desktop.png")

        # 4) Player tab — Doncic (mid-pack)
        page.goto(f"{URL}/?hero_player=Luka+Doncic", wait_until="domcontentloaded")
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_luka_desktop.png"
        )
        print("  player_luka_desktop.png")

        # 5) Methodology stub
        click_tab(page, "Methodology")
        time.sleep(2.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/methodology_desktop.png"
        )
        print("  methodology_desktop.png")

        # 6) Empty state — over-filter (set min FGA to max via slider)
        click_tab(page, "Leaderboard")
        page.wait_for_selector('.gap-table', timeout=10000)
        time.sleep(1.0)
        # Push the min FGA slider all the way right
        page.evaluate("""
            () => {
                const sliders = document.querySelectorAll('div[data-testid="stSlider"] input[type="range"]');
                if (sliders.length) {
                    const s = sliders[0];
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(s, '1500');
                    s.dispatchEvent(new Event('input', { bubbles: true }));
                    s.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        """)
        time.sleep(2.5)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/leaderboard_empty_desktop.png"
        )
        print("  leaderboard_empty_desktop.png")

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
        page.wait_for_selector('.gap-table', timeout=15000)
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/leaderboard_mobile.png"
        )
        print("  leaderboard_mobile.png")

        click_tab(page, "Player")
        time.sleep(3.0)
        page.locator('.block-container').first.screenshot(
            path=f"{out}/player_mobile.png"
        )
        print("  player_mobile.png")

        ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
