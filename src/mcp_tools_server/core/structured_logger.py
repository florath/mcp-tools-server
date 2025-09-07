"""Structured logging for MCP Tools Server with consistent JSON format."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'tool_name'):
            log_entry["tool"] = record.tool_name
        if hasattr(record, 'session_id'):
            log_entry["session_id"] = record.session_id
        if hasattr(record, 'operation'):
            log_entry["operation"] = record.operation
        if hasattr(record, 'params'):
            log_entry["parameters"] = record.params
        if hasattr(record, 'result'):
            log_entry["result"] = record.result
        if hasattr(record, 'error'):
            log_entry["error"] = record.error
        if hasattr(record, 'duration_ms'):
            log_entry["duration_ms"] = record.duration_ms
            
        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLogger:
    """Structured logger that outputs consistent JSON format logs."""
    
    def __init__(self, name: str = "mcp_tools_server"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Setup logger with JSON formatter."""
        if self.logger.handlers:
            return  # Already configured
            
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with optional structured data."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with optional structured data."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with optional structured data."""
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with optional structured data."""
        self.logger.debug(message, extra=kwargs)
    
    def tool_call(self, tool_name: str, params: Dict[str, Any], 
                  session_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        """Log tool call with complete parameters."""
        self.info(
            f"Tool {tool_name} called" + (f" - {reason}" if reason else ""),
            tool_name=tool_name,
            operation="tool_call",
            params=params,
            session_id=session_id
        )
    
    def tool_result(self, tool_name: str, result: Any, duration_ms: Optional[float] = None,
                   session_id: Optional[str] = None) -> None:
        """Log tool result."""
        self.info(
            f"Tool {tool_name} completed successfully",
            tool_name=tool_name,
            operation="tool_result",
            result=result,
            duration_ms=duration_ms,
            session_id=session_id
        )
    
    def tool_error(self, tool_name: str, error: str, params: Optional[Dict[str, Any]] = None,
                   session_id: Optional[str] = None) -> None:
        """Log tool error."""
        self.error(
            f"Tool {tool_name} failed: {error}",
            tool_name=tool_name,
            operation="tool_error",
            error=error,
            params=params,
            session_id=session_id
        )
    
    def security_violation(self, tool_name: str, violation_type: str, details: Dict[str, Any],
                          session_id: Optional[str] = None) -> None:
        """Log security violation."""
        self.warning(
            f"Security violation in tool {tool_name}: {violation_type}",
            tool_name=tool_name,
            operation="security_violation",
            error=violation_type,
            params=details,
            session_id=session_id
        )
    
    def session_event(self, event: str, session_id: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log session-related events."""
        self.info(
            f"Session {event}: {session_id}",
            operation="session_event",
            session_id=session_id,
            params=details or {}
        )
    
    def server_event(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log server-related events."""
        self.info(
            event,
            operation="server_event",
            params=details or {}
        )


# Global logger instance
logger = StructuredLogger()