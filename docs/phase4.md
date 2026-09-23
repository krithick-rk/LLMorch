# LLMorch — Phase 4 Adaptive 1–4 Agent Strategy Engine Report

## 1. Executive Summary

Phase 4 establishes runtime adaptive agent selection, allowing LLMorch to dynamically determine the optimal agent pool size (1, 2, 3, or 4 active agents) based on deterministic task complexity, security sensitivity, uncertainty, parallelism, budget constraints, and hard availability filtering.

## 2. Minimum Useful Pool Principle

LLMorch strictly enforces using the **minimum number of agents** required for investigation quality:
- **1 Agent**: Narrow scope, low complexity, or low uncertainty.
- **2 Agents**: Security-sensitive or moderate uncertainty tasks requiring independent corroboration.
- **3 Agents**: High complexity or cross-domain investigations requiring multiple capability roles.
- **4 Agents**: Critical complexity, high uncertainty, multi-capability requirements, and high parallelism potential with 4 eligible agents available.

## 3. Architecture & Contracts

- **`StrategyEngine`** (`orchestrator/strategy.py`): Evaluates task signals and hard constraints to produce an explainable decision.
- **`StrategyDecision`** (`schemas/strategy.py`): Persisted Pydantic contract recording decision IDs, signals, reasoning, candidate/excluded agents, and escalation/stop conditions.
- **`AgentAssignment`** (`schemas/strategy.py`): Assigns task-time roles (`primary_investigation`, `independent_investigation`, `architecture_analysis`, `adversarial_review`).

## 4. Hard Constraint & Soft Preference Filtering

- **Hard Constraints**: Excludes agents failing capability matching, disabled in configuration, or reporting `UNAVAILABLE` health state. Never fabricates missing agents.
- **Soft Preferences**: Ranks eligible candidates based on capability coverage, health, load, and budget impact.

## 5. Execution Modes (1, 2, 3, 4 Agents)

- **1-Agent Mode**: Executes directly without fork overhead.
- **2-Agent / 3-Agent / 4-Agent Modes**: Forks root task into N child tasks executed concurrently via `ThreadPoolExecutor(max_workers=N)` with separate Git worktree workspaces and un-anchored context boundaries, followed by post-discovery correlation.
