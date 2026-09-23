# LLMorch — Agent Discovery Independence Specification

To prevent anchoring bias and false consensus during multi-agent vulnerability research:

1. **Independent Discovery Phase**:
   - Each agent receives an un-anchored prompt containing only task objectives and pre-check facts.
   - Live execution transcripts and candidate hypotheses are kept private to that agent's run.
2. **Correlation Boundary**:
   - Agent outputs are merged only AFTER both independent runs have finished.
3. **Audit Trail**:
   - `AGENT_SELECTED`, `PARALLEL_INVESTIGATION_STARTED`, `EVIDENCE_RECORDED`, and `CORRELATION_STARTED` events are recorded in SQLite to provide an append-only audit trail.
