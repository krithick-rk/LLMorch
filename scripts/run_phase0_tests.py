#!/usr/bin/env python3
"""
LLMorch Phase 0 Test Suite Runner
Executes all foundational tests for Phase 0 validation.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    print("=" * 60)
    print("Executing LLMorch Phase 0 Unit Test Suite")
    print("=" * 60)
    test_dir = str(PROJECT_ROOT / "tests")
    res = pytest.main(["-v", test_dir])
    if res == 0:
        print("\n==> SUCCESS: ALL PHASE 0 UNIT TESTS PASSED!")
    else:
        print(f"\n==> FAILURE: Tests exited with code {res}")
    return res


if __name__ == "__main__":
    sys.exit(main())
