# LLMorch — Multi-Agent Vulnerability Research & Security Orchestration Platform

LLMorch is an elastic multi-agent vulnerability research orchestrator for hardware and software security assessment.

## Phase 0: Contract Freeze & Foundation

This repository contains the Phase 0 foundation, establishing machine-readable data contracts, state machines, agent abstractions, adapter boundaries, persistence models, and configuration infrastructure.

### Quick Start

```bash
# Check system status
python -m llmorch doctor

# View configured agents
python -m llmorch agents

# View active system configuration
python -m llmorch config

# View version information
python -m llmorch version
```

### Key Components
- **Schemas**: Pydantic data contracts (`schemas/`)
- **Orchestrator**: Task and Finding state machines (`orchestrator/`)
- **Adapters**: Provider-neutral adapter interfaces and AGY adapter (`adapters/`)
- **Registry**: Agent registration and selection engine (`registry/`)
- **History / Persistence**: SQLite foreign-key enforced relational database service (`history/`)
- **Configs**: System, agent, tool, and policy definitions (`configs/`)
