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
        schema = self.get_parameters_schema()
        
        # Add reason field to all tool schemas to enforce thoughtful usage
        if "properties" not in schema:
            schema["properties"] = {}
        
        schema["properties"]["reason"] = {
            "type": "string",
            "description": "Clear explanation of why you need to use this tool and what you hope to accomplish",
            "minLength": 10
        }
        
        # Add reason to required fields
        if "required" not in schema:
            schema["required"] = []
        if "reason" not in schema["required"]:
            schema["required"].append("reason")
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": schema
        }
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        pass