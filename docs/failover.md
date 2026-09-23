# LLMorch Failover Engine Specification

## Failover Architecture
The `FailoverEngine` (`scheduler/failover.py`) manages automatic recovery when an agent execution fails or becomes quota-exhausted.

### Core Guarantees
1. **Durable Lineage**: Every retry creates a new `Run` record linked to `parent_run_id`.
2. **Task Continuity**: `task_id` remains unchanged.
3. **Loop Prevention**: Agents previously attempted in the recovery chain are excluded from re-selection.
4. **Quota Protection**: Quota-exhausted agents are marked `QUOTA_LIMITED` and temporarily removed from dispatch consideration.
5. **Max Retries Capping**: Retry attempts are capped by `max_retries_per_task` (default: 2). Exceeding this limit transitions the task to `FAILED` with `RECOVERY_EXHAUSTED`.

### Event Audit Stream
- `AGENT_FAILURE_DETECTED`
- `AGENT_QUOTA_EXHAUSTED`
- `AGENT_MARKED_UNAVAILABLE`
- `AGENT_HEALTH_CHANGED`
- `CHECKPOINT_CREATED`
- `FAILOVER_STARTED`
- `REPLACEMENT_CANDIDATES_RESOLVED`
- `REPLACEMENT_AGENT_SELECTED`
- `TASK_REASSIGNED`
- `TASK_RESUMED`
- `RECOVERY_EXHAUSTED` / `RECOVERY_BLOCKED`
