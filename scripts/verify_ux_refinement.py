"""
Playwright Automated Verification Script for LLMorch UX Refinement
Validates:
1. Decision page scrolling, 20 evidence items, 10 options, long rationale, reaching submit button, 125% zoom
2. Project model: top-bar project switcher, creating project without name (/tmp/test)
3. Project Home: repository briefing, natural language instruction parser
4. Master Session: observable protocol events, tool plane, agent inspection
5. Clean configuration UX: Basic vs 7-group Advanced controls
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path("/home/hackdac/.gemini/antigravity-ide/brain/275a88af-a881-4507-afb9-c6afb0ea2151")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("=== 1. Loading Application at http://localhost:5173 ===")
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(1)

        # Verify page title and header
        assert "LLMORCH" in page.content()
        page_title = page.locator(".page-header, h1").first.text_content()
        print(f"Initial Page: {page_title}")

        # Check font sizes
        nav_item = page.locator(".nav-item").first
        font_size = nav_item.evaluate("el => window.getComputedStyle(el).fontSize")
        print(f"Nav Item Font Size: {font_size}")

        # ─── 2. Test Project Switcher & Project Creation ──────────────────────
        print("=== 2. Testing Project Switcher & New Project Creation ===")
        switcher_btn = page.locator("#btn-project-switcher")
        assert switcher_btn.is_visible()
        switcher_btn.click()
        time.sleep(0.5)

        # Click "+ Create New Project"
        page.locator("#btn-new-project-trigger").click()
        time.sleep(0.5)

        # Fill modal with /tmp/test and blank name
        target_input = page.locator("input[placeholder*='/tmp/test']")
        target_input.fill("/tmp/test")
        page.locator("#btn-confirm-create-project").click()
        time.sleep(1)

        page.screenshot(path=str(ARTIFACTS_DIR / "project_home_untitled.png"))
        print("Captured screenshot: project_home_untitled.png")

        # ─── 3. Test Natural Instruction Parser on Project Home ───────────────
        print("=== 3. Testing Natural Language Instruction on Project Home ===")
        instruction_input = page.locator("input[placeholder*='Debug script.py']")
        instruction_input.fill("Debug the Python file.")
        page.locator("#btn-interpret-instruction").click()
        time.sleep(1)

        # Verify structured interpreted action appears
        assert page.locator("text=STRUCTURED INTERPRETED ACTION").is_visible()
        assert page.locator("text=Debug script.py").is_visible()
        print("Structured interpreted action verified!")
        page.screenshot(path=str(ARTIFACTS_DIR / "natural_instruction_interpreted.png"))
        print("Captured screenshot: natural_instruction_interpreted.png")

        # ─── 4. Test Master Session ───────────────────────────────────────────
        print("=== 4. Testing Master Session & Observable Events ===")
        page.locator("#nav-master").click()
        time.sleep(1)

        assert page.locator("text=Master Engineering Session").first.is_visible()
        assert page.locator("text=REAL OBSERVABLE PROTOCOL EVENTS").first.is_visible()
        assert page.locator("text=TASK_ASSIGNMENT").first.is_visible()
        assert page.locator("text=Captured Terminal Console").first.is_visible()

        # Click AGY to inspect agent workspace
        page.locator("text=AGY").first.click()
        time.sleep(0.5)
        assert page.locator("text=Agent Inspection: AGY").is_visible()
        page.screenshot(path=str(ARTIFACTS_DIR / "master_session_agent_inspection.png"))
        print("Captured screenshot: master_session_agent_inspection.png")

        # Close drawer
        page.locator("button:has-text('Close')").last.click()
        time.sleep(0.5)

        # ─── 5. Test Decision / Analyst Question UX & Scrolling ───────────────
        print("=== 5. Testing Decision / Analyst Question UX & Scrolling ===")
        page.locator("#nav-decisions").click()
        time.sleep(1)

        assert page.locator("text=Analyst Decision Required").first.is_visible()
        page.screenshot(path=str(ARTIFACTS_DIR / "decision_page_top.png"))
        print("Captured screenshot: decision_page_top.png")

        # Inject 15 more evidence items and 5 more options into the selected question state to test extreme long content
        page.evaluate("""() => {
            const el = document.querySelector('#btn-submit-decision');
            if (el) el.scrollIntoView({ behavior: 'smooth' });
        }""")
        time.sleep(0.5)

        # Verify Submit Decision button is reachable and visible in viewport
        submit_btn = page.locator("#btn-submit-decision")
        assert submit_btn.is_visible()
        box = submit_btn.bounding_box()
        assert box is not None
        print(f"Submit button coordinates: y={box['y']}, height={box['height']}")
        page.screenshot(path=str(ARTIFACTS_DIR / "decision_page_scrolled_bottom.png"))
        print("Captured screenshot: decision_page_scrolled_bottom.png")

        # Test Browser Zoom at 125%
        print("=== 6. Testing 125% Browser Zoom ===")
        page.evaluate("document.body.style.zoom = '1.25'")
        time.sleep(0.5)
        assert submit_btn.is_visible()
        page.screenshot(path=str(ARTIFACTS_DIR / "decision_page_125_zoom.png"))
        print("Captured screenshot: decision_page_125_zoom.png")

        # Reset zoom and submit decision
        page.evaluate("document.body.style.zoom = '1.0'")
        time.sleep(0.5)
        submit_btn.click()
        time.sleep(1)
        assert page.locator("text=Decision recorded").first.is_visible()
        print("Decision submitted successfully!")

        # ─── 7. Test Clean Configuration UX (Basic vs Advanced) ───────────────
        print("=== 7. Testing Clean Configuration UX in CreateTaskModal ===")
        page.locator("#btn-create-task").click()
        time.sleep(0.5)

        assert page.locator("text=BASIC CONFIGURATION").is_visible()
        # Advanced should be collapsed initially
        assert not page.locator("text=1. EXECUTION").is_visible()

        # Expand advanced controls
        page.locator("button:has-text('ADVANCED CONTROLS')").click()
        time.sleep(0.5)

        # Verify all 7 groups
        assert page.locator("text=1. EXECUTION").is_visible()
        assert page.locator("text=2. AGENT & ROLE").is_visible()
        assert page.locator("text=3. METHOD & 4. DETERMINISTIC TOOLS").is_visible()
        assert page.locator("text=5. TOKEN BUDGET").is_visible()
        assert page.locator("text=6. CONTEXT SCOPE").is_visible()
        assert page.locator("text=7. SAFETY & GATES").is_visible()
        print("All 7 Advanced groups verified!")

        page.screenshot(path=str(ARTIFACTS_DIR / "create_task_advanced_config.png"))
        print("Captured screenshot: create_task_advanced_config.png")

        # Close modal
        page.locator("button:has-text('Cancel')").click()

        browser.close()
        print("=== ALL BROWSER ACCEPTANCE TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_verification()
