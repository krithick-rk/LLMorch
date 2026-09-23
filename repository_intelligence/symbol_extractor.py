"""
LLMorch Repository Intelligence - Multi-Language Symbol Extractor (Phase 7)
Extracts program symbols, modules, functions, ports, and hardware constructs across C/C++, Go, Java, Python, and RTL.
"""

import os
import re
from typing import List, Dict, Any, Optional
from schemas.repository_intelligence import SymbolEntity
from schemas.file_classification import FileClassificationRecord


class SymbolExtractor:
    """
    Deterministic multi-language symbol & module extractor.
    Uses regex AST pattern matchers for C/C++, Go, Java, Python, and SystemVerilog/Verilog.
    """

    @classmethod
    def extract_symbols(cls, file_records: List[FileClassificationRecord], repo_root: str) -> List[SymbolEntity]:
        symbols: List[SymbolEntity] = []

        for rec in file_records:
            abs_p = rec.abs_path
            if rec.is_symlink or not os.path.exists(abs_p) or rec.size_bytes == 0 or rec.size_bytes > 500_000:
                continue

            lang = rec.language
            rel_p = rec.rel_path

            try:
                with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                content = "".join(lines)

                # 1. RTL (SystemVerilog / Verilog / SVA)
                if lang in {"systemverilog", "verilog", "sva"} or rel_p.endswith((".v", ".sv", ".svh", ".sva")):
                    # Module definitions
                    mod_matches = re.finditer(r'module\s+([A-Za-z0-9_]+)', content)
                    for m in mod_matches:
                        symbols.append(SymbolEntity(
                            name=m.group(1),
                            kind="module",
                            language="rtl",
                            file_path=rel_p,
                            line_start=content[:m.start()].count("\n") + 1,
                            line_end=content[:m.start()].count("\n") + 10
                        ))

                    # Ports & Signals
                    port_matches = re.finditer(r'(input|output|inout)\s+(?:logic|wire|reg)?\s*(?:\[[^\]]+\])?\s*([A-Za-z0-9_]+)', content)
                    for p in port_matches:
                        symbols.append(SymbolEntity(
                            name=p.group(2),
                            kind="port",
                            language="rtl",
                            file_path=rel_p,
                            line_start=content[:p.start()].count("\n") + 1,
                            line_end=content[:p.start()].count("\n") + 1,
                            metadata={"direction": p.group(1)}
                        ))

                    # Always blocks / FSMs
                    always_matches = re.finditer(r'always_(ff|comb|latch)\s*@?\s*(?:\([^\)]+\))?', content)
                    for a in always_matches:
                        symbols.append(SymbolEntity(
                            name=f"always_{a.group(1)}",
                            kind="always_block",
                            language="rtl",
                            file_path=rel_p,
                            line_start=content[:a.start()].count("\n") + 1,
                            line_end=content[:a.start()].count("\n") + 5
                        ))

                # 2. C / C++
                elif lang in {"c", "cpp"}:
                    # Functions
                    fn_matches = re.finditer(r'(?:[A-Za-z0-9_]+[\*\s]+)+([A-Za-z0-9_]+)\s*\([^\)]*\)\s*\{', content)
                    for fn in fn_matches:
                        name = fn.group(1)
                        if name not in {"if", "while", "for", "switch"}:
                            symbols.append(SymbolEntity(
                                name=name,
                                kind="function",
                                language=lang,
                                file_path=rel_p,
                                line_start=content[:fn.start()].count("\n") + 1,
                                line_end=content[:fn.start()].count("\n") + 15
                            ))
                    # Classes / Structs
                    class_matches = re.finditer(r'(?:class|struct)\s+([A-Za-z0-9_]+)', content)
                    for cl in class_matches:
                        symbols.append(SymbolEntity(
                            name=cl.group(1),
                            kind="class",
                            language=lang,
                            file_path=rel_p,
                            line_start=content[:cl.start()].count("\n") + 1,
                            line_end=content[:cl.start()].count("\n") + 25
                        ))
                    # Macros
                    macro_matches = re.finditer(r'#define\s+([A-Za-z0-9_]+)', content)
                    for mc in macro_matches:
                        symbols.append(SymbolEntity(
                            name=mc.group(1),
                            kind="macro",
                            language=lang,
                            file_path=rel_p,
                            line_start=content[:mc.start()].count("\n") + 1,
                            line_end=content[:mc.start()].count("\n") + 1
                        ))

                # 3. Go
                elif lang == "go":
                    fn_matches = re.finditer(r'func\s+(?:\([^\)]+\)\s+)?([A-Za-z0-9_]+)\s*\(', content)
                    for fn in fn_matches:
                        symbols.append(SymbolEntity(
                            name=fn.group(1),
                            kind="function",
                            language="go",
                            file_path=rel_p,
                            line_start=content[:fn.start()].count("\n") + 1,
                            line_end=content[:fn.start()].count("\n") + 15
                        ))
                    iface_matches = re.finditer(r'type\s+([A-Za-z0-9_]+)\s+interface\s*\{', content)
                    for ifc in iface_matches:
                        symbols.append(SymbolEntity(
                            name=ifc.group(1),
                            kind="interface",
                            language="go",
                            file_path=rel_p,
                            line_start=content[:ifc.start()].count("\n") + 1,
                            line_end=content[:ifc.start()].count("\n") + 10
                        ))

                # 4. Java
                elif lang == "java":
                    class_matches = re.finditer(r'(?:public|private|protected)?\s*(?:class|interface)\s+([A-Za-z0-9_]+)', content)
                    for cl in class_matches:
                        symbols.append(SymbolEntity(
                            name=cl.group(1),
                            kind="class",
                            language="java",
                            file_path=rel_p,
                            line_start=content[:cl.start()].count("\n") + 1,
                            line_end=content[:cl.start()].count("\n") + 20
                        ))
                    method_matches = re.finditer(r'(?:public|protected|private)?\s*(?:static\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z0-9_]+)\s*\([^\)]*\)\s*\{', content)
                    for meth in method_matches:
                        mname = meth.group(1)
                        if mname not in {"if", "while", "for", "switch"}:
                            symbols.append(SymbolEntity(
                                name=mname,
                                kind="method",
                                language="java",
                                file_path=rel_p,
                                line_start=content[:meth.start()].count("\n") + 1,
                                line_end=content[:meth.start()].count("\n") + 15
                            ))

                # 5. Python
                elif lang == "python":
                    class_matches = re.finditer(r'class\s+([A-Za-z0-9_]+)', content)
                    for cl in class_matches:
                        symbols.append(SymbolEntity(
                            name=cl.group(1),
                            kind="class",
                            language="python",
                            file_path=rel_p,
                            line_start=content[:cl.start()].count("\n") + 1,
                            line_end=content[:cl.start()].count("\n") + 20
                        ))
                    fn_matches = re.finditer(r'def\s+([A-Za-z0-9_]+)\s*\(', content)
                    for fn in fn_matches:
                        symbols.append(SymbolEntity(
                            name=fn.group(1),
                            kind="function",
                            language="python",
                            file_path=rel_p,
                            line_start=content[:fn.start()].count("\n") + 1,
                            line_end=content[:fn.start()].count("\n") + 10
                        ))

            except Exception:
                pass

        return symbols
