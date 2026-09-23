"""
LLMorch Data Contracts - Agent Health & Quota State
"""

from enum import Enum
from typing import Optional, Union, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AgentHealthState(str, Enum):
    """Structured representation of agent health and operational availability."""
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    QUOTA_LIMITED = "QUOTA_LIMITED"
    OFFLINE = "OFFLINE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    ERROR = "ERROR"


class AgentQuotaStatus(str, Enum):
    """Quota status classification."""
    UNKNOWN = "UNKNOWN"
    OK = "OK"
    WARNING = "WARNING"
    EXHAUSTED = "EXHAUSTED"


class AgentUsageStatus(BaseModel):
    """
    Real-time usage and quota tracking data.
    Quota fields default to None (representing 'unknown') when APIs are unavailable.
    Never fake quota values.
    """
    remaining_quota: Optional[float] = Field(default=None, description="Remaining quota units, or None if unknown")
    total_quota: Optional[float] = Field(default=None, description="Total quota limit, or None if unknown")
    quota_reset_time: Optional[datetime] = Field(default=None, description="Reset timestamp for quota, or None if unknown")
    current_load: int = Field(default=0, description="Current concurrent tasks being executed")
    last_seen: datetime = Field(default_factory=datetime.utcnow, description="Last heart-beat or communication timestamp")
    health_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when health was recorded")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional health diagnostic details")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
