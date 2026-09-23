#!/usr/bin/env python3
"""
Antigravity Inline AI Fix Script
Resolves: "LS check error: [internal] certificate has expired"

Root cause: The bundled self-signed localhost certificate for the internal
Language Server expired on September 4, 2026. This script configures the local
HTTP/2 client in Antigravity to accept the internal language server connection
without rejecting on certificate expiration, restoring inline AI, autocomplete,
and code lenses.
"""

import sys
import os
import shutil
import argparse

TARGETS = [
    {
        "path": "/usr/share/antigravity/resources/app/out/main.js",
        "old": "nodeOptions:{ca:n}",
        "new": "nodeOptions:{ca:n,rejectUnauthorized:!1}",
    },
    {
        "path": "/usr/share/antigravity/resources/app/extensions/antigravity/dist/extension.js",
        "old": "nodeOptions:{ca:o.readFileSync(s.resolve(__dirname,r))}",
        "new": "nodeOptions:{ca:o.readFileSync(s.resolve(__dirname,r)),rejectUnauthorized:!1}",
    },
]


def check_status():
    all_patched = True
    all_unpatched = True
    for item in TARGETS:
        fpath = item["path"]
        if not os.path.exists(fpath):
            print(f"[ERROR] Target file not found: {fpath}")
            return False
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        is_patched = item["new"] in content
        is_unpatched = item["old"] in content
        print(f"File: {fpath}")
        print(f"  Patched:   {is_patched}")
        print(f"  Unpatched: {is_unpatched}")
        if not is_patched:
            all_patched = False
        if not is_unpatched:
            all_unpatched = False

    if all_patched:
        print("\n==> Status: Antigravity is ALREADY PATCHED. Inline AI fix is active.")
        return True
    elif all_unpatched:
        print("\n==> Status: Antigravity is UNPATCHED. Expired certificate error is present.")
        return False
    else:
        print("\n==> Status: Inconsistent state (partially patched).")
        return False


def apply_patch(dry_run=False):
    print(f"==> {'[DRY RUN] ' if dry_run else ''}Applying Antigravity Inline AI Patch...")
    for item in TARGETS:
        fpath = item["path"]
        if not os.path.exists(fpath):
            print(f"[ERROR] Target file not found: {fpath}")
            sys.exit(1)

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        if item["new"] in content:
            print(f"[OK] Already patched: {fpath}")
            continue

        if item["old"] not in content:
            print(f"[ERROR] Target pattern not found in {fpath}. File may have changed.")
            sys.exit(1)

        count = content.count(item["old"])
        if count != 1:
            print(f"[ERROR] Expected 1 occurrence of target pattern in {fpath}, found {count}.")
            sys.exit(1)

        new_content = content.replace(item["old"], item["new"])

        if dry_run:
            print(f"[DRY-RUN OK] Successfully verified patch for {fpath}")
            continue

        # Backup original
        bak_path = fpath + ".bak"
        if not os.path.exists(bak_path):
            shutil.copy2(fpath, bak_path)
            print(f"[BACKUP] Created {bak_path}")

        # Write patched file
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[PATCHED] Successfully patched {fpath}")

    if not dry_run:
        print("\n==> SUCCESS: All targets patched! Restart Antigravity to enable inline AI.")


def revert_patch():
    print("==> Reverting Antigravity Inline AI Patch...")
    for item in TARGETS:
        fpath = item["path"]
        bak_path = fpath + ".bak"
        if os.path.exists(bak_path):
            shutil.copy2(bak_path, fpath)
            print(f"[RESTORED] Restored {fpath} from backup.")
        else:
            # Fallback to replacing new with old
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            if item["new"] in content:
                content = content.replace(item["new"], item["old"])
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[REVERTED] Reverted patch in {fpath}")
            else:
                print(f"[SKIP] No patched pattern in {fpath}")


def main():
    parser = argparse.ArgumentParser(description="Fix Antigravity Inline AI certificate expiration")
    parser.add_argument("--check", action="store_true", help="Check patch status")
    parser.add_argument("--dry-run", action="store_true", help="Test patch matching without modifying files")
    parser.add_argument("--revert", action="store_true", help="Revert changes from backup")
    args = parser.parse_args()

    if args.check:
        check_status()
    elif args.revert:
        revert_patch()
    else:
        apply_patch(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
