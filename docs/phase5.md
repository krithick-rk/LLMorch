# LLMorch Phase 5: Failover, Quota Awareness, Checkpointing and Model-Independent Resume

## 1. Overview
Phase 5 implements a durable, model-independent failover and checkpoint recovery engine for LLMorch.
When any executing agent encounters an interruption—such as process crash, timeout, quota exhaustion, auth failure, or adapter error—the framework automatically captures an immutable structured checkpoint, updates agent health state in the registry, filters out previously failed agents (preventing infinite loops), selects an eligible replacement agent via the Strategy Engine, spawns a new linked `Run` record (preserving `task_id` stability), and resumes investigation execution without losing prior state or work.

---

## 2. Architectural Principles
1. **Durable State vs Conversation Transcript**:
   The LLM conversation transcript is NOT the source of truth. Structured tasks, runs, checkpoints, artifacts, evidence, and repository snapshots represent the authoritative state.
2. **Stable Task Identity**:
   Task identity (`task_id`) remains constant across failover attempts. Each attempt creates a new `Run` (`run_id`) linked to its lineage parent (`parent_run_id`).
3. **Model-Independent Replacement**:
   Agent replacement selection is determined by capabilities, health, quota status, and strategy policies, never by hardcoded provider fallback logic (`if claude_failed: use_codex()`).
4. **Loop Prevention**:
   The recovery engine tracks all previously failed agents in the current task recovery chain (`failed_agents_in_chain`) and excludes them from candidate selection for that task.

---

## 3. Failure Taxonomy (`schemas/errors.py`)
- `AGENT_UNAVAILABLE`: Agent is offline or unreachable before dispatch.
- `AGENT_TIMEOUT`: Execution exceeded configured timeout threshold.
- `AGENT_PROCESS_FAILURE`: Subprocess exited unexpectedly with error code.
- `QUOTA_EXHAUSTED`: Rate limit or quota exhaustion reported by provider/adapter.
- `AUTH_FAILURE`: Missing or invalid authentication profile/keys.
- `ADAPTER_FAILURE`: Internal adapter mapping failure.
- `WORKSPACE_FAILURE`: Disk, permissions, or git worktree initialization failure.
- `TOOL_FAILURE`: Tool execution error (does not trigger agent replacement unless persistent).
- `POLICY_BLOCKED`: Action prohibited by security/workspace policy.
- `UNKNOWN_FAILURE`: Unclassified system error.

---

## 4. Checkpoint Design (`schemas/checkpoint.py`)
Checkpoints are append-only historical records containing:
- `checkpoint_id`: Unique identifier (`chk-...`).
- `task_id` & `workflow_id`: Target task/workflow context.
- `run_id`: Execution run that generated the checkpoint.
- `completed_subtasks` & `remaining_subtasks`: Subtask progress lists.
- `artifact_refs`, `evidence_refs`, `finding_refs`, `hypothesis_refs`: Durable state references.
- `workspace_snapshot` & `repository_snapshot`: Workspace and git commit snapshot metadata.
- `recovery_context`: Failure code, failed agent ID, failure reason, recovery attempt number.
- `is_valid` & `invalidation_reason`: Checkpoint integrity verification.

---

## 5. Failover Recovery Algorithm
```text
1. Detect execution interruption / failure signal.
2. Classify failure code via ErrorCode taxonomy.
3. Update agent state in Registry (e.g. QUOTA_LIMITED, UNAVAILABLE).
4. Save immutable Checkpoint with recovery context.
5. Query Agent Registry for eligible replacement candidates:
   - Exclude agents in task recovery chain (Loop Prevention).
   - Exclude QUOTA_LIMITED, UNAVAILABLE, or OFFLINE agents.
   - Filter by task required_capabilities.
6. Check max retry limit (max_retries_per_task = 2).
7. Create new Run linked to parent_run_id.
8. Transition Task state (RUNNING) and assign replacement agent.
9. Record audit events (FAILOVER_STARTED, TASK_REASSIGNED, TASK_RESUMED).
10. Resume task DAG execution.
```

---

## 6. Audit & History Logging
CLI commands `status`, `checkpoints`, and `recover` display complete run lineage and recovery history:
```bash
python3 -m llmorch status <task-id>
python3 -m llmorch checkpoints <task-id>
python3 -m llmorch recover <task-id>
```
