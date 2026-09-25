"""
LLMorch Data Contracts - Error Taxonomy & Exception Foundation
"""

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(str, Enum):
    """Structured error codes for failure classification and failover routing."""
    AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    AGENT_PROCESS_FAILURE = "AGENT_PROCESS_FAILURE"
    AUTH_FAILURE = "AUTH_FAILURE"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"
    WORKSPACE_FAILURE = "WORKSPACE_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class LLMorchError(Exception):
    """Base exception for all LLMorch failures."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.UNKNOWN_FAILURE, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.code.value,
            "message": self.message,
            "details": self.details,
        }


class AgentUnavailableError(LLMorchError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=ErrorCode.AGENT_UNAVAILABLE, details=details)


class QuotaExhaustedError(LLMorchError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=ErrorCode.QUOTA_EXHAUSTED, details=details)


class AdapterError(LLMorchError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=ErrorCode.ADAPTER_FAILURE, details=details)


class InvalidStateTransitionError(LLMorchError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=ErrorCode.INVALID_STATE_TRANSITION, details=details)


class PolicyBlockedError(LLMorchError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=ErrorCode.POLICY_BLOCKED, details=details)


class AgentExecutionDisabled(LLMorchError):
    """Raised when an agent is registered but execution is prohibited by policy."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=ErrorCode.POLICY_BLOCKED, details=details)


AgentExecutionDisabledError = AgentExecutionDisabled

