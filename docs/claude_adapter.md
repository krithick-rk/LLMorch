# LLMorch — Claude Code Adapter Specification

The `ClaudeAdapter` (`adapters/claude_adapter.py`) encapsulates Anthropic Claude Code CLI execution behind the provider-neutral `BaseAgentAdapter` interface.

## 1. Executable & Environment Setup
- **Binary Detection**: Automatically checks `shutil.which("claude")`, `shutil.which("claude-code")`, and `shutil.which("claude-cli")`.
- **Non-Interactive Execution**: Invokes non-interactive print mode via `-p "<context_prompt>"`.
- **Workspace Isolation**: Executed strictly inside the assigned workspace working directory.

## 2. Interface Compliance
Implements all required methods from `BaseAgentAdapter`:
- `start(task)`: Creates `Run` record with `agent_id = "agent-claude-01"`.
- `execute_task_sync(task, workspace_dir, context_prompt)`: Runs process synchronously with process group ID (`os.setsid`).
- `stream(run_id)`: Streams agent execution events.
- `cancel(task_id)`: Sends `SIGTERM` to process group (`os.killpg`).
- `health()`: Queries CLI binary availability.
- `capabilities()`: Returns supported capability list.
- `normalize_result(raw_output)`: Parses raw output into standard `TaskResult` contract.

## 3. Failure Handling & Credentials
- Authentication is managed via the host environment; credentials are NEVER copied into LLMorch databases or repository files.
- Process timeouts and failures set `RunStatus.FAILED` or `RunStatus.TIMEOUT` without corrupting task state.
