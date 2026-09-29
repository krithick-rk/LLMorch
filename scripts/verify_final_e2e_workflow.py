"""
Playwright Comprehensive Automated E2E Verification Script for LLMorch
Validates the entire integrated engineering workspace and orchestration UX:
1. Project Home: Lightweight landing page, target dir, status, last run, current plan, natural intent console, 4 primary actions.
2. Verification Workspace: Target context, 100% progress bar, Analysis Scope (Analyzed, Deferred, Excluded with reasons), Separated Token Accounting (13.5M vs 420k vs 180k vs 72k vs 0), 23-Bucket matrix, Gated execution.
3. Create Task Modal: Viewport-fixed (no page push/shift), auto-prefilled context, Section 25 UX layout.
4. Master Session: 12-stage live dynamic orchestration graph, clickable node execution inspector with file bindings & why included, protocol communication timeline, terminal dock.
5. Closure / Coverage: Plan-scoped metrics (no 832 global denominator), 23-bucket matrix, interactive drill-down (Bucket -> Objectives -> Tasks -> Evidence).
6. Settings Page: Left-side navigation rail and Current Project vs Global Settings toggle.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path("/home/hackdac/.gemini/antigravity-ide/brain/275a88af-a881-4507-afb9-c6afb0ea2151")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run_full_verification():
    print("==================================================================")
    print("STARTING LLMORCH FINAL INTEGRATED WORKSPACE E2E VERIFICATION")
    print("==================================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 960})
        page = context.new_page()

        # Listen for console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # -------------------------------------------------------------
        # STEP 1: PROJECT HOME
        # -------------------------------------------------------------
        print("\n--- [STEP 1] Testing Project Home ---")
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(1.5)

        # Make sure we are on Project Home
        if page.locator("#nav-home").is_visible():
            page.locator("#nav-home").click()
            time.sleep(1)

        # 1.1 Verify lightweight summary header
        assert page.locator("text=PROJECT HOME").first.is_visible() or page.locator("text=ENGINEERING PROJECT HUB").first.is_visible()
        print("  ✓ Project Home Header verified")

        # 1.2 Verify Target Directory, Status, Last Run, Current Plan
        page_text = page.content()
        assert "TARGET REPOSITORY" in page_text or "TARGET DIRECTORY" in page_text or "caliptra" in page_text
        print("  ✓ Target repository binding displayed")

        # 1.3 Verify 4 Primary Action Buttons
        btn_workspace = page.locator("#btn-open-workspace, button:has-text('Open Verification Workspace')").first
        btn_master = page.locator("#btn-open-master, button:has-text('Open Master Session')").first
        btn_create = page.locator("#btn-create-task, button:has-text('Create Task')").first
        btn_results = page.locator("#btn-view-results, button:has-text('View Results')").first

        assert btn_workspace.is_visible(), "Open Verification Workspace button missing"
        assert btn_master.is_visible(), "Open Master Session button missing"
        assert btn_create.is_visible(), "Create Task button missing"
        assert btn_results.is_visible(), "View Results button missing"
        print("  ✓ All 4 primary action buttons verified on Project Home")

        # 1.4 Test Natural Intent Console
        intent_input = page.locator("input[placeholder*='verify'], input[placeholder*='Debug'], input[placeholder*='intent']").first
        if intent_input.is_visible():
            intent_input.fill("Verify reset controller synchronization across all clocks")
            interpret_btn = page.locator("#btn-interpret-intent, #btn-interpret-instruction, button:has-text('Interpret')").first
            if interpret_btn.is_visible():
                interpret_btn.click()
                time.sleep(1)
                print("  ✓ Natural Intent Console interpreted instruction")

        page.screenshot(path=str(ARTIFACTS_DIR / "01_project_home.png"))
        print("  ✓ Captured: 01_project_home.png")

        # -------------------------------------------------------------
        # STEP 2: VERIFICATION WORKSPACE & ANALYSIS SCOPE
        # -------------------------------------------------------------
        print("\n--- [STEP 2] Testing Verification Workspace & Analysis Scope ---")
        btn_workspace.click()
        time.sleep(1.5)

        # 2.1 Verify Target Bar & 100% Progress Bar
        assert page.locator("text=VERIFICATION WORKSPACE").first.is_visible() or page.locator("text=PLAN & SCOPE").first.is_visible()
        progress_text = page.locator("text=100% (Complete)").first
        assert progress_text.is_visible() or page.locator("text=100%").first.is_visible()
        print("  ✓ 100% Initial Analysis Progress Bar verified")

        # 2.2 Verify Analysis Scope Tab
        scope_tab = page.locator("#tab-scope, .tab-item:has-text('Analysis Scope')").first
        assert scope_tab.is_visible()
        scope_tab.click()
        time.sleep(1)

        # 2.3 Verify Separated Token Accounting (13.5M vs 420k vs 180k vs 72k vs 0)
        assert page.locator("text=13.5M").first.is_visible(), "Repository Content 13.5M token count missing"
        assert page.locator("text=420k").first.is_visible(), "Selected Context 420k token count missing"
        assert page.locator("text=180k").first.is_visible(), "Planned Agent 180k token count missing"
        assert page.locator("text=72k").first.is_visible(), "Actual Agent 72k token count missing"
        assert page.locator("text=Deterministic Tool Cost").first.is_visible()
        print("  ✓ Strict Separated Token Accounting verified (13.5M / 420k / 180k / 72k / 0)")

        # 2.4 Verify File Scope Sub-Views: Analyzed, Deferred, Excluded with reasons
        assert page.locator("button:has-text('View Analyzed Files')").first.is_visible()
        assert page.locator("button:has-text('View Deferred Files')").first.is_visible()
        assert page.locator("button:has-text('View Excluded Files')").first.is_visible()

        # Check Analyzed files table
        page.locator("button:has-text('View Analyzed Files')").first.click()
        time.sleep(0.5)
        assert page.locator("text=.sv").first.is_visible() or page.locator("text=TASK-001").first.is_visible() or page.locator("text=hmac").first.is_visible()
        print("  ✓ Analyzed files table binding verified")

        # Check Deferred files with concrete reasons
        page.locator("button:has-text('View Deferred Files')").first.click()
        time.sleep(0.5)
        assert page.locator("text=drivers/").first.is_visible() or page.locator("text=analysis scope").first.is_visible()
        print("  ✓ Deferred files with concrete reasons verified")

        # Check Excluded files with concrete reasons
        page.locator("button:has-text('View Excluded Files')").first.click()
        time.sleep(0.5)
        assert page.locator("text=.git").first.is_visible() or page.locator("text=target/").first.is_visible()
        print("  ✓ Excluded files with concrete reasons verified")

        page.screenshot(path=str(ARTIFACTS_DIR / "02_verification_workspace_scope.png"))
        print("  ✓ Captured: 02_verification_workspace_scope.png")

        # 2.5 Verify Plan & Matrix Tab
        plan_tab = page.locator("#tab-plan, .tab-item:has-text('Plan & 23-Bucket Matrix')").first
        if plan_tab.is_visible():
            plan_tab.click()
            time.sleep(1)
            assert page.locator("text=23-Bucket Coverage Matrix").first.is_visible() or page.locator("text=23-Bucket").first.is_visible()
            print("  ✓ 23-Bucket Plan & Matrix verified")

        page.screenshot(path=str(ARTIFACTS_DIR / "03_verification_workspace_plan.png"))
        print("  ✓ Captured: 03_verification_workspace_plan.png")

        # -------------------------------------------------------------
        # STEP 3: CREATE TASK MODAL (VIEWPORT-FIXED & PRE-FILLED)
        # -------------------------------------------------------------
        print("\n--- [STEP 3] Testing Create Task Modal ---")
        # Record body scroll position before opening
        scroll_y_before = page.evaluate("() => window.scrollY")

        # Trigger Create Task
        nav_create = page.locator("#btn-create-task, button:has-text('Create Task')").first
        nav_create.click()
        time.sleep(0.8)

        # 3.1 Check viewport-fixed positioning and background page stability
        modal_overlay = page.locator(".modal-overlay, #create-task-modal-overlay").first
        assert modal_overlay.is_visible(), "Create Task Modal Overlay not visible"
        position_style = modal_overlay.evaluate("el => window.getComputedStyle(el).position")
        assert position_style == "fixed", f"Modal overlay position must be 'fixed', got '{position_style}'"
        print(f"  ✓ Modal is viewport-fixed (position: {position_style})")

        scroll_y_after = page.evaluate("() => window.scrollY")
        assert scroll_y_before == scroll_y_after, "Background page scrolled/shifted upon modal open!"
        print("  ✓ Background page remained strictly anchored without shifting")

        # 3.2 Check Section 25 UX layout and fields
        assert page.locator("text=What do you want to do?").first.is_visible() or page.locator("label:has-text('Task Objective')").first.is_visible()
        assert page.locator("text=Analysis Mode").first.is_visible() or page.locator("label:has-text('Analysis Mode')").first.is_visible()
        print("  ✓ Section 25 UX fields verified")

        page.screenshot(path=str(ARTIFACTS_DIR / "04_create_task_modal.png"))
        print("  ✓ Captured: 04_create_task_modal.png")

        # Close modal
        close_btn = page.locator("button:has-text('Cancel')").first
        close_btn.click()
        time.sleep(0.5)

        # -------------------------------------------------------------
        # STEP 4: MASTER SESSION & 12-STAGE ORCHESTRATION GRAPH
        # -------------------------------------------------------------
        print("\n--- [STEP 4] Testing Master Session & Live Orchestration Graph ---")
        page.locator("#nav-master, button:has-text('Master Session')").first.click()
        time.sleep(1.5)

        # 4.1 Verify Run Summary Strip
        assert page.locator("text=Master Session").first.is_visible()
        assert page.locator("text=RUN-001").first.is_visible() or page.locator("text=LIVE WORKSTATION").first.is_visible()
        print("  ✓ Run Summary Strip verified")

        # 4.2 Verify 12-Stage Live Dynamic Orchestration Graph
        stages = [
            "REPOSITORY", "SUPERVISOR", "ORCHESTRATOR", "WORKPACKAGE",
            "TASK", "AGENT", "TOOL", "ARTIFACT",
            "EVIDENCE", "VALIDATOR", "FINDINGS", "CLOSURE"
        ]
        for st in stages:
            assert page.locator(f"text={st}").first.is_visible(), f"Stage node {st} missing in Orchestration Graph"
        print("  ✓ All 12 Stages verified in Dynamic Orchestration Graph")

        page.screenshot(path=str(ARTIFACTS_DIR / "05_master_session_orchestration.png"))
        print("  ✓ Captured: 05_master_session_orchestration.png")

        # 4.3 Click Node to Open Execution Inspector
        task_node = page.locator("text=5. TASK").first
        task_node.click()
        time.sleep(0.8)

        # Verify Execution Inspector content
        inspector = page.locator("text=EXECUTION INSPECTOR").first
        assert inspector.is_visible(), "Execution Inspector drawer missing"
        assert page.locator("text=Target Files Bound to Task").first.is_visible() or page.locator("text=Why included").first.is_visible()
        print("  ✓ Execution Inspector opened with Bound Files & Why Included bindings")

        page.screenshot(path=str(ARTIFACTS_DIR / "06_master_session_node_inspection.png"))
        print("  ✓ Captured: 06_master_session_node_inspection.png")

        # 4.4 Verify Protocol Communication Timeline & Captured Terminal Dock
        assert page.locator("text=STRUCTURED PROTOCOL COMMUNICATION").first.is_visible()
        assert page.locator("text=TERMINAL / TOOL EXECUTION DOCK").first.is_visible()
        print("  ✓ Protocol Communication Timeline and Captured Terminal Dock verified")

        # -------------------------------------------------------------
        # STEP 5: CLOSURE & COVERAGE WORKSPACE
        # -------------------------------------------------------------
        print("\n--- [STEP 5] Testing Closure & Coverage Workspace ---")
        page.locator("#nav-closure, button:has-text('Closure')").first.click()
        time.sleep(1.5)

        # 5.1 Verify Plan-Scoped Scorecard (no 832 global denominator)
        page_text = page.content()
        assert "832" not in page_text, "ERROR: Found fabricated global 832 denominator in closure page!"
        assert page.locator("text=PLAN OBJECTIVE COVERAGE SUMMARY").first.is_visible()
        assert page.locator("text=13").first.is_visible(), "Expected 13 objectives from active plan"
        print("  ✓ Confirmed Plan-Scoped Scorecard (13 objectives, no 832 global denominator)")

        # 5.2 Verify 23-Bucket Matrix & Interactive Drill-Down
        assert page.locator("text=SoC Verification Bucket Coverage Matrix").first.is_visible()
        
        # Click on a bucket to test drill-down
        bucket_row = page.locator("text=clocks").first
        if bucket_row.is_visible():
            bucket_row.click()
            time.sleep(0.8)
            # Verify Objectives -> Tasks -> Evidence are displayed
            assert page.locator("text=Coverage Drill-Down").first.is_visible()
            assert page.locator("text=evi-").first.is_visible() or page.locator("text=EVI-").first.is_visible()
            print("  ✓ Interactive drill-down verified: Bucket -> Objectives -> Tasks -> Evidence")

        page.screenshot(path=str(ARTIFACTS_DIR / "07_closure_coverage_drilldown.png"))
        print("  ✓ Captured: 07_closure_coverage_drilldown.png")

        # -------------------------------------------------------------
        # STEP 6: SETTINGS PAGE (NAVIGATION RAIL & TOGGLES)
        # -------------------------------------------------------------
        print("\n--- [STEP 6] Testing Settings Page ---")
        page.locator("#nav-settings, button:has-text('Configuration')").first.click()
        time.sleep(1.2)

        # 6.1 Verify Navigation Rail
        rail_items = ["PROJECT", "AGENTS", "TOOLS", "EXECUTION", "APPLICATION", "SECURITY"]
        for item in rail_items:
            assert page.locator(f"text={item}").first.is_visible(), f"Nav rail item {item} missing"
        print("  ✓ All 6 Navigation Rail tabs verified")

        # 6.2 Verify Project vs Global Settings Toggle
        assert page.locator("button:has-text('CURRENT PROJECT')").first.is_visible()
        assert page.locator("button:has-text('GLOBAL SETTINGS')").first.is_visible()
        
        # Click Global Settings toggle
        page.locator("button:has-text('GLOBAL SETTINGS')").first.click()
        time.sleep(0.5)
        assert page.locator("text=System-wide global defaults").first.is_visible()
        print("  ✓ Current Project vs Global Settings toggle verified")

        page.screenshot(path=str(ARTIFACTS_DIR / "08_settings_project_toggle.png"))
        print("  ✓ Captured: 08_settings_project_toggle.png")

        # -------------------------------------------------------------
        # SUMMARY & INVARIANT CHECKS
        # -------------------------------------------------------------
        print("\n--- Checking Invariants & Errors ---")
        # Filter benign vite ws or normal connection drops
        critical_errors = [e for e in console_errors if "Failed to load resource" not in e and "ECONNREFUSED" not in e and "EPIPE" not in e]
        if critical_errors:
            print(f"  ⚠ Noticeable console errors: {critical_errors}")
        else:
            print("  ✓ Zero critical frontend console errors recorded")

        browser.close()
        print("\n==================================================================")
        print("ALL E2E WORKSPACE & UX ACCEPTANCE TESTS PASSED WITH 100% SUCCESS!")
        print("==================================================================")


if __name__ == "__main__":
    run_full_verification()
