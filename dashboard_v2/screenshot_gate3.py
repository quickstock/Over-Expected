"""Gate 3 screenshots — desktop + mobile, leaderboard + player + methodology.

Each capture uses a FRESH browser context so Streamlit's session state
isn't sticky across captures (the WebSocket persists across page.goto
within the same context, which makes the URL pre-select for hero_player
silently ignored on subsequent visits).

Element-level screenshots via .block-container (full-page returns blank
in this env). Tab clicks go through JS to bypass the sidebar hit-test
that intercepts the second tab.
"""
import os
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
    # Use Playwright's role-based click — fires the actual onClick that
    # Streamlit wires to tab[role=tab]. A bare .click() on the element
    # in JS doesn't reach Streamlit's React handler.
    page.get_by_role("tab", name=name).click()


def wait_tab_active(page, name: str, timeout_ms: int = 10000) -> None:
    """Wait until the named tab is the active one (aria-selected=true)."""
    page.wait_for_function(
        """(name) => {
            const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
            const t = tabs.find(b => b.textContent.trim() === name);
            return t && t.getAttribute('aria-selected') === 'true';
        }""",
        arg=name,
        timeout=timeout_ms,
    )
    # Then wait for the matching tabpanel to actually be visible
    page.wait_for_function(
        """(name) => {
            const tabs = Array.from(document.querySelectorAll('button[role="tab"]'));
            const idx = tabs.findIndex(b => b.textContent.trim() === name);
            if (idx < 0) return false;
            const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));
            const p = panels[idx];
            return p && getComputedStyle(p).display !== 'none' && p.getBoundingClientRect().width > 0;
        }""",
        arg=name,
        timeout=timeout_ms,
    )


def shot(page, name: str, outdir: str) -> None:
    """Screenshot the first .block-container."""
    page.locator(".block-container").first.screenshot(path=f"{outdir}/{name}.png")
    print(f"  {name}.png")


def fresh_desktop_capture(p, out: str, *, label: str, url: str = URL,
                          tab: str = "Leaderboard", settle: float = 2.0,
                          pre_action=None) -> None:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('button[role="tab"]', timeout=15000)
    if pre_action is not None:
        pre_action(page)
    click_tab(page, tab)
    wait_tab_active(page, tab)
    time.sleep(settle)
    shot(page, label, out)
    ctx.close()
    browser.close()


def fresh_mobile_capture(p, out: str, *, label: str, url: str = URL,
                         tab: str = "Leaderboard", settle: float = 2.0) -> None:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
    )
    page = ctx.new_page()
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('button[role="tab"]', timeout=15000)
    click_tab(page, tab)
    wait_tab_active(page, tab)
    time.sleep(settle)
    shot(page, label, out)
    ctx.close()
    browser.close()


def main():
    out = "/Users/kevin/Desktop/new_statistics/xFTA/dashboard_v2/screenshots/gate3"
    os.makedirs(out, exist_ok=True)

    with sync_playwright() as p:
        # ---- DESKTOP — fresh context per capture -----------------------
        # 1) Leaderboard default
        fresh_desktop_capture(p, out, label="leaderboard_desktop",
                              tab="Leaderboard")

        # 2) Player tab — default Embiid (no URL pre-select, default branch
        #    in app.py picks Embiid)
        fresh_desktop_capture(p, out, label="player_embiid_desktop",
                              tab="Player")

        # 3) Player tab — Klay (cool/negative)
        fresh_desktop_capture(p, out, label="player_klay_desktop",
                              url=f"{URL}/?hero_player=Klay+Thompson",
                              tab="Player")

        # 4) Player tab — Doncic (mid-pack)
        fresh_desktop_capture(p, out, label="player_luka_desktop",
                              url=f"{URL}/?hero_player=Luka+Don%C4%8Di%C4%87",
                              tab="Player")

        # 5) Methodology — heavy SQL (calibration bins 725k rows), needs longer settle
        fresh_desktop_capture(p, out, label="methodology_desktop",
                              tab="Methodology", settle=8.0)

        # 6) Empty leaderboard — push min-possessions slider beyond any
        #    player's season total so we get a clean "No matches" state.
        fresh_desktop_capture(p, out, label="leaderboard_empty_desktop",
                              url=f"{URL}/?min_poss=2000",
                              tab="Leaderboard", settle=2.0)

        # ---- MOBILE — fresh contexts ----------------------------------
        fresh_mobile_capture(p, out, label="leaderboard_mobile",
                             tab="Leaderboard")
        fresh_mobile_capture(p, out, label="player_mobile",
                             tab="Player")


if __name__ == "__main__":
    main()
