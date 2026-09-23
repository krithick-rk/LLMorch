# LLMorch — Phase 2 Generic Adapters & Model Independence Report

## 1. Executive Summary

Phase 2 establishes complete model independence and generic agent adapter abstraction for LLMorch. The orchestrator now dispatches tasks to different underlying agents (`agent-agy-01` via `AGYAdapter` and `agent-claude-01` via `ClaudeAdapter`) using a provider-neutral interface without containing any provider-specific branching (`if provider == ...`).

## 2. Generic Adapter Interface (`adapters/base.py`)

All adapters implement `BaseAgentAdapter`:
```python
class BaseAgentAdapter(ABC):
    def start(self, task: Task) -> Run: ...
    def execute_task_sync(self, task: Task, workspace_dir: str, context_prompt: str) -> Dict[str, Any]: ...
    def stream(self, run_id: str) -> Generator[Event, None, None]: ...
    def cancel(self, task_id: str) -> bool: ...
    def health(self) -> AgentHealthState: ...
    def capabilities(self) -> List[str]: ...
    def collect_artifacts(self, run_id: str) -> List[Artifact]: ...
    def normalize_result(self, raw_output: Any) -> TaskResult: ...
    def version(self) -> str: ...
    def configuration(self) -> Dict[str, Any]: ...
    def workspace_requirements(self) -> Dict[str, Any]: ...
```

## 3. Claude Code Adapter Implementation (`adapters/claude_adapter.py`)

- **Binary Detection**: Automatically detects installed `claude`, `claude-code`, or `claude-cli` executable.
- **Invocation**: Executes non-interactive prompt via `claude -p "<context_prompt>"`.
- **Process Supervision**: Uses `subprocess.Popen` with process-group management (`preexec_fn=os.setsid` and `os.killpg`) for timeout enforcement and clean cancellation.
- **Normalization**: Parses stdout/JSON into standardized `TaskResult` contract.

## 4. Multi-Agent Registry & Capability-Based Routing

- Both `agent-agy-01` (provider: `antigravity`) and `agent-claude-01` (provider: `anthropic`) are registered in `AgentRegistry`.
- Capability tags (`repository_analysis`, `security_review`, `code_analysis`, etc.) allow matching agents based on task requirements.
- The CLI supports agent selection:
  ```bash
  python3 -m llmorch investigate --repo /path/to/repo --target schemas --agent agent-agy-01
  python3 -m llmorch investigate --repo /path/to/repo --target schemas --agent agent-claude-01
  ```

## 5. Model-Agnostic State & Contract Parity

- Persistent state (`Task`, `Run`, `Artifact`, `Evidence`, `Finding`, `Event`) is entirely decoupled from the underlying LLM/agent context.
- Output from both AGY and Claude is normalized into the exact same `TaskResult` contract.
- Failures in one adapter or process execution are cleanly isolated and do not corrupt database or other agents.
