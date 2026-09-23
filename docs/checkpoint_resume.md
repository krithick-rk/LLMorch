# LLMorch Checkpoint & Resume Specification

## Checkpoint Model
Checkpoints snapshot task execution progress to allow model-independent resume.

### Schema Structure
```json
{
  "checkpoint_id": "chk-7f8a9b0c1d2e",
  "task_id": "task-001",
  "workflow_id": "wf-998877665544",
  "run_id": "run-112233445566",
  "completed_subtasks": ["intake", "precheck"],
  "remaining_subtasks": ["investigation", "validation"],
  "task_state": {"failed_agent": "agent-agy-01"},
  "artifact_refs": ["art-001"],
  "evidence_refs": ["ev-001"],
  "recovery_context": {
    "failed_agent_id": "agent-agy-01",
    "failure_code": "QUOTA_EXHAUSTED",
    "failure_reason": "API 429 Rate limit"
  },
  "is_valid": true,
  "created_at": "2026-09-23T08:30:00Z"
}
```

### Checkpoint Validation
Before resume, the checkpoint validity is checked (`is_valid == True`). If stale or corrupted, recovery is blocked (`RECOVERY_BLOCKED`).
