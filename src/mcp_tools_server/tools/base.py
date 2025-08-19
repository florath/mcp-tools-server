"""Base class for all tools."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel


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
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get tool information."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters_schema()
        }
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        pass