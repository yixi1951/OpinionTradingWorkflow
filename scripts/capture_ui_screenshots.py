"""Capture Streamlit dashboard screenshots for README / portfolio.

Usage (Streamlit must already be running):
    python scripts/capture_ui_screenshots.py
    python scripts/capture_ui_screenshots.py --url http://localhost:8502 --out docs/screenshots
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "screenshots"

TABS = [
    ("tab_picks", "实时选股"),
    ("tab_sentiment", "舆情分析"),
    ("tab_comments", "评论依据"),
    ("tab_eval", "回测评估"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture OpinionTrading UI tab screenshots")
    parser.add_argument("--url", default="http://localhost:8501", help="Streamlit base URL")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    parser.add_argument("--wait", type=float, default=3.0, help="Seconds after each tab click")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed. Run: pip install playwright && playwright install chromium")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(args.url, wait_until="networkidle", timeout=120_000)

        # Streamlit reruns can take a moment on first load
        page.wait_for_selector('[data-testid="stTabs"]', timeout=120_000)
        time.sleep(2)

        for slug, label in TABS:
            tab = page.get_by_role("tab", name=label)
            tab.click()
            time.sleep(args.wait)
            out_path = args.out / f"ui_{slug}.png"
            page.screenshot(path=str(out_path), full_page=True)
            print(f"Saved {out_path}")

        browser.close()

    print(f"\nDone — {len(TABS)} screenshots in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
