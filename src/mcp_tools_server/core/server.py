"""FastAPI server setup and routing."""

import json
import logging
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Config
from .session import SessionManager
from .structured_logger import logger
from ..security.validator import SecurityValidator
from ..tools.registry import ToolRegistry


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

        # MCP session map: mcp_session_id -> rest_session_id
        self._mcp_sessions: Dict[str, str] = {}
        
        # Track registered capabilities per session


        self._setup_middleware()
        self._setup_routes()
        self._setup_mcp_routes()
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

            token = None
            if session_id:
                # Look up session directory
                session_directory = await self.session_manager.get_session_directory(session_id)
                if session_directory:
                    logger.debug(f"Setting session directory for request: {session_directory}")
                    token = self.security_validator.set_session_directory(session_directory)
                else:
                    logger.warning(f"Session not found or expired: {session_id}")

            try:
                response = await call_next(request)
                return response
            finally:
                # Restore previous session context (ContextVar token-based reset)
                if token is not None:
                    self.security_validator.reset_session_directory(token)
    
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
            """Get schema for a specific tool (MCP client format for backward compatibility)."""
            tool_instance = self.tool_registry.get_tool(tool_name)
            if not tool_instance:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

            # Return in the format expected by MCP client (backward compat)
            openai_schema = tool_instance.get_openai_function_schema()
            function_data = openai_schema["function"]

            return {
                "tool_name": function_data["name"],
                "description": function_data["description"],
                "endpoint": f"/{tool_name}/v1",
                "method": "POST",
                "parameters_schema": function_data["parameters"],
                "example_request": self._get_example_request(tool_name, tool_instance),
            }

        @self.app.get("/tools/schemas")
        async def get_openai_tool_schemas():
            """
            Get tool schemas in OpenAI function calling format.

            Returns schemas compatible with vLLM native tool calling API.
            Each tool is represented as a function with JSON schema parameters.
            """
            tools = []
            for name, tool_instance in self.tool_registry.tools.items():
                tools.append(tool_instance.get_openai_function_schema())

            return {
                "tools": tools,
                "total_count": len(tools),
                "format": "openai_function_calling",
                "usage": "Pass the 'tools' array to vLLM /v1/chat/completions endpoint with tool_choice parameter"
            }

        # Register session management routes
        self._setup_session_routes()
        
        # Register tool routes
        for tool_name, tool_instance in self.tool_registry.tools.items():
            self._register_tool_route(tool_name, tool_instance)
    
    def _setup_mcp_routes(self):
        """Setup MCP JSON-RPC 2.0 endpoint for Streamable HTTP transport.
        
        Handles POST / (the URL configured in codex) as well as POST /mcp
        (the conventional MCP endpoint path).  Both paths share the same handler.
        """

        async def _mcp_handler(request: Request) -> JSONResponse:
            """Handle MCP JSON-RPC requests."""
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    status_code=400,
                    content={"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": "Parse error"}},
                )

            method: str = body.get("method", "")
            msg_id = body.get("id")          # None for notifications
            params: Dict[str, Any] = body.get("params") or {}
            mcp_session_id: Optional[str] = request.headers.get("mcp-session-id")

            # --- initialize ---
            if method == "initialize":
                new_mcp_session_id = str(uuid.uuid4())

                # If the caller passes a custom rootDirectory, create a REST session for it
                root_directory: Optional[str] = params.get("rootDirectory") or params.get("_directory")
                if root_directory:
                    try:
                        rest_session_id = await self.session_manager.create_session(root_directory)
                        self._mcp_sessions[new_mcp_session_id] = rest_session_id
                        logger.debug(f"MCP session {new_mcp_session_id} linked to REST session {rest_session_id} for {root_directory}")
                    except Exception as exc:
                        logger.warning(f"Could not create REST session for rootDirectory '{root_directory}': {exc}")

                # Also accept an explicit X-MCP-Session-ID header on initialize
                linked_rest_session = request.headers.get("X-MCP-Session-ID")
                if linked_rest_session and new_mcp_session_id not in self._mcp_sessions:
                    self._mcp_sessions[new_mcp_session_id] = linked_rest_session

                response_body = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "MCP Tools Server", "version": "0.1.0"},
                    },
                }
                resp = JSONResponse(content=response_body)
                resp.headers["mcp-session-id"] = new_mcp_session_id
                return resp

            # --- tools/list ---
            if method == "tools/list":
                tools = []
                for name, tool_instance in self.tool_registry.tools.items():
                    schema = tool_instance.get_parameters_schema()
                    tools.append({
                        "name": name,
                        "description": tool_instance.description,
                        "inputSchema": schema,
                    })
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": tools},
                })

            # --- tools/call ---
            if method == "tools/call":
                tool_name: str = params.get("name", "")
                arguments: Dict[str, Any] = params.get("arguments") or {}

                logger.info(f"MCP tools/call: {tool_name}",
                           tool_name=tool_name,
                           operation="mcp_tool_call",
                           params=arguments)

                tool_instance = self.tool_registry.get_tool(tool_name)
                if tool_instance is None:
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32602, "message": f"Tool not found: {tool_name}"},
                    })

                # Resolve session directory for this MCP session and activate it
                # so the security validator scopes access correctly.
                sec_token = None
                if mcp_session_id and mcp_session_id in self._mcp_sessions:
                    rest_session_id = self._mcp_sessions[mcp_session_id]
                    session_dir = await self.session_manager.get_session_directory(rest_session_id)
                    if session_dir:
                        sec_token = self.security_validator.set_session_directory(session_dir)

                try:
                    result = await tool_instance.execute(arguments)
                    content_text = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": content_text}]},
                    })
                except Exception as exc:
                    logger.warning(f"MCP tools/call error for '{tool_name}': {exc}")
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(exc)},
                    })
                finally:
                    if sec_token is not None:
                        self.security_validator.reset_session_directory(sec_token)

            # --- notifications (no response body needed) ---
            if msg_id is None:
                return JSONResponse(status_code=202, content={})

            # --- unknown method ---
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })

        # Register at both the root path (matches the current codex config URL)
        # and the conventional /mcp path.
        self.app.add_api_route("/", _mcp_handler, methods=["POST"])
        self.app.add_api_route("/mcp", _mcp_handler, methods=["POST"])
    
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
                
                # Extract session ID from headers
                session_id = request.headers.get("X-MCP-Session-ID")
                
                # Debug logging: log complete request
                logger.debug(f"Tool {tool_name} request", 
                           tool_name=tool_name, 
                           operation="tool_request",
                           params=params,
                           session_id=session_id)
                
                # Extract reason field (optional, but logged if provided)
                reason = params.get("reason", "")
                if reason and len(reason.strip()) < 10:
                    # Warn but don't reject if reason is too short
                    logger.warning(f"Tool {tool_name} called with insufficient reason: '{reason}' ({len(reason)} chars)")
                
                # Log tool usage with reason
                # Tool call logging is now handled by individual tools in their execute method
                
                # Set session ID on tool for logging
                if hasattr(tool_instance, 'set_session_id') and session_id:
                    tool_instance.set_session_id(session_id)
                
                # Execute tool (reason is included in params but tools can ignore it)
                result = await tool_instance.execute(params)
                
                response = {
                    "success": True,
                    "tool": tool_name,
                    "result": result
                }
                
                # Debug logging: log complete response
                logger.debug(f"Tool {tool_name} response",
                           tool_name=tool_name,
                           operation="tool_response", 
                           result=response,
                           session_id=session_id)
                
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
