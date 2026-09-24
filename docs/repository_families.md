# Repository Family Abstraction

LLMorch avoids scattered `if/elif` branching across orchestration logic by encapsulating repository-specific layout, build system, register metadata, and HW-SW contract discovery behind the `RepositoryFamilyAdapter` abstraction.

## Supported Families
* `OpenTitanFamilyAdapter`: FuseSoC, HJSON register definitions, Bazel/Meson, C DIFs.
* `CaliptraFamilyAdapter`: Cargo xtask, SystemRDL registers, Rust bare-metal firmware, Mailbox & SoC registers.
* `GenericFallbackAdapter`: Graceful fallback for standard software repositories.

## Detection Pipeline
```python
from pathlib import Path
from repository_intelligence.family import detect_repository_family

repo_path = Path("/path/to/repo")
family_type, adapter = detect_repository_family(repo_path)

# Unified API without branching:
contracts = adapter.discover_hw_sw_contracts(repo_path)
surface = adapter.build_security_surface(repo_path)
units = adapter.construct_analysis_units(repo_path)
backends = adapter.discover_validation_backends(repo_path)
```
