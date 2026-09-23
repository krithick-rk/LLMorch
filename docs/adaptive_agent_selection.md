# LLMorch — Adaptive Agent Selection & Explainability

## 1. Explainability Guarantees
Every strategy decision is persisted as a `StrategyDecision` record and output to the CLI, providing answers to:
- Why was this agent count selected?
- What signals (complexity, security, uncertainty, budget) influenced the decision?
- Which agents were considered and why were any excluded?
- What conditions would trigger escalation or stop rules?

## 2. Escalation & Stop Rules
- **Escalation**: Triggered when initial discovery yields high uncertainty or contradictory hypotheses, prompting the addition of an independent investigator up to `max_agents: 4`.
- **Stop Conditions**: Halts pool expansion when marginal benefit is low, capacity limit is reached, or budget is exhausted.
