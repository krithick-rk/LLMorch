# LLMorch Quota Awareness Specification

## Quota & Rate Limit Handling

### Registry Integration
Agents reporting `QUOTA_EXHAUSTED` errors have their registry status updated:
- `health`: `QUOTA_LIMITED`
- `quota_status`: `EXHAUSTED`
- `availability`: `False`

### Replacement Selection
When selecting replacement agents:
1. `StrategyEngine` and `FailoverEngine` filter candidates by `availability == True` and `health == AgentHealthState.AVAILABLE`.
2. Quota-limited agents are excluded automatically without hardcoding model names.
3. If no eligible replacement agent exists, the task transitions to `BLOCKED`.
