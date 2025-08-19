"""Main entry point for MCP Tools Server."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from pythonjsonlogger import jsonlogger

from .core.config import load_config
from .core.server import MCPToolsServer


def setup_logging(config):
    """Setup logging configuration."""
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    
    if config.logging.format == "json":
        logHandler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter()
        logHandler.setFormatter(formatter)
        logger = logging.getLogger()
        logger.addHandler(logHandler)
        logger.setLevel(log_level)
    else:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Tools Server")
    parser.add_argument(
        "--config", 
        default="config/server_config.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--host",
        help="Override host from config"
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override port from config"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Override config with command line args
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting MCP Tools Server on {config.server.host}:{config.server.port}")
    logger.info(f"Security: {len(config.security.allowed_directories)} allowed directories")
    
    # Create server
    try:
        mcp_server = MCPToolsServer(config)
        logger.info(f"Server created successfully")
        
        # Run server
        uvicorn.run(
            mcp_server.app,
            host=config.server.host,
            port=config.server.port,
            log_level="debug" if config.server.debug else "info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()