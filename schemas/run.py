"""
LLMorch Data Contracts - Run Model
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class RunStatus(str, Enum):
    """Run execution status."""
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    INTERRUPTED = "INTERRUPTED"


class Run(BaseModel):
    """
    Represents one execution attempt of a Task.
    One Task can have multiple Runs due to retries or failover.
    """
    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}", description="Unique run attempt identifier")
    task_id: str = Field(..., description="Associated task identifier")
    parent_run_id: Optional[str] = Field(default=None, description="Lineage parent run ID if this run is a retry/failover attempt")
    agent_id: str = Field(..., description="Identifier of the executing agent")
    adapter_version: str = Field(default="1.0.0", description="Version of the adapter used for this run")
    start_time: datetime = Field(default_factory=datetime.utcnow, description="Run start timestamp")
    end_time: Optional[datetime] = Field(default=None, description="Run completion timestamp")
    process_id: Optional[int] = Field(default=None, description="OS process ID if applicable")
    exit_status: Optional[int] = Field(default=None, description="Exit status code")
    workspace_id: str = Field(..., description="Workspace environment identifier")
    environment_fingerprint: str = Field(..., description="Fingerprint hash of workspace/host environment")
    status: RunStatus = Field(default=RunStatus.RUNNING, description="Current status of run attempt")
    failure_code: Optional[str] = Field(default=None, description="Structured ErrorCode if failed")
    failure_reason: Optional[str] = Field(default=None, description="Detailed failure description if failed")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
