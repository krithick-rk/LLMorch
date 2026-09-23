# LLMorch — Investigation Flow Specification

The investigation flow (`orchestrator/investigation.py`) implements the complete Phase 1 pipeline:

```
[1] Intake & Snapshot   ---> Verifies repository root and commit identity
[2] Scoped Analysis     ---> Applies NoiseFilter to limit LLM context
[3] Pre-checks          ---> Runs static regex/pattern checks
[4] Task Dispatch       ---> Task state: QUEUED -> DISPATCHED -> RUNNING
[5] Agent Selection     ---> Selected via AgentRegistry matching capabilities
[6] Workspace           ---> Isolated directory created for execution
[7] Subprocess Exec     ---> AGYAdapter runs local CLI
[8] Citation Check      ---> Verifies files and line numbers reported by agent
[9] Validation          ---> FindingValidator runs deterministic checks
[10] Finding & Evidence ---> Persists Evidence and Finding in SQLite
```
