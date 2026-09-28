"""
LLMorch Dynamic Agent Roles & Capability Mapping (Agentic Layer)
Maps 23-bucket SoC verification tasks to task-scoped capabilities and roles.
Enforces the 1-4 elastic agent execution model where a single executable agent
can sequentially assume multiple verification roles.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from schemas.soc_ontology import SoCBucket


class AgentRoleDefinition(BaseModel):
    role_name: str
    primary_responsibility: str
    supported_buckets: List[SoCBucket]
    required_capabilities: List[str]
    recommended_tools: List[str]
    description: str


SOC_AGENT_ROLES: Dict[str, AgentRoleDefinition] = {
    "Spec / Verification QA": AgentRoleDefinition(
        role_name="Spec / Verification QA",
        primary_responsibility="Extract requirements, answer verification questions, identify missing specification context",
        supported_buckets=[SoCBucket.IP_BOUNDARY, SoCBucket.MEMORY_SYSTEM, SoCBucket.PRODUCT_VARIANTS],
        required_capabilities=["specification_analysis", "natural_language_reasoning", "requirement_extraction"],
        recommended_tools=["semgrep"],
        description="Ingests RM/TRM documents and maintains specification-to-design fidelity"
    ),
    "SoC Asset & Boundary": AgentRoleDefinition(
        role_name="SoC Asset & Boundary",
        primary_responsibility="Identify assets, trust boundaries, interfaces and critical components",
        supported_buckets=[SoCBucket.IP_BOUNDARY, SoCBucket.CONNECTIVITY, SoCBucket.SECURITY],
        required_capabilities=["boundary_analysis", "asset_mapping"],
        recommended_tools=["verilator", "yosys", "semgrep"],
        description="Maps IP perimeters, register access controls, and privilege tiers"
    ),
    "Architecture / Connectivity": AgentRoleDefinition(
        role_name="Architecture / Connectivity",
        primary_responsibility="Map buses, clocks, resets, IRQ, DMA, pins, sidebands and reachability",
        supported_buckets=[SoCBucket.CONNECTIVITY, SoCBucket.CROSS_IP_FLOWS, SoCBucket.PIN_MUXING],
        required_capabilities=["connectivity_mapping", "cross_ip_flow_tracing"],
        recommended_tools=["verilator", "yosys", "slang"],
        description="Analyzes structural interconnects, pin multiplexing, and cross-subsystem event triggers"
    ),
    "Threat Modeling": AgentRoleDefinition(
        role_name="Threat Modeling",
        primary_responsibility="Build threats, attack surfaces, assumptions, misuse cases and security objectives",
        supported_buckets=[SoCBucket.SECURITY, SoCBucket.ERROR_SAFETY, SoCBucket.DEBUG],
        required_capabilities=["threat_modeling", "abuse_case_generation"],
        recommended_tools=["semgrep", "z3"],
        description="Formulates threat models and attacker privilege escalation paths"
    ),
    "CDC / RDC / Clock / Reset": AgentRoleDefinition(
        role_name="CDC / RDC / Clock / Reset",
        primary_responsibility="Identify clock/reset crossings, synchronization risks, and sequencing scenarios",
        supported_buckets=[SoCBucket.CLOCKS, SoCBucket.RESETS, SoCBucket.CDC, SoCBucket.RDC, SoCBucket.X_INIT],
        required_capabilities=["cdc_rdc_analysis", "clock_tree_reasoning", "reset_sequencing"],
        recommended_tools=["yosys", "verilator"],
        description="Verifies clock domain crossings, reset assertion ordering, and X-propagation"
    ),
    "Power / Performance": AgentRoleDefinition(
        role_name="Power / Performance",
        primary_responsibility="Plan DVFS, power states, QoS, latency, bandwidth and blast-radius scenarios",
        supported_buckets=[SoCBucket.PERFORMANCE, SoCBucket.BLAST_RADIUS, SoCBucket.POWER_MODES],
        required_capabilities=["power_modeling", "performance_analysis"],
        recommended_tools=["cocotb", "verilator"],
        description="Assesses power-mode transitions, retention isolation, and contention latency"
    ),
    "Memory / Interconnect / Coherency": AgentRoleDefinition(
        role_name="Memory / Interconnect / Coherency",
        primary_responsibility="Map memory attributes, ordering, coherency, atomics, deadlock and multi-master cases",
        supported_buckets=[SoCBucket.MEMORY_SYSTEM, SoCBucket.INTERCONNECT, SoCBucket.PROCESSOR_INTEGRATION],
        required_capabilities=["memory_map_analysis", "interconnect_routing", "coherency_reasoning"],
        recommended_tools=["verilator", "slang", "yosys"],
        description="Verifies memory address maps, bus ordering rules, and cache/interconnect integration"
    ),
    "Boot / Debug / OTP / Lifecycle": AgentRoleDefinition(
        role_name="Boot / Debug / OTP / Lifecycle",
        primary_responsibility="Plan secure boot, debug access, fuses, OTP, lifecycle and product variants",
        supported_buckets=[SoCBucket.BOOT, SoCBucket.DEBUG, SoCBucket.FUSES_OTP, SoCBucket.PRODUCT_VARIANTS],
        required_capabilities=["lifecycle_state_analysis", "boot_flow_verification"],
        recommended_tools=["verilator", "semgrep"],
        description="Examines root-of-trust boot, debug authentication unlocks, and fuse provisioning"
    ),
    "Verification Planning": AgentRoleDefinition(
        role_name="Verification Planning",
        primary_responsibility="Convert requirements and risks into tests, properties, coverage and tool plans",
        supported_buckets=[SoCBucket.IP_BOUNDARY, SoCBucket.CONNECTIVITY, SoCBucket.SECURITY, SoCBucket.PRODUCT_VARIANTS],
        required_capabilities=["plan_synthesis", "scenario_decomposition"],
        recommended_tools=["verilator", "cocotb"],
        description="Synthesizes verification objectives into bounded, executable work packages"
    ),
    "Test / Property Generation": AgentRoleDefinition(
        role_name="Test / Property Generation",
        primary_responsibility="Generate UVM, SVA, formal assertions, fuzz targets, and simulation tests",
        supported_buckets=[SoCBucket.SECURITY, SoCBucket.CONNECTIVITY, SoCBucket.CDC, SoCBucket.GATE_STATIC_SIGNOFF],
        required_capabilities=["sva_generation", "testbench_authoring"],
        recommended_tools=["verilator", "cocotb", "yosys"],
        description="Produces executable testbenches and SystemVerilog Assertions"
    ),
    "Vulnerability / Security Verification": AgentRoleDefinition(
        role_name="Vulnerability / Security Verification",
        primary_responsibility="Investigate security weaknesses, privilege leaks, and hardware abuse cases",
        supported_buckets=[SoCBucket.SECURITY, SoCBucket.IP_BOUNDARY, SoCBucket.DEBUG],
        required_capabilities=["vulnerability_research", "reproducer_generation"],
        recommended_tools=["yosys", "verilator", "z3", "semgrep"],
        description="Executes targeted penetration and hardware security invariant testing"
    ),
    "Policy Generation": AgentRoleDefinition(
        role_name="Policy Generation",
        primary_responsibility="Generate machine-readable security policy candidates tied to validated evidence",
        supported_buckets=[SoCBucket.SECURITY, SoCBucket.ERROR_SAFETY],
        required_capabilities=["policy_synthesis", "invariant_formulation"],
        recommended_tools=["semgrep", "z3"],
        description="Generates verifiable security policy candidates (SoCureLLM-inspired)"
    ),
    "Critic": AgentRoleDefinition(
        role_name="Critic",
        primary_responsibility="Falsify plans, identify unsupported assumptions and contradictory evidence",
        supported_buckets=[SoCBucket.GATE_STATIC_SIGNOFF, SoCBucket.IP_BOUNDARY, SoCBucket.SECURITY],
        required_capabilities=["adversarial_critique", "contradiction_detection"],
        recommended_tools=["yosys", "verilator", "boolector"],
        description="Adversarially audits verification claims and challenges unverified assumptions"
    ),
    "Reproducer / Validation": AgentRoleDefinition(
        role_name="Reproducer / Validation",
        primary_responsibility="Create executable reproducer/test and prepare deterministic validation",
        supported_buckets=[SoCBucket.GATE_STATIC_SIGNOFF, SoCBucket.SECURITY],
        required_capabilities=["test_execution", "deterministic_validation"],
        recommended_tools=["verilator", "cocotb", "slang"],
        description="Orchestrates sandbox execution of candidate PoCs and validates deterministic outcomes"
    ),
    "Closure": AgentRoleDefinition(
        role_name="Closure",
        primary_responsibility="Maintain requirement/test/coverage/waiver closure and surface residual gaps",
        supported_buckets=[SoCBucket.CLOSURE],
        required_capabilities=["coverage_audit", "closure_tracking"],
        recommended_tools=["verilator", "cocotb"],
        description="Aggregates verified evidence against requirements to produce authoritative closure snapshots"
    ),
}


def get_role_definition(role_name: str) -> Optional[AgentRoleDefinition]:
    return SOC_AGENT_ROLES.get(role_name)


def list_roles_for_bucket(bucket: SoCBucket) -> List[AgentRoleDefinition]:
    matching = []
    for r in SOC_AGENT_ROLES.values():
        if bucket in r.supported_buckets:
            matching.append(r)
    return matching


get_role_profile = get_role_definition


def list_all_roles() -> List[str]:
    """Returns list of all available dynamic agent role names."""
    return list(SOC_AGENT_ROLES.keys())


def map_bucket_to_role(bucket: SoCBucket) -> str:
    """Maps an SoC verification bucket to its primary recommended role."""
    from schemas.soc_ontology import SOC_BUCKET_DEFINITIONS
    defn = SOC_BUCKET_DEFINITIONS.get(bucket)
    if defn:
        return defn.recommended_role
    roles = list_roles_for_bucket(bucket)
    return roles[0].role_name if roles else "Verification Planning"
