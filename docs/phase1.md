# LLMorch — Phase 1 Single-Agent End-to-End MVP Implementation Report

## 1. Executive Summary

Phase 1 establishes the first end-to-end vulnerability research workflow for LLMorch using a single configured agent (`agent-agy-01` via `AGYAdapter` launching local `antigravity` CLI). The complete vertical slice has been implemented and validated without breaking Phase 0 data contracts or abstractions.

## 2. Real Antigravity Executable Detection & Execution Flow

- **Executable Detected**: `antigravity` (located on system `PATH` via `shutil.which`)
- **Invocation Command**: `antigravity --prompt "<context_prompt>"`
- **Supervision & Process Isolation**: Uses `subprocess.Popen` with process-group management (`preexec_fn=os.setsid` and `os.killpg`) to ensure clean cancellation and prevent orphaned child processes.
- **Environment Boundary**: Executed strictly within the assigned task workspace (`/home/hackdac/Desktop/intern/LLMorch/workspaces/<workflow_id>/<task_id>`).

## 3. Vertical Pipeline Operations

```
USER REQUEST / CLI (--repo, --target)
        ↓
1. Repository Intake (Path normalization, symlink safety audit, commit hash)
        ↓
2. Snapshot (RepositorySnapshot metadata record created)
        ↓
3. Analysis Unit & Noise Filtering (NoiseFilter classifies ANALYZE vs IGNORE)
        ↓
4. Cheap Deterministic Pre-checks (DeterministicPreChecker static pattern scan)
        ↓
5. Task Creation (Task schema, state=QUEUED)
        ↓
6. Agent Registry Selection (select_agents() returns agent-agy-01)
        ↓
7. Workspace Allocation (WorkspaceManager creates isolated git worktree/dir)
        ↓
8. AGY Adapter Process Execution (Subprocess launch, stdout/stderr captured)
        ↓
9. Result Normalization (TaskResult contract produced)
        ↓
10. Citation / Location Verification (FindingValidator verifies target files/lines)
        ↓
11. Deterministic Validation (Syntax/lint verification, validator status returned)
        ↓
12. Evidence & Finding Storage (Evidence & Finding schemas persisted in SQLite)
        ↓
13. Task Finalization (Task transitions to SUCCEEDED or FAILED)
```

## 4. Workspaces & Security Isolation

- Workspaces are dynamically created under `workspaces/<workflow_id>/<task_id>`.
- The worker executes inside the workspace and is prevented from mutating the primary checkout repository.
- Host credentials, user home directories, and external symlinks are strictly isolated.

## 5. CLI Investigation Command

Run a real investigation:

```bash
python3 -m llmorch investigate --repo /home/hackdac/Desktop/intern/LLMorch --target schemas
```
