# LLMorch — State Machines Specification

LLMorch defines two core state machines in `orchestrator/state_machine.py`: the Task State Machine and the Finding State Machine.

## 1. Task State Machine

### States
- `QUEUED`: Task created and awaiting dispatch.
- `DISPATCHED`: Task assigned to an agent and queued for process launch.
- `RUNNING`: Task execution actively under way.
- `WAITING`: Task paused waiting for subtask, user input, or validator.
- `BLOCKED`: Task execution blocked by policy or missing dependency.
- `SUCCEEDED` (Terminal): Task completed successfully.
- `FAILED` (Terminal): Task execution failed after all retries exhausted.
- `CANCELED` (Terminal): Task execution explicitly canceled by user or orchestrator.

### Transition Rules
```
QUEUED → DISPATCHED, CANCELED
DISPATCHED → RUNNING, FAILED, CANCELED
RUNNING → WAITING, SUCCEEDED, FAILED, CANCELED, BLOCKED
WAITING → RUNNING, FAILED, CANCELED
BLOCKED → RUNNING, QUEUED, FAILED, CANCELED
```

Attempts to transition out of terminal states (`SUCCEEDED`, `FAILED`, `CANCELED`) raise `InvalidStateTransitionError`.

## 2. Finding State Machine

### States
- `HYPOTHESIS`: Initial candidate finding or vulnerability hypothesis.
- `REVIEWED`: Preliminary inspection completed by an agent.
- `CORROBORATED`: Supporting tool output or evidence gathered.
- `CONTRADICTED`: Contradicting evidence observed.
- `VALIDATION_PENDING`: Sent to formal validator or reproducer script.
- `CONFIRMED` (Terminal): Finding verified by execution or proof.
- `REJECTED` (Terminal): Finding disproven or rejected.
- `UNRESOLVED`: Conflicting evidence remains unresolved.

### Transition Rules
```
HYPOTHESIS → REVIEWED, VALIDATION_PENDING, REJECTED
REVIEWED → CORROBORATED, CONTRADICTED, VALIDATION_PENDING, REJECTED
CORROBORATED → VALIDATION_PENDING, CONFIRMED, UNRESOLVED
CONTRADICTED → REJECTED, UNRESOLVED
VALIDATION_PENDING → CONFIRMED, REJECTED, CONTRADICTED, UNRESOLVED
UNRESOLVED → VALIDATION_PENDING, REVIEWED, REJECTED
```

The orchestrator owns all state transitions for security findings.
