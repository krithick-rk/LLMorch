# LLMorch — Generic Adapter Architecture & Model Independence

## 1. Provider-Neutral Architecture

```
                    ┌─────────────────────┐
                    │    ORCHESTRATOR     │
                    │                     │
                    │ Task / DAG / Policy │
                    │ State / Scheduling  │
                    └──────────┬──────────┘
                               │
                        Agent Registry
                               │
                    capability-based match
                               │
              ┌────────────────┴────────────────┐
              │                                 │
        ┌─────▼────────┐                 ┌──────▼───────┐
        │  AGY Adapter │                 │Claude Adapter│
        └─────┬────────┘                 └──────┬───────┘
              │                                 │
        Antigravity CLI                    Claude Code CLI
              │                                 │
              └──────────────┬──────────────────┘
                             ▼
                        SAME Task model
                        SAME Evidence model
                        SAME Run model
                        SAME Result model
                        SAME Finding model
```

## 2. Adapter Lifecycle
1. **Task Received**: Task contract validated against policy and required capabilities.
2. **Workspace Preparation**: WorkspaceManager allocates isolated working directory.
3. **Provider-Specific Invocation**: Adapter constructs controlled argument list for target CLI.
4. **Supervised Execution**: Subprocess launched with process group ID (`os.setsid`) and timeout monitoring.
5. **Event Streaming & Capture**: Stdout/stderr captured and streamed as structured `Event` records.
6. **Output Normalization**: Raw output normalized into standard `TaskResult` contract.

## 3. Strict Separation of Concerns
- **Role & Capability**: Assigned dynamically by Orchestrator.
- **Provider & Adapter**: Encapsulated inside adapter package (`adapters/`).
- **Orchestration Logic**: Completely free of provider-specific branching (`if provider == ...`).
