# LLMorch — AGY Adapter Specification

The `AGYAdapter` (`adapters/agy_adapter.py`) encapsulates Antigravity CLI process execution behind the provider-neutral `BaseAgentAdapter` interface.

## 1. Interface Capabilities
- `start(task: Task) -> Run`: Initializes execution attempt record.
- `execute_task_sync(task, workspace_dir, prompt)`: Launches real CLI process with process-group supervision.
- `stream(run_id)`: Generates real-time execution events.
- `cancel(task_id)`: Sends `SIGTERM` to the process group (`os.killpg`).
- `health()`: Checks binary existence via `shutil.which`.
- `capabilities()`: Returns supported capability list.
- `normalize_result(raw_output)`: Parses raw stdout into standard `TaskResult` contract.

## 2. Process Group Isolation & Supervision
- Sets process group ID via `preexec_fn=os.setsid`.
- Monitors process timeout using `task.budget.max_seconds`.
- On cancellation or timeout, terminates child and sub-child processes gracefully without leaking host resources.
