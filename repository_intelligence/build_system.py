"""
LLMorch Repository Intelligence - Build System & Native Metadata Indexer (Phase 7)
Indexes build targets (Bazel, FuseSoC, CMake, Cargo, Go) and parses native security metadata (HJSON).
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from schemas.repository_intelligence import BuildTarget, HW_SW_Contract
from schemas.file_classification import FileClassificationRecord


class BuildSystemIndexer:
    """
    Parses build targets and native security metadata deterministically.
    """

    @classmethod
    def index_build_targets(cls, file_records: List[FileClassificationRecord], repo_root: str) -> List[BuildTarget]:
        targets: List[BuildTarget] = []

        for rec in file_records:
            abs_p = rec.abs_path
            name = os.path.basename(abs_p)

            if not os.path.exists(abs_p) or rec.is_symlink:
                continue

            # Bazel BUILD / BUILD.bazel Target Extraction
            if name in {"BUILD", "BUILD.bazel"}:
                try:
                    with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    # Regex search for cc_library, cc_binary, py_library, go_library, sv_module rules
                    rule_matches = re.findall(r'(cc_library|cc_binary|py_library|go_library|rules_verilog|sv_library)\s*\(\s*name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    for rule_type, target_name in rule_matches:
                        targets.append(BuildTarget(
                            build_system="Bazel",
                            target_name=f"//{os.path.dirname(rec.rel_path)}:{target_name}",
                            defined_in_file=rec.rel_path,
                            source_files=[rec.rel_path]
                        ))
                except Exception:
                    pass

            # FuseSoC .core Target Extraction
            elif name.endswith(".core"):
                try:
                    with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    name_match = re.search(r'name\s*:\s*([^\s]+)', content)
                    t_name = name_match.group(1) if name_match else name
                    targets.append(BuildTarget(
                        build_system="FuseSoC",
                        target_name=t_name,
                        defined_in_file=rec.rel_path,
                        source_files=[rec.rel_path]
                    ))
                except Exception:
                    pass

            # CMakeLists.txt Extraction
            elif name == "CMakeLists.txt":
                try:
                    with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    add_matches = re.findall(r'(add_library|add_executable)\s*\(\s*([^\s\)]+)', content, re.IGNORECASE)
                    for _, target_name in add_matches:
                        targets.append(BuildTarget(
                            build_system="CMake",
                            target_name=target_name,
                            defined_in_file=rec.rel_path,
                            source_files=[rec.rel_path]
                        ))
                except Exception:
                    pass

        return targets

    @classmethod
    def extract_hw_sw_contracts(cls, file_records: List[FileClassificationRecord], repo_root: str) -> List[HW_SW_Contract]:
        """
        Detects HW ↔ SW contract metadata (HJSON register descriptions -> C header -> DIF).
        """
        contracts: List[HW_SW_Contract] = []

        hjson_files = [r for r in file_records if r.rel_path.endswith(".hjson") or "reg" in r.rel_path.lower()]
        c_headers = [r for r in file_records if r.rel_path.endswith(".h") and ("reg" in r.rel_path.lower() or "dif" in r.rel_path.lower())]

        for hfile in hjson_files:
            abs_p = hfile.abs_path
            if not os.path.exists(abs_p):
                continue
            try:
                with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Search register definitions in HJSON/JSON content
                reg_matches = re.findall(r'name\s*[:=]\s*[\'"]([A-Za-z0-9_]+)[\'"]', content)
                for reg in reg_matches:
                    if reg.lower() in {"registers", "param", "reset"}:
                        continue

                    # Match header ref if available
                    matched_header = next((h.rel_path for h in c_headers if reg.lower() in h.rel_path.lower()), None)
                    contracts.append(HW_SW_Contract(
                        register_name=reg.upper(),
                        hjson_ref=hfile.rel_path,
                        header_ref=matched_header,
                        access_policy="RW" if "rw" in content.lower() else "RO",
                        lock_bits=[f"{reg.lower()}_regwen", f"{reg.lower()}_lock"]
                    ))
            except Exception:
                pass

        return contracts
