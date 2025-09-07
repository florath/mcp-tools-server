"""FastAPI server setup and routing."""

import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Config
from .session import SessionManager
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
        
        # Initialize session manager
        self.session_manager = SessionManager(
            timeout_seconds=config.sessions.timeout_seconds,
            max_sessions=config.sessions.max_sessions
        )
        
        # Initialize security validator
        self.security_validator = SecurityValidator(config.security)
        
        # Initialize tool registry
        self.tool_registry = ToolRegistry(config, self.security_validator)
        
        self._setup_middleware()
        self._setup_routes()
        self._setup_exception_handlers()
        self._setup_startup_events()
    
    def _setup_middleware(self):
        """Setup middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure as needed
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add session middleware
        @self.app.middleware("http")
        async def session_middleware(request: Request, call_next):
            # Extract session ID from headers
            session_id = request.headers.get("X-MCP-Session-ID")
            
            if session_id:
                # Look up session directory
                session_directory = await self.session_manager.get_session_directory(session_id)
                if session_directory:
                    logger.debug(f"Setting session directory for request: {session_directory}")
                    # Set session directory on security validator for this request
                    self.security_validator.set_session_directory(session_directory)
                else:
                    logger.warning(f"Session not found or expired: {session_id}")
            
            try:
                response = await call_next(request)
                return response
            finally:
                # Clean up session context after request
                if session_id:
                    self.security_validator.set_session_directory(None)
    
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
        
        # Register session management routes
        self._setup_session_routes()
        
        # Register tool routes
        for tool_name, tool_instance in self.tool_registry.tools.items():
            self._register_tool_route(tool_name, tool_instance)
    
    def _setup_session_routes(self):
        """Setup session management routes."""
        
        @self.app.post("/sessions")
        async def create_session(request: Request):
            """Create a new session."""
            try:
                params = await request.json()
                directory = params.get("directory")
                
                if not directory:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "directory parameter is required"}
                    )
                
                session_id = await self.session_manager.create_session(directory)
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "directory": directory,
                    "message": f"Session created successfully: {session_id}"
                }
                
            except Exception as e:
                logger.error(f"Error creating session: {e}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": str(e)
                    }
                )
        
        @self.app.get("/sessions/stats")
        async def get_session_stats():
            """Get session manager statistics."""
            try:
                stats = await self.session_manager.get_stats()
                
                return {
                    "success": True,
                    "stats": stats
                }
                
            except Exception as e:
                logger.error(f"Error getting session stats: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Internal server error"
                    }
                )
        
        @self.app.get("/sessions/{session_id}")
        async def get_session(session_id: str):
            """Get session information."""
            try:
                session = await self.session_manager.get_session(session_id)
                
                if not session:
                    return JSONResponse(
                        status_code=404,
                        content={"error": f"Session not found: {session_id}"}
                    )
                
                return {
                    "success": True,
                    "session_id": session.session_id,
                    "directory": str(session.directory),
                    "created_at": session.created_at.isoformat(),
                    "last_accessed": session.last_accessed.isoformat(),
                    "age_seconds": (session.last_accessed - session.created_at).total_seconds()
                }
                
            except Exception as e:
                logger.error(f"Error getting session {session_id}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Internal server error"
                    }
                )
        
        @self.app.delete("/sessions/{session_id}")
        async def delete_session(session_id: str):
            """Delete a session."""
            try:
                removed = await self.session_manager.remove_session(session_id)
                
                if not removed:
                    return JSONResponse(
                        status_code=404,
                        content={"error": f"Session not found: {session_id}"}
                    )
                
                return {
                    "success": True,
                    "message": f"Session deleted successfully: {session_id}"
                }
                
            except Exception as e:
                logger.error(f"Error deleting session {session_id}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Internal server error"
                    }
                )
        
        @self.app.get("/sessions")
        async def list_sessions():
            """List all active sessions."""
            try:
                sessions = await self.session_manager.list_sessions()
                
                return {
                    "success": True,
                    "sessions": sessions,
                    "total_count": len(sessions)
                }
                
            except Exception as e:
                logger.error(f"Error listing sessions: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Internal server error"
                    }
                )
    
    def _register_tool_route(self, tool_name: str, tool_instance: Any):
        """Register route for a specific tool."""
        
        @self.app.post(f"/{tool_name}/v1")
        async def tool_endpoint(request: Request, params: Dict[str, Any] = None):
            """Generic tool endpoint."""
            try:
                if params is None:
                    params = await request.json()
                
                # Extract and validate reason field
                reason = params.get("reason", "")
                if not reason or len(reason.strip()) < 10:
                    raise ValueError(f"Tool call missing or insufficient reason. Please provide a clear explanation (at least 10 characters) of why you need to use the {tool_name} tool.")
                
                # Log tool usage with reason
                logger.info(f"Tool {tool_name} called with reason: {reason}")
                logger.debug(f"Tool {tool_name} parameters: {params}")
                
                # Execute tool (reason is included in params but tools can ignore it)
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
                
                # Extract clean error message for LLM while logging full details
                clean_error, error_details = self._extract_clean_error_message(error_msg)
                
                if "Security error" in error_msg:
                    status_code = 403  # Forbidden
                    logger.warning(f"Security violation in tool {tool_name}: {error_details}")
                else:
                    status_code = 400  # Bad Request
                    logger.warning(f"Client error in tool {tool_name}: {error_details}")
                
                return JSONResponse(
                    status_code=status_code,
                    content={
                        "success": False,
                        "tool": tool_name,
                        "error": clean_error,
                        "details": error_details  # Full details for debugging
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
    
    def _extract_clean_error_message(self, error_msg: str) -> tuple[str, str]:
        """
        Extract clean LLM-friendly error message and detailed error for logging.
        
        Args:
            error_msg: Raw error message from tool execution
            
        Returns:
            Tuple of (clean_message_for_llm, detailed_message_for_logs)
        """
        # Extract the core error message by removing wrapper prefixes
        clean_msg = error_msg
        
        # Remove "Security error: " prefix but keep the actual error
        if clean_msg.startswith("Security error: "):
            clean_msg = clean_msg[16:]
        
        # Remove "File reading error: " prefix
        if clean_msg.startswith("File reading error: "):
            clean_msg = clean_msg[20:]
            
        # Remove "Path validation error: " prefix
        if clean_msg.startswith("Path validation error: "):
            clean_msg = clean_msg[24:]
            
        # Remove other common prefixes that add noise
        prefixes_to_remove = [
            "Filename validation error: ",
            "Directory validation error: ",
            "Directory path validation error: "
        ]
        
        for prefix in prefixes_to_remove:
            if clean_msg.startswith(prefix):
                clean_msg = clean_msg[len(prefix):]
                break
        
        # Common error message improvements for LLM clarity
        error_mappings = {
            # File/directory not found
            r"File does not exist: (.+)": r"File not found: \1",
            r"Directory does not exist: (.+)": r"Directory not found: \1", 
            
            # Path issues
            r"Path is not a file: (.+)": r"Path is a directory, not a file: \1",
            r"Path is not a directory: (.+)": r"Path is a file, not a directory: \1",
            
            # Permission issues
            r"File path not in allowed directories: (.+)": r"Access denied: \1 is outside allowed directory",
            r"Directory path not in allowed directories: (.+)": r"Access denied: \1 is outside allowed directory",
            
            # File size/extension issues
            r"File too large: (\d+) bytes": r"File too large (exceeds size limit)",
            r"File extension not allowed: (.+)": r"File type not allowed: \1",
            
            # Generic security issues
            r"Hidden files not allowed": r"Cannot access hidden files",
            r"Path traversal not allowed": r"Invalid path (contains '..')"
        }
        
        import re
        for pattern, replacement in error_mappings.items():
            clean_msg = re.sub(pattern, replacement, clean_msg)
        
        return clean_msg.strip(), error_msg
    
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
    
    def _setup_startup_events(self):
        """Setup startup and shutdown events."""
        
        @self.app.on_event("startup")
        async def startup_event():
            """Initialize resources when server starts."""
            await self.session_manager.start()
            logger.info("MCP Tools Server startup completed")
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Cleanup resources when server shuts down."""
            await self.session_manager.shutdown()
            logger.info("MCP Tools Server shutdown completed")
    
    async def shutdown(self):
        """Shutdown the server and cleanup resources."""
        await self.session_manager.shutdown()
        logger.info("MCP Tools Server shutdown completed")
