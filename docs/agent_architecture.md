# LLMorch — Agent Architecture & Adapter Boundaries

## 1. Elastic Agent Model (1–4 Agents)

LLMorch supports dynamic scaling across 1 to 4 agents without hard-coding roles or provider names:
- **1 configured agent**: Single-agent mode
- **2 configured agents**: Two-agent mode
- **3 configured agents**: Three-agent mode
- **4 configured agents**: Four-agent mode

Agents are identified by independent identifiers (e.g. `agent-agy-01`) rather than model names. Roles (e.g. master, researcher, validator) are assigned dynamically by the orchestrator based on data-driven capability matching.

## 2. Provider-Neutral Adapter Pattern

The core orchestrator interacts only through the `BaseAgentAdapter` interface:

```
Orchestrator
     ↓
BaseAgentAdapter Interface
     ↓
AGYAdapter Implementation
     ↓
Antigravity CLI (Local Subprocess)
```

Future adapters (`ClaudeAdapter`, `CodexAdapter`, `RemoteA2AAdapter`) implement the exact same interface without modifying orchestrator logic.

## 3. A2A & MCP Architectural Boundaries

LLMorch enforces clear architectural separation across integration mechanisms:
- **Adapter**: Local or provider-specific process boundary (e.g. AGY CLI). Local CLI calls are **never** described or treated as A2A.
- **A2A (Agent-to-Agent)**: Distributed agent interoperability protocol across distinct gateway endpoints.
- **MCP (Model Context Protocol)**: Tool and context provider integration boundary.

## 4. Failover & Checkpoints

When an active agent encounters failure or quota exhaustion (`AGENT_UNAVAILABLE`, `QUOTA_EXHAUSTED`):
1. Execution state is persisted into a `Checkpoint`.
2. The agent's status in `AgentRegistry` is updated to `UNAVAILABLE` or `QUOTA_LIMITED`.
3. `AgentRegistry.select_agents()` identifies an available replacement agent matching the task's required capabilities.
4. The replacement agent resumes execution directly from the `Checkpoint` without requiring prior conversation logs.
