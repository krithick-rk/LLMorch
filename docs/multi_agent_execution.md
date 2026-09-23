# LLMorch — Multi-Agent Execution Specification

## 1. Concurrency & Scheduling
- Concurrent execution is managed via Python `concurrent.futures.ThreadPoolExecutor(max_workers=2)`.
- Parent root task is created in state `RUNNING` and forked into two child tasks (`task_id` -> `child_task_id_0`, `child_task_id_1`).
- Root task transitions to `READY_FOR_REVIEW` only after both child tasks finish discovery and post-discovery correlation completes.

## 2. Workspace & Context Isolation
- **Workspace**: Allocated dynamically by `WorkspaceManager` under separate directory trees.
- **Context**: Prompts passed to child tasks contain only root task objectives, scoped analysis paths, and deterministic pre-check findings. No LLM transcripts or hypotheses from peer agents are exposed.
