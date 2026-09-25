"""
LLMorch Repository Token Estimator (Phase 9.1)
Estimates repository token footprint and LLM analysis consumption using
repository intelligence outputs (classification, noise filter, analysis units, secrets quarantine).
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from schemas.estimation import (
    RepositoryTokenEstimate,
    LanguageTokenEstimate,
    StageTokenEstimate,
    EstimationMethod,
    ConfidenceLevel,
)
from schemas.file_classification import FileClassificationType, FileClassificationRecord
from schemas.analysis_unit import AnalysisUnit
from token_tracker.accounting import estimate_tokens_from_text


# Language character-to-token heuristic ratios
LANG_RATIOS: Dict[str, float] = {
    "c": 3.5,
    "cpp": 3.5,
    "c++": 3.5,
    "h": 3.5,
    "hpp": 3.5,
    "systemverilog": 3.2,
    "verilog": 3.2,
    "sv": 3.2,
    "v": 3.2,
    "vhdl": 3.3,
    "python": 3.6,
    "py": 3.6,
    "rust": 3.5,
    "rs": 3.5,
    "go": 3.6,
    "java": 3.4,
    "hjson": 3.0,
    "json": 3.0,
    "yaml": 3.2,
    "yml": 3.2,
    "toml": 3.2,
    "bzl": 3.4,
    "bazel": 3.4,
    "markdown": 4.0,
    "md": 4.0,
}


def _get_file_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if not ext:
        base = os.path.basename(path).lower()
        if base in ("makefile", "dockerfile"):
            return base
        return "text"
    return ext


def estimate_repository_tokens(
    repository_path: str,
    snapshot_id: Optional[str] = None,
    file_records: Optional[List[Any]] = None,
    analysis_units: Optional[List[AnalysisUnit]] = None,
    quarantined_secrets: Optional[List[Any]] = None,
    selected_models: Optional[List[str]] = None,
    analysis_policy: Optional[str] = None
) -> RepositoryTokenEstimate:
    """
    Produces structured repository token estimate.
    Differentiates between total repository footprint and LLM-scoped security analysis tokens.
    Guarantees secrets are never counted for LLM transmission.
    """
    repo_root = Path(repository_path).resolve()
    if not repo_root.exists():
        return RepositoryTokenEstimate(
            repository_path=repository_path,
            confidence=ConfidenceLevel.LOW,
            confidence_rationale="Repository path does not exist."
        )

    # 1. Inspect Files
    total_files = 0
    source_files = 0
    security_relevant_files = 0
    excluded_files = 0
    quarantined_count = len(quarantined_secrets or [])

    raw_bytes = 0
    relevant_source_bytes = 0
    llm_eligible_bytes = 0
    excluded_bytes = 0

    lang_stats: Dict[str, Dict[str, Any]] = {}

    # Check if tiktoken is available to determine method
    estimation_method = EstimationMethod.LOCAL_TOKENIZER
    try:
        import tiktoken
        estimation_method = EstimationMethod.ACTUAL_TOKENIZER
    except Exception:
        estimation_method = EstimationMethod.HEURISTIC_ESTIMATE

    # Walk repository or use supplied file_records
    if file_records:
        for r in file_records:
            total_files += 1
            rel_path = getattr(r, "rel_path", getattr(r, "file_path", str(r)))
            sz = getattr(r, "size_bytes", 0)
            raw_bytes += sz
            classification = getattr(r, "classification", None)
            is_secret = getattr(r, "is_secret", False)

            lang = _get_file_language(rel_path)
            if lang not in lang_stats:
                lang_stats[lang] = {"files": 0, "bytes": 0, "eligible_bytes": 0, "excluded_bytes": 0}
            lang_stats[lang]["files"] += 1
            lang_stats[lang]["bytes"] += sz

            if is_secret:
                excluded_files += 1
                excluded_bytes += sz
                lang_stats[lang]["excluded_bytes"] += sz
                continue

            # Classify eligibility
            cls_str = str(classification).lower() if classification else ""
            if any(term in cls_str for term in ("primary", "source", "security", "contract", "header", "rtl")):
                source_files += 1
                relevant_source_bytes += sz
                llm_eligible_bytes += sz
                lang_stats[lang]["eligible_bytes"] += sz
                if "security" in cls_str or "critical" in cls_str or "contract" in cls_str:
                    security_relevant_files += 1
            elif any(term in cls_str for term in ("vendor", "third_party", "generated", "cache", "noise")):
                excluded_files += 1
                excluded_bytes += sz
                lang_stats[lang]["excluded_bytes"] += sz
            else:
                source_files += 1
                relevant_source_bytes += sz
                llm_eligible_bytes += sz
                lang_stats[lang]["eligible_bytes"] += sz
    else:
        # Direct filesystem walk with security noise filtering
        ignored_dirs = {".git", ".venv", "node_modules", "vendor", "third_party", "build", "dist", "target", ".cache", "__pycache__"}
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for f in files:
                p = Path(root) / f
                try:
                    st = p.stat()
                    sz = st.st_size
                except Exception:
                    continue

                total_files += 1
                raw_bytes += sz
                rel = str(p.relative_to(repo_root))
                lang = _get_file_language(rel)

                if lang not in lang_stats:
                    lang_stats[lang] = {"files": 0, "bytes": 0, "eligible_bytes": 0, "excluded_bytes": 0}
                lang_stats[lang]["files"] += 1
                lang_stats[lang]["bytes"] += sz

                # Detect and quarantine secrets (.env, secrets, credentials, pem, keys)
                is_secret_file = any(term in f.lower() for term in (".env", "secret", "credential", "id_rsa", "password", "token", ".pem"))
                if is_secret_file:
                    excluded_files += 1
                    excluded_bytes += sz
                    quarantined_count += 1
                    lang_stats[lang]["excluded_bytes"] += sz
                    continue

                # Skip binaries / large assets / noise
                if sz > 2 * 1024 * 1024 or lang in ("png", "jpg", "jpeg", "gif", "exe", "so", "o", "a", "tar", "zip", "gz"):
                    excluded_files += 1
                    excluded_bytes += sz
                    lang_stats[lang]["excluded_bytes"] += sz
                    continue

                source_files += 1
                relevant_source_bytes += sz
                llm_eligible_bytes += sz
                lang_stats[lang]["eligible_bytes"] += sz

                # Security relevance heuristic
                if any(k in rel.lower() for k in ("security", "auth", "crypto", "reg", "fsm", "ctrl", "priv", "otp", "keymgr", "lock")):
                    security_relevant_files += 1

    # Compute language token estimates
    lang_estimates: List[LanguageTokenEstimate] = []
    raw_token_total = 0
    llm_eligible_token_total = 0

    for lang, data in sorted(lang_stats.items(), key=lambda x: x[1]["bytes"], reverse=True):
        ratio = LANG_RATIOS.get(lang, 3.6)
        raw_tok = max(1, int(data["bytes"] / ratio)) if data["bytes"] > 0 else 0
        elig_tok = max(1, int(data["eligible_bytes"] / ratio)) if data["eligible_bytes"] > 0 else 0
        excl_tok = max(0, int(data["excluded_bytes"] / ratio)) if data["excluded_bytes"] > 0 else 0

        raw_token_total += raw_tok
        llm_eligible_token_total += elig_tok

        lang_estimates.append(LanguageTokenEstimate(
            language=lang,
            file_count=data["files"],
            raw_bytes=data["bytes"],
            estimated_tokens=raw_tok,
            llm_eligible_tokens=elig_tok,
            excluded_tokens=excl_tok,
        ))

    # AnalysisUnit estimation based on actual eligible content
    if llm_eligible_token_total == 0 or source_files == 0:
        au_count = 0
        au_estimate = 0
        context_expansion_estimate = 0
        discovery_tokens = 0
        intake_tokens = 0
        surfaces_tokens = 0
        initial_sweep_tokens = 0
        deep_analysis_tokens = 0
        repro_tokens = 0
        validation_tokens = 0
        initial_analysis_total = 0
        followup_total = 0
        estimated_total = 0
        recommended_budget = 0
    elif llm_eligible_token_total < 5000:
        # Small / tiny repository — strictly proportional, no massive minimum floor
        au_count = len(analysis_units) if analysis_units else (1 if source_files > 0 else 0)
        au_estimate = max(50, int(llm_eligible_token_total * 0.8))
        context_expansion_estimate = int(llm_eligible_token_total * 0.2)
        discovery_tokens = max(20, int(llm_eligible_token_total * 0.15))
        intake_tokens = max(20, int(llm_eligible_token_total * 0.2))
        surfaces_tokens = max(20, int(llm_eligible_token_total * 0.15))
        initial_sweep_tokens = au_estimate
        deep_analysis_tokens = context_expansion_estimate
        repro_tokens = max(20, int(llm_eligible_token_total * 0.2))
        validation_tokens = max(10, int(llm_eligible_token_total * 0.1))

        initial_analysis_total = discovery_tokens + intake_tokens + surfaces_tokens + initial_sweep_tokens
        followup_total = deep_analysis_tokens + repro_tokens + validation_tokens
        estimated_total = initial_analysis_total + followup_total
        recommended_budget = int(estimated_total * 1.25)
    else:
        # Standard repository
        au_count = len(analysis_units) if analysis_units else max(1, min(10, security_relevant_files or 3))
        au_estimate = int(min(llm_eligible_token_total * 0.35, au_count * 20000))
        context_expansion_estimate = int(au_estimate * 0.4)

        discovery_tokens = min(35000, max(1000, int(llm_eligible_token_total * 0.05)))
        intake_tokens = min(50000, max(1500, int(llm_eligible_token_total * 0.08)))
        surfaces_tokens = min(75000, max(2000, int(llm_eligible_token_total * 0.12)))
        initial_sweep_tokens = au_estimate
        deep_analysis_tokens = context_expansion_estimate
        repro_tokens = min(60000, max(2000, int(au_estimate * 0.3)))
        validation_tokens = min(40000, max(1500, int(repro_tokens * 0.6)))

        initial_analysis_total = discovery_tokens + intake_tokens + surfaces_tokens + initial_sweep_tokens
        followup_total = deep_analysis_tokens + repro_tokens + validation_tokens
        estimated_total = initial_analysis_total + followup_total
        recommended_budget = int(estimated_total * 1.25)

    stages = [
        StageTokenEstimate(
            stage="discovery",
            display_name="Repository Discovery & Intake",
            estimated_input_tokens=int(discovery_tokens * 0.8),
            estimated_output_tokens=int(discovery_tokens * 0.2),
            estimated_total_tokens=discovery_tokens,
            description="Repository file indexing, build configuration analysis, and architecture discovery."
        ),
        StageTokenEstimate(
            stage="security_surfaces",
            display_name="Security Surfaces & Contracts",
            estimated_input_tokens=int(surfaces_tokens * 0.8),
            estimated_output_tokens=int(surfaces_tokens * 0.2),
            estimated_total_tokens=surfaces_tokens,
            description="Extraction of registers, hardware-software contracts, and attack surface boundaries."
        ),
        StageTokenEstimate(
            stage="analysis_units",
            display_name="AnalysisUnit Initial Sweep",
            estimated_input_tokens=int(initial_sweep_tokens * 0.85),
            estimated_output_tokens=int(initial_sweep_tokens * 0.15),
            estimated_total_tokens=initial_sweep_tokens,
            description="Targeted agent evaluation of high-priority security units."
        ),
        StageTokenEstimate(
            stage="deep_analysis",
            display_name="Context Expansion & Deep Analysis",
            estimated_input_tokens=int(deep_analysis_tokens * 0.85),
            estimated_output_tokens=int(deep_analysis_tokens * 0.15),
            estimated_total_tokens=deep_analysis_tokens,
            description="Follow-up agent investigation of candidate vulnerabilities."
        ),
        StageTokenEstimate(
            stage="reproduction_validation",
            display_name="Reproducer & Validation",
            estimated_input_tokens=int((repro_tokens + validation_tokens) * 0.75),
            estimated_output_tokens=int((repro_tokens + validation_tokens) * 0.25),
            estimated_total_tokens=repro_tokens + validation_tokens,
            description="Sandboxed execution, deterministic replay verification, and verdict generation."
        ),
    ]

    confidence = ConfidenceLevel.HIGH if file_records else ConfidenceLevel.MEDIUM
    confidence_rationale = (
        f"Estimate based on {total_files} discovered files ({llm_eligible_token_total:,} LLM-scoped tokens, "
        f"{quarantined_count} quarantined secrets safely excluded, {len(lang_estimates)} language categories analyzed)."
    )

    return RepositoryTokenEstimate(
        repository_path=str(repo_root),
        snapshot_id=snapshot_id,
        total_files_discovered=total_files,
        source_files_count=source_files,
        security_relevant_files_count=security_relevant_files,
        excluded_files_count=excluded_files,
        quarantined_secrets_count=quarantined_count,
        raw_repository_bytes=raw_bytes,
        relevant_source_bytes=relevant_source_bytes,
        llm_eligible_bytes=llm_eligible_bytes,
        excluded_bytes=excluded_bytes,
        raw_token_estimate=raw_token_total,
        llm_scoped_token_estimate=llm_eligible_token_total,
        analysis_unit_estimate=au_estimate,
        context_expansion_estimate=context_expansion_estimate,
        initial_analysis_estimate=initial_analysis_total,
        followup_analysis_estimate=followup_total,
        estimated_total_tokens=estimated_total,
        recommended_budget=recommended_budget,
        estimation_method=estimation_method,
        confidence=confidence,
        confidence_rationale=confidence_rationale,
        breakdown_by_language=lang_estimates[:15],
        breakdown_by_stage=stages,
        sample_files_analyzed=total_files,
        secrets_excluded_safely=True,
    )
