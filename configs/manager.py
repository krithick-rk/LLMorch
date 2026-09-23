"""
LLMorch Config Manager
Loads and validates YAML configuration files into Pydantic models.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from schemas.policy import AgentPolicy


class ConfigManager:
    """
    Central manager for loading, parsing, and validating LLMorch configuration files.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path(__file__).parent

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        path = self.config_dir / filename
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_system_config(self) -> Dict[str, Any]:
        return self._load_yaml("system.yaml").get("system", {})

    def get_agents_config(self) -> list:
        return self._load_yaml("agents.yaml").get("agents", [])

    def get_policy_config(self) -> AgentPolicy:
        policy_data = self._load_yaml("policies.yaml").get("agent_policy", {})
        return AgentPolicy(**policy_data) if policy_data else AgentPolicy()

    def get_tools_config(self) -> Dict[str, Any]:
        return self._load_yaml("tools.yaml").get("tools", {})
