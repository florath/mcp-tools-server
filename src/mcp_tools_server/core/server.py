"""FastAPI server setup and routing."""

import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Config
from ..security.validator import SecurityValidator
from ..tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


class MCPToolsServer:
    """Main MCP tools server."""
    
    def __init__(self, config: Config):
        self.config = config
        self.app = FastAPI(
            title="MCP Tools Server",
            description="Secure HTTP server for meta-cognitive agent tools",
            version="0.1.0",
            debug=config.server.debug
        )
        
        # Initialize security validator
        self.security_validator = SecurityValidator(config.security)
        
        # Initialize tool registry
        self.tool_registry = ToolRegistry(config, self.security_validator)
        
        self._setup_middleware()
        self._setup_routes()
        self._setup_exception_handlers()
    
    def _setup_middleware(self):
        """Setup middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure as needed
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup routes for all tools."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint with server info."""
            return {
                "name": "MCP Tools Server",
                "version": "0.1.0",
                "status": "running",
                "available_tools": list(self.tool_registry.get_available_tools())
            }
        
        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy", "tools_loaded": len(self.tool_registry.tools)}
        
        @self.app.get("/tools")
        async def list_tools():
            """List all available tools with basic info."""
            tools = []
            for name, tool_instance in self.tool_registry.tools.items():
                tools.append({
                    "name": name,
                    "description": tool_instance.description,
                    "endpoint": f"/{name}/v1",
                    "method": "POST",
                    "schema_endpoint": f"/tools/{name}/schema"
                })
            return {
                "tools": tools,
                "total_count": len(tools)
            }
        
        @self.app.get("/tools/{tool_name}/schema")
        async def get_tool_schema(tool_name: str):
            """Get detailed schema for a specific tool."""
            tool_instance = self.tool_registry.get_tool(tool_name)
            if not tool_instance:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
            
            return {
                "tool_name": tool_name,
                "description": tool_instance.description,
                "endpoint": f"/{tool_name}/v1",
                "method": "POST",
                "parameters_schema": tool_instance.get_parameters_schema(),
                "example_request": self._get_example_request(tool_name, tool_instance),
                "security_info": self.security_validator.get_security_info() if hasattr(self, 'security_validator') else None
            }
        
        @self.app.get("/tools/schemas")
        async def get_all_tool_schemas():
            """Get schemas for all tools (convenient for LLMs)."""
            schemas = {}
            for name, tool_instance in self.tool_registry.tools.items():
                schemas[name] = {
                    "description": tool_instance.description,
                    "endpoint": f"/{name}/v1",
                    "method": "POST",
                    "parameters_schema": tool_instance.get_parameters_schema(),
                    "example_request": self._get_example_request(name, tool_instance)
                }
            
            return {
                "schemas": schemas,
                "server_info": {
                    "base_url": f"http://{self.config.server.host}:{self.config.server.port}",
                    "security_info": self.security_validator.get_security_info()
                },
                "usage_instructions": "Send POST requests to the tool endpoints with JSON parameters matching the schema"
            }
        
        # Register tool routes
        for tool_name, tool_instance in self.tool_registry.tools.items():
            self._register_tool_route(tool_name, tool_instance)
    
    def _register_tool_route(self, tool_name: str, tool_instance: Any):
        """Register route for a specific tool."""
        
        @self.app.post(f"/{tool_name}/v1")
        async def tool_endpoint(request: Request, params: Dict[str, Any] = None):
            """Generic tool endpoint."""
            try:
                if params is None:
                    params = await request.json()
                
                logger.info(f"Tool {tool_name} called with params: {params}")
                
                # Execute tool
                result = await tool_instance.execute(params)
                
                response = {
                    "success": True,
                    "tool": tool_name,
                    "result": result
                }
                
                # Log first 500 characters of response
                response_str = str(response)
                logger.info(f"Response for {tool_name} (first 500 chars): {response_str[:500]}")
                
                return response
                
            except ValueError as e:
                # Handle client errors (invalid parameters, security violations)
                error_msg = str(e)
                if "Security error" in error_msg:
                    status_code = 403  # Forbidden
                    logger.warning(f"Security violation in tool {tool_name}: {e}")
                else:
                    status_code = 400  # Bad Request
                    logger.warning(f"Client error in tool {tool_name}: {e}")
                
                return JSONResponse(
                    status_code=status_code,
                    content={
                        "success": False,
                        "tool": tool_name,
                        "error": error_msg
                    }
                )
            except Exception as e:
                # Handle unexpected server errors
                logger.error(f"Internal error executing tool {tool_name}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "tool": tool_name,
                        "error": "Internal server error"
                    }
                )
        
        # Set the endpoint name dynamically
        tool_endpoint.__name__ = f"{tool_name}_endpoint"
    
    def _get_example_request(self, tool_name: str, tool_instance: Any) -> Dict[str, Any]:
        """Generate example request for a tool."""
        if tool_name == "file_reader":
            return {
                "file_path": "/tmp/workspace/example.json",
                "encoding": "utf-8",
                "include_line_numbers": True
            }
        
        # Default example for other tools
        schema = tool_instance.get_parameters_schema()
        example = {}
        
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                if prop_schema.get("type") == "string":
                    if "default" in prop_schema:
                        example[prop_name] = prop_schema["default"]
                    else:
                        example[prop_name] = f"example_{prop_name}"
                elif prop_schema.get("type") == "boolean":
                    example[prop_name] = prop_schema.get("default", False)
                elif prop_schema.get("type") == "integer":
                    example[prop_name] = prop_schema.get("default", 10)
                elif prop_schema.get("type") == "array":
                    example[prop_name] = []
        
        return example
    
    def _setup_exception_handlers(self):
        """Setup global exception handlers."""
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail, "status_code": exc.status_code}
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled exception: {exc}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )
