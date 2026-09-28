"""
LLMorch SoC Context Fabric
Integrates specifications, repository structure, RTL, software, registers,
memory maps, interfaces, connectivity, clocks, resets, power domains, and security assets.
Assembles scoped, token-bounded ContextPacks for specific tasks and verification roles.
"""

from __future__ import annotations

import json
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from schemas.soc_verification import SoCComponent, InterfaceContract, SecurityAsset, ThreatModel, Requirement
from schemas.soc_ontology import SoCBucket


class ContextPack(BaseModel):
    pack_id: str = Field(default_factory=lambda: f"ctx-{uuid.uuid4().hex[:8]}")
    task_id: Optional[str] = None
    role: str
    bucket: SoCBucket
    scope: str
    components: List[SoCComponent] = Field(default_factory=list)
    interfaces: List[InterfaceContract] = Field(default_factory=list)
    security_assets: List[SecurityAsset] = Field(default_factory=list)
    requirements: List[Requirement] = Field(default_factory=list)
    source_snippets: Dict[str, str] = Field(default_factory=dict)
    registers: List[Dict[str, Any]] = Field(default_factory=list)
    token_budget: int = 15000
    estimated_tokens: int = 0
    provenance: str = "SoC Context Fabric"


class SoCContextFabric:
    """
    In-memory / persistent typed graph of the SoC under analysis.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.components: Dict[str, SoCComponent] = {}
        self.interfaces: List[InterfaceContract] = []
        self.security_assets: Dict[str, SecurityAsset] = {}
        self.threat_models: List[ThreatModel] = []
        self.requirements: Dict[str, Requirement] = {}

    def add_component(self, comp: SoCComponent) -> None:
        self.components[comp.component_id] = comp

    def add_interface(self, iface: InterfaceContract) -> None:
        self.interfaces.append(iface)

    def add_security_asset(self, asset: SecurityAsset) -> None:
        self.security_assets[asset.asset_id] = asset

    def add_threat_model(self, threat: ThreatModel) -> None:
        self.threat_models.append(threat)

    def add_requirement(self, req: Requirement) -> None:
        self.requirements[req.requirement_id] = req

    def assemble_context_pack(
        self,
        task_id: str,
        role: str,
        bucket: SoCBucket,
        scope: str,
        token_limit: int = 15000
    ) -> ContextPack:
        """
        Assembles a scoped, token-bounded context pack relevant to the task's bucket and scope.
        Never dumps the entire repository.
        """
        matched_components = []
        matched_requirements = []
        matched_assets = []
        matched_interfaces = []

        # Find components related to scope
        for comp in self.components.values():
            if scope.lower() in comp.name.lower() or any(scope.lower() in sf.lower() for sf in comp.source_files):
                matched_components.append(comp)
            elif bucket in (SoCBucket.IP_BOUNDARY, SoCBucket.CONNECTIVITY, SoCBucket.INTERCONNECT):
                matched_components.append(comp)

        # Find requirements matching bucket
        for req in self.requirements.values():
            if req.primary_bucket == bucket or any(c.name in req.affected_components for c in matched_components):
                matched_requirements.append(req)

        # Find relevant security assets
        if bucket in (SoCBucket.SECURITY, SoCBucket.BOOT, SoCBucket.DEBUG, SoCBucket.FUSES_OTP):
            matched_assets = list(self.security_assets.values())[:5]

        # Calculate rough token footprint (4 chars per token)
        estimated_tokens = (
            len(matched_components) * 150 +
            len(matched_requirements) * 120 +
            len(matched_assets) * 80 +
            500
        )

        pack = ContextPack(
            task_id=task_id,
            role=role,
            bucket=bucket,
            scope=scope,
            components=matched_components[:10],
            interfaces=matched_interfaces[:10],
            security_assets=matched_assets[:5],
            requirements=matched_requirements[:15],
            token_budget=token_limit,
            estimated_tokens=min(estimated_tokens, token_limit),
            provenance=f"SoC Context Fabric (scanned {self.repo_path})"
        )
        return pack

    def export_graph_summary(self) -> Dict[str, Any]:
        return {
            "repository_path": self.repo_path,
            "components_count": len(self.components),
            "interfaces_count": len(self.interfaces),
            "security_assets_count": len(self.security_assets),
            "threat_models_count": len(self.threat_models),
            "requirements_count": len(self.requirements),
            "components": [c.model_dump() for c in self.components.values()][:50],
            "interfaces": [i.model_dump() for i in self.interfaces][:50],
            "security_assets": [a.model_dump() for a in self.security_assets.values()][:50],
        }
