# Global Intelligence Plane Architecture & Guide

The Global Intelligence Plane provides reusable, non-authoritative security research guidance across projects.

## Architecture

```text
AnalysisUnit / Target Context
             │
             ▼
Deterministic Structural & Semantic Matching
             │
             ▼
Global Intelligence Retrieval
  - Relevant Vulnerability Families
  - Applicable Security Invariants
  - Historical Strategy Outcomes
  - False Positive Distinguishers
  - Tool Evidence Guidance
             │
             ▼
     InvestigationContext
   (Non-Authoritative Guidance)
             │
             ▼
      Agent Planning
             │
             ▼
    Deterministic Tools
             │
             ▼
      Evidence Plane
             │
             ▼
        Validator
  (Sole Terminal Authority)
             │
             ▼
       Finding State
             │
             ▼
    Human Review Loop
             │
             ▼
     FeedbackRecord
             │
             ▼
  Controlled Promotion
             │
             ▼
Global Intelligence Update
```

## API Usage

```python
from history.database import DatabaseService
from intelligence.service import GlobalIntelligenceService
from schemas.global_intelligence import FeedbackRecord, FeedbackLabel

db = DatabaseService("history/llmorch.db")
service = GlobalIntelligenceService(db)

# 1. Synthesize non-authoritative guidance for an AnalysisUnit
guidance = service.get_guidance(
    analysis_unit_id="unit-123",
    context={"target_context": "dma mmio register lock", "indicators": ["dma", "privilege_check"]}
)

print(guidance.disclaimer)
# "GLOBAL INTELLIGENCE GUIDANCE IS NON-AUTHORITATIVE. Final finding validity is determined exclusively by the Validator."

# 2. Record first-class human feedback
feedback = FeedbackRecord(
    finding_id="find-456",
    project_id="proj-alpha",
    reviewer="senior_hwsec_analyst",
    label=FeedbackLabel.CONFIRMED,
    reason="Reproduced via Cocotb harness asserting bus master privilege leak"
)
service.record_feedback(feedback)
```
