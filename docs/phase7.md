# LLMorch Phase 7: Repository Intelligence, Relevance Filtering & AnalysisUnits

See `PHASE7_IMPLEMENTATION_REPORT.md` for the full report, architecture diagram, and definition-of-done checklist.

## Quick Reference

### Pipeline
```
Repository → Snapshot → Classification → Secrets Quarantine → Symlink Safety
→ Build System Indexing → Symbol Extraction → Dependency Graph
→ Security Surface → AnalysisUnits → Relevance Ranking
→ Phase 6 Memory Retrieval → Scoped Agent Context
```

### CLI
```bash
python3 -m llmorch repo scan <repo-path>
python3 -m llmorch repo status <snapshot-id>
python3 -m llmorch repo units <snapshot-id>
python3 -m llmorch repo unit <unit-id>
python3 -m llmorch repo security-surface <unit-id>
python3 -m llmorch repo dependencies <unit-id>
python3 -m llmorch repo diff <snap-a> <snap-b>
```

### Key Principles
- **Repository Intelligence is deterministic infrastructure first** — LLMs interpret structured facts, not raw file dumps
- **Secrets are quarantined** — never sent to LLM or stored in global memory
- **External symlinks are blocked** — never followed beyond authorized root
- **AnalysisUnits represent real security boundaries** — not one-file-per-unit
- **Priority ≠ vulnerability** — high relevance score means investigation resource priority only
- **Context is scoped** — vendor/generated/secrets excluded by default; 1-hop expansion is audited
