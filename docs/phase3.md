# LLMorch — Phase 3 Two-Agent Independent Parallel Execution Report

## 1. Executive Summary

Phase 3 implements concurrent, two-agent independent parallel research workflows. The system forks a root task into two child tasks executed in separate working environments and context boundaries. Post-discovery correlation combines agent outputs into correlated finding clusters without consensus voting or compromising technical validation boundaries.

## 2. Multi-Agent Available Pool & Adapters

- **`agent-agy-01`**: `AGYAdapter` (antigravity CLI)
- **`agent-claude-01`**: `ClaudeAdapter` (Claude Code CLI)
- **`agent-codex-01`**: `CodexAdapter` (Codex CLI)

## 3. Independent Parallel Discovery Architecture

```
                      ROOT TASK
                          │
                          ▼
                    ORCHESTRATOR
                          │
                    Strategy / DAG
                          │
                    Select 2 Agents
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
        Agent A                     Agent B
        Workspace A                 Workspace B
        Context A                   Context B
            │                           │
            ▼                           ▼
       Independent                  Independent
       Investigation                Investigation
            │                           │
            └─────────────┬─────────────┘
                          ▼
                      EVIDENCE
                          │
                          ▼
                     CORRELATOR
                          │
                 ┌────────┼─────────┐
                 ▼        ▼         ▼
              related  duplicate  independent
                          │
                          ▼
                        CRITIC
```

## 4. Execution Rules & Capacity Limits
- **Max Agents Limit**: Hard-bounded to `max_agents: 2` in `system.yaml` for Phase 3.
- **Insufficient Capacity Reporting**: Returns `INSUFFICIENT_AGENT_CAPACITY` if fewer than two requested or available agents can be scheduled.
- **Context & Workspace Isolation**: Each child task executes in a distinct Git worktree workspace (`workspaces/<workflow_id>/<task_id>`). Neither agent receives the other's transcript or hypotheses during discovery.

## 5. Post-Discovery Correlation (`correlation/engine.py`)

- **Classifications**: `DUPLICATE`, `RELATED`, `INDEPENDENT`, `CONTRADICTORY`, `UNRELATED`.
- **Lineage Preservation**: Captures independent discovery lineages (`agent_id`, `run_id`, `hypothesis`) within each `FindingCluster`.
- **Non-Validation Guarantee**: Correlation engine categorizes relationships between hypotheses without voting or assigning technical confidence.
