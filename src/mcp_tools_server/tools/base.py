"""Base class for all tools."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel
from ..core.structured_logger import logger


class ToolRequest(BaseModel):
    """Base request model for tools."""
    pass


class ToolResponse(BaseModel):
    """Base response model for tools."""
    success: bool = True
    data: Any = None
    error: str = None


class BaseTool(ABC):
    """Base class for all MCP tools."""
    
    def __init__(self, name: str, description: str, security_validator=None):
        self.name = name
        self.description = description
        self.security_validator = security_validator
        self._current_session_id: Optional[str] = None
    
    def set_session_id(self, session_id: str) -> None:
        """Set the current session ID for logging."""
        self._current_session_id = session_id
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        pass
    
    def log_tool_call(self, params: Dict[str, Any]) -> None:
        """Log tool call with complete parameters."""
        reason = params.get('reason', 'No reason provided')
        logger.tool_call(
            tool_name=self.name,
            params=params,
            session_id=self._current_session_id,
            reason=reason
        )
    
    def log_tool_result(self, result: Any, duration_ms: Optional[float] = None) -> None:
        """Log tool result."""
        logger.tool_result(
            tool_name=self.name,
            result=result,
            duration_ms=duration_ms,
            session_id=self._current_session_id
        )
    
    def log_tool_error(self, error: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Log tool error."""
        logger.tool_error(
            tool_name=self.name,
            error=error,
            params=params,
            session_id=self._current_session_id
        )
    
    def log_security_violation(self, violation_type: str, details: Dict[str, Any]) -> None:
        """Log security violation."""
        logger.security_violation(
            tool_name=self.name,
            violation_type=violation_type,
            details=details,
            session_id=self._current_session_id
        )
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        pass

    def get_openai_function_schema(self) -> Dict[str, Any]:
        """
        Get tool schema in OpenAI function calling format.

        Converts MCP tool schema to OpenAI-compatible function schema
        for use with vLLM native tool calling.

        Returns:
            Dict containing OpenAI function schema with type, name, description, and parameters
        """
        # Get base parameters schema
        parameters_schema = self.get_parameters_schema().copy()

        # Add reason field to all tool schemas to enforce thoughtful usage
        if "properties" not in parameters_schema:
            parameters_schema["properties"] = {}

        parameters_schema["properties"]["reason"] = {
            "type": "string",
            "description": "Clear explanation of why you are calling this tool and what you intend to achieve.",
            "minLength": 10,
        }

        # Add reason to required fields
        if "required" not in parameters_schema:
            parameters_schema["required"] = []
        if "reason" not in parameters_schema["required"]:
            parameters_schema["required"].append("reason")

        # Return OpenAI function calling format
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters_schema
            }
        }
    
    def _normalize_path_for_response(self, path: Path) -> str:
        """
        Convert an absolute path to a relative path for tool responses.
        ALWAYS returns relative paths to maintain session isolation.
        """
        if not self.security_validator:
            return str(path)
        
        base_dir = self.security_validator.get_effective_base_directory()

        if base_dir:
            try:
                relative_path = str(path.relative_to(base_dir))
                return relative_path if relative_path != "." else "."
            except ValueError:
                # Path is not under base directory - return just the filename
                return path.name
        else:
            # No base directory available - return just the filename
            return path.name

    def get_info(self) -> Dict[str, Any]:
        """Get basic information about the tool for registry purposes."""
        return {
            "name": self.name,
            "description": self.description,
            "schema_endpoint": f"/tools/{self.name}/schema",
        }
