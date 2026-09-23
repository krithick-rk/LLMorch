# LLMorch — Strategy Engine Architecture Specification

## 1. Overview
The `StrategyEngine` (`orchestrator/strategy.py`) is responsible for selecting the optimal agent pool size and role assignments.

## 2. Input Signals & Assessment
- **Complexity**: Derived from file count in AnalysisUnit (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Security Sensitivity**: Keywords (`crypto`, `auth`, `privilege`, `boot`, `key`, `state`, `register`).
- **Uncertainty**: Static pre-check findings and target ambiguity.
- **Parallelism**: Independent sub-domain investigation potential.
- **Budget**: Resource cost units remaining for the workflow.

## 3. Decision Pipeline
1. Capability extraction from Task specification.
2. Hard constraint filtering against `AgentRegistry`.
3. Signal derivation from task targets and pre-checks.
4. Optimal agent count calculation (1 to 4).
5. Explainable `StrategyDecision` creation.
6. Task-time `AgentAssignment` mapping.
