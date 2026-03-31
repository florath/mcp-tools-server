"""
Programmatic API for MCP Tools Server.

Provides clean start/stop/status functions for embedding the server
in other applications without subprocess management.
"""

import asyncio
import logging
import socket
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import uvicorn
from uvicorn.config import Config as UvicornConfig

from .core.config import Config, ServerConfig, SecurityConfig, LoggingConfig, ToolsConfig
from .core.server import MCPToolsServer


class MCPServerManager:
    """
    Manages MCP Tools Server lifecycle programmatically.
    
    Provides clean start/stop/status interface without subprocess management.
    """
    
    def __init__(self):
        self.server_thread: Optional[threading.Thread] = None
        self.server_task: Optional[asyncio.Task] = None
        self.uvicorn_server: Optional[uvicorn.Server] = None
        self.config: Optional[Config] = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    def start_server(
        self,
        port: int,
        host: str = "127.0.0.1",
        max_file_size_mb: int = 100,
        debug: bool = False,
        log_level: str = "INFO"
    ) -> bool:
        """
        Start MCP Tools Server programmatically.


        Args:
            port: Port to run server on
            host: Host to bind to (default: 127.0.0.1)
            max_file_size_mb: Maximum file size limit
            debug: Enable debug mode
            log_level: Logging level

        Returns:
            True if server started successfully, False otherwise
        """
        if self._running:
            self.logger.warning("Server is already running")
            return False
            
        # Check if port is available
        if not self._is_port_available(host, port):
            self.logger.error(f"Port {port} is already in use")
            return False
            
        try:
            # Create configuration
            self.config = Config(
                server=ServerConfig(
                    host=host,
                    port=port,
                    debug=debug
                ),
                security=SecurityConfig(
                    max_file_size_mb=max_file_size_mb,
                    allowed_file_extensions=[
                        ".json", ".yaml", ".yml", ".txt", ".py", ".js", ".ts",
                        ".md", ".csv", ".xml", ".html", ".css", ".sql", ".toml",
                        ".cfg", ".ini", ".conf", ".sh", ".bat", ".dockerfile",
                        ".dockerignore", ".gitignore", ".env", ".lock"
                    ]
                ),
                logging=LoggingConfig(
                    level=log_level,
                    format="standard"  # Use standard format for programmatic use
                ),
                tools=ToolsConfig()
            )
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self._run_server_thread,
                daemon=True
            )
            self.server_thread.start()
            
            # Wait for server to start
            max_wait = 10  # seconds
            for _ in range(max_wait * 10):  # Check every 100ms
                if self._running:
                    self.logger.info(f"MCP Tools Server started on {host}:{port}")
                    return True
                time.sleep(0.1)
                
            self.logger.error("Server failed to start within timeout")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            return False
    
    def stop_server(self, timeout: float = 10.0) -> bool:
        """
        Stop MCP Tools Server gracefully.
        
        Args:
            timeout: Maximum time to wait for graceful shutdown
            
        Returns:
            True if server stopped successfully, False otherwise
        """
        if not self._running:
            self.logger.warning("Server is not running")
            return True
            
        try:
            # Signal server to stop
            self._running = False
            
            # Cancel server task if running
            if self.uvicorn_server:
                self.uvicorn_server.should_exit = True
                
            # Wait for server thread to finish
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=timeout)
                
                if self.server_thread.is_alive():
                    self.logger.warning("Server thread did not terminate gracefully")
                    return False
                    
            self.server_thread = None
            self.uvicorn_server = None
            self.config = None
            self._loop = None
            
            self.logger.info("MCP Tools Server stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop server: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current server status and configuration.
        
        Returns:
            Dictionary with server status information
        """
        if not self._running or not self.config:
            return {
                "running": False,
                "config": None
            }
            
        return {
            "running": True,
            "config": {
                "host": self.config.server.host,
                "port": self.config.server.port,
                "max_file_size_mb": self.config.security.max_file_size_mb,
                "debug": self.config.server.debug,
            }
        }
    
    def is_running(self) -> bool:
        """Check if server is currently running."""
        return self._running and self.server_thread is not None and self.server_thread.is_alive()
    
    def _run_server_thread(self):
        """Run server in background thread with its own event loop."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Create MCP server
            mcp_server = MCPToolsServer(self.config)
            
            # Create Uvicorn server config
            uvicorn_config = UvicornConfig(
                app=mcp_server.app,
                host=self.config.server.host,
                port=self.config.server.port,
                log_level="debug" if self.config.server.debug else "info",
                access_log=False,  # Disable access log for cleaner output
                loop="asyncio"
            )
            
            # Create and start Uvicorn server
            self.uvicorn_server = uvicorn.Server(uvicorn_config)
            self._running = True
            
            # Run server
            self._loop.run_until_complete(self.uvicorn_server.serve())
            
        except Exception as e:
            self.logger.error(f"Server thread error: {e}")
        finally:
            self._running = False
            if self._loop:
                self._loop.close()
    
    def _is_port_available(self, host: str, port: int) -> bool:
        """Check if a port is available for binding."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                return True
        except OSError:
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure server is stopped."""
        if self.is_running():
            self.stop_server()


@asynccontextmanager
async def managed_mcp_server(
    port: int,
    host: str = "127.0.0.1",
    **kwargs
):
    """
    Async context manager for MCP Tools Server.


    Args:
        port: Port to run server on
        host: Host to bind to
        **kwargs: Additional server configuration

    Yields:
        MCPServerManager instance with running server

    Example:
        async with managed_mcp_server(7092) as server:
            status = server.get_status()
        # Server is automatically stopped
    """
    manager = MCPServerManager()
    try:
        success = manager.start_server(port, host, **kwargs)
        if not success:
            raise RuntimeError("Failed to start MCP server")
        yield manager
    finally:
        manager.stop_server()


def find_available_port(start_port: int = 7091, max_attempts: int = 100) -> Optional[int]:
    """
    Find an available port starting from the given port.
    
    Args:
        start_port: Starting port number to check
        max_attempts: Maximum number of ports to try
        
    Returns:
        Available port number or None if none found
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return None