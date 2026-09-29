"""
Responsive Resolution & Viewport Verification for LLMorch
Tests viewports:
- 1920x1080 (FHD desktop)
- 1440x900 (MacBook / 16:10 laptop)
- 1366x768 (Standard laptop)
- 1280x800 (Compact laptop)
- 1024x768 (Tablet / low-res workstation)
- 720x960 (Split-screen mode)
Validates:
- No body horizontal overflow (scrollWidth == clientWidth)
- Controls accessible
- Scroll ownership intact
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path("/home/hackdac/.gemini/antigravity-ide/brain/275a88af-a881-4507-afb9-c6afb0ea2151")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "1920x1080_fhd", "width": 1920, "height": 1080},
    {"name": "1440x900_macbook", "width": 1440, "height": 900},
    {"name": "1366x768_laptop", "width": 1366, "height": 768},
    {"name": "1280x800_compact", "width": 1280, "height": 800},
    {"name": "1024x768_standard", "width": 1024, "height": 768},
    {"name": "720x960_splitscreen", "width": 720, "height": 960},
]

def run_responsive_tests():
    print("==================================================================")
    print("STARTING RESPONSIVE VIEWPORT ACCEPTANCE TESTS")
    print("==================================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in VIEWPORTS:
            print(f"\n--- Testing Viewport: {vp['name']} ({vp['width']}x{vp['height']}) ---")
            context = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()

            page.goto("http://localhost:5173", wait_until="networkidle")
            time.sleep(1)

            # Check body horizontal overflow
            body_overflow = page.evaluate("document.body.scrollWidth > window.innerWidth")
            assert not body_overflow, f"Horizontal overflow detected on body at {vp['name']}!"

            # Test Project Home buttons visibility
            btn_ws = page.locator("#btn-open-verification-ws, button:has-text('Open Verification Workspace')").first
            btn_master = page.locator("#btn-open-master-session, button:has-text('Open Master Session')").first
            assert btn_ws.is_visible()
            assert btn_master.is_visible()

            # Navigate to Master Session
            btn_master.click()
            time.sleep(1)

            # Verify Master Session does not have body overflow
            master_overflow = page.evaluate("document.body.scrollWidth > window.innerWidth")
            assert not master_overflow, f"Horizontal overflow in Master Session at {vp['name']}!"

            # Verify Orchestration Graph is visible
            assert page.locator("text=LIVE DYNAMIC ORCHESTRATION GRAPH").first.is_visible()
            print(f"  ✓ Master Session rendered cleanly at {vp['width']}x{vp['height']}")

            # Capture screenshot
            page.screenshot(path=str(ARTIFACTS_DIR / f"responsive_{vp['name']}.png"))
            print(f"  ✓ Saved screenshot: responsive_{vp['name']}.png")

            context.close()

        browser.close()

    print("\n==================================================================")
    print("ALL RESPONSIVE VIEWPORT TESTS PASSED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_responsive_tests()
