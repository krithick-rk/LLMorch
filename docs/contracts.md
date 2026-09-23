# LLMorch — Data Contracts Specification

All machine-readable data contracts in LLMorch are implemented using Pydantic models located in `schemas/`.

## 1. Task Contract (`schemas/task.py`)
- `task_id`: Unique durable task identifier (e.g. `task-a1b2c3d4e5f6`)
- `workflow_id`: Parent workflow ID
- `parent_task_id`: Parent task ID for subtasks
- `objective`: Objective description
- `inputs`: Input parameter dictionaries
- `dependencies`: List of preceding task_ids
- `required_capabilities`: Capability strings required
- `preferred_roles`: Preferred functional roles
- `risk_level`: RiskLevel enum (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `workspace_policy`: Workspace isolation rules
- `tool_policy`: Tool permissions
- `budget`: Step/time/cost budget limits
- `status`: TaskStatus enum
- `assigned_agent_id`: Identifier of assigned agent
- `retry_count`: Retry counter
- `acceptance_criteria`: Acceptance criteria strings
- `result_ref`: Output reference URI/path
- `schema_version`: Contract schema version (`1.0.0`)
- Timestamps: `created_at`, `started_at`, `completed_at`

## 2. Agent Contract (`schemas/agent.py`)
- `agent_id`: Independent instance identifier (e.g. `agent-agy-01`)
- `provider`: Provider identifier (e.g. `antigravity`)
- `interface`: AgentInterface enum (`cli`, `api`, `a2a`, `embedded`)
- `model`: Model identifier (e.g. `runtime-resolved`)
- `capabilities`: Capability strings
- `protocols`: Protocol strings (`cli-v1`, `mcp-v1`)
- `permissions`: Permission scope strings
- `health`: AgentHealthState enum
- `availability`: Boolean flag
- `concurrency_limit`: Max concurrent tasks (default 1)
- `usage_status`: AgentUsageStatus
- `quota_status`: AgentQuotaStatus enum
- `workspace_class`: Workspace level requirement
- `auth_profile`: Authentication metadata
- `adapter_version`: Adapter version string
- `metadata`: Extension metadata dictionary
- `schema_version`: Contract schema version (`1.0.0`)

## 3. Checkpoint Contract (`schemas/checkpoint.py`)
- `checkpoint_id`: Unique checkpoint identifier
- `task_id`: Associated task ID
- `workflow_id`: Optional workflow ID
- `run_id`: Associated run ID
- `completed_subtasks`: List of completed subtask IDs
- `remaining_subtasks`: List of remaining subtask IDs
- `task_state`: Intermediate execution state dictionary
- `artifact_refs`: List of produced artifact IDs
- `evidence_refs`: List of recorded evidence IDs
- `finding_refs`: List of generated finding IDs
- `hypothesis_refs`: List of active hypothesis IDs
- `workspace_snapshot`: Workspace snapshot metadata
- `repository_snapshot`: Repository commit/snapshot hash
- `next_action`: Explicit next action recommendation
- `created_at`: Checkpoint timestamp

## 4. Evidence Contract (`schemas/evidence.py`)
- `evidence_id`: Unique evidence identifier
- `task_id`: Associated task ID
- `run_id`: Associated run ID
- `agent_id`: Agent ID
- `artifact_id`: Optional artifact ID
- `source_type`: EvidenceSourceType enum (`AGENT_CLAIM`, `TOOL_OUTPUT`, `EXECUTION_RESULT`, `VALIDATOR_RESULT`)
- `timestamp`: Timestamp
- `tool`: Tool name
- `command`: Command string executed
- `raw_hash`: Hash of raw unparsed output
- `canonical_hash`: Hash of canonical output
- `semantic_fingerprint`: Semantic fingerprint string
- `environment_fingerprint`: Environment fingerprint string
- `exit_status`: Exit status code
- `provenance_links`: Preceding evidence links

## 5. Event Contract (`schemas/event.py`)
- `event_id`: Unique event identifier
- `run_id`: Associated run ID
- `timestamp`: Timestamp
- `event_type`: EventType enum
- `actor`: Actor identifier
- `tool`: Optional tool identifier
- `payload_ref`: Reference URI to large payload
- `payload`: Inline event payload
- `parent_event_id`: Causal parent event ID
