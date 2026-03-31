"""Session management for MCP tools server."""

import asyncio
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone


from ..core.structured_logger import logger


@dataclass
class Session:
    """Represents an active session."""
    session_id: str
    directory: Path
    created_at: datetime
    last_accessed: datetime
    
    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_accessed).total_seconds()
        return elapsed > timeout_seconds
    
    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = datetime.now(timezone.utc)


class SessionError(Exception):
    """Session management error."""
    pass


class SessionManager:
    """Manages MCP server sessions for stage isolation."""
    
    def __init__(self, timeout_seconds: int = 3600, max_sessions: int = 100):
        """
        Initialize session manager.
        
        Args:
            timeout_seconds: Session timeout in seconds (default: 1 hour)
            max_sessions: Maximum concurrent sessions (default: 100)
        """
        self.timeout_seconds = timeout_seconds
        self.max_sessions = max_sessions
        self.sessions: Dict[str, Session] = {}
        self._lock = None  # Will be created when event loop is running
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False
    
    async def start(self) -> None:
        """Start the session manager (must be called when event loop is running)."""
        if self._started:
            return
            
        self._lock = asyncio.Lock()
        self._start_cleanup_task()
        self._started = True
        logger.info("Session manager started")
    
    def _start_cleanup_task(self) -> None:
        """Start background task for session cleanup."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
    
    async def _cleanup_expired_sessions(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._remove_expired_sessions()
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")
    
    async def _remove_expired_sessions(self) -> None:
        """Remove expired sessions from memory."""
        async with self._lock:
            expired_sessions = []
            for session_id, session in self.sessions.items():
                if session.is_expired(self.timeout_seconds):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                logger.info(f"Removing expired session: {session_id}")
                del self.sessions[session_id]
    
    async def _ensure_started(self) -> None:
        """Ensure session manager is started."""
        if not self._started:
            await self.start()
    
    async def create_session(self, directory: str) -> str:
        """
        Create a new session.
        
        Args:
            directory: Directory path for the session
            
        Returns:
            Session ID (UUID string)
            
        Raises:
            SessionError: If session creation fails
        """
        await self._ensure_started()
        async with self._lock:
            if len(self.sessions) >= self.max_sessions:
                # Try to clean up expired sessions first
                await self._remove_expired_sessions()
                if len(self.sessions) >= self.max_sessions:
                    raise SessionError(f"Maximum number of sessions reached: {self.max_sessions}")
            
            session_id = str(uuid.uuid4())
            session_dir = Path(directory).resolve()
            
            # Validate directory exists
            if not session_dir.exists() or not session_dir.is_dir():
                raise SessionError(f"Session directory does not exist or is not a directory: {directory}")
            
            now = datetime.now(timezone.utc)
            session = Session(
                session_id=session_id,
                directory=session_dir,
                created_at=now,
                last_accessed=now
            )
            
            self.sessions[session_id] = session
            logger.info(f"Created session {session_id} for directory: {session_dir}")
            
            return session_id
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.
        
        Args:
            session_id: Session ID to lookup
            
        Returns:
            Session object if found and not expired, None otherwise
        """
        await self._ensure_started()
        async with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            
            if session.is_expired(self.timeout_seconds):
                logger.info(f"Session {session_id} has expired, removing")
                del self.sessions[session_id]
                return None
            
            # Update last accessed time
            session.touch()
            return session
    
    async def get_session_directory(self, session_id: str) -> Optional[Path]:
        """
        Get session directory by ID.
        
        Args:
            session_id: Session ID to lookup
            
        Returns:
            Session directory Path if session exists and is valid, None otherwise
        """
        session = await self.get_session(session_id)
        return session.directory if session else None
    
    async def remove_session(self, session_id: str) -> bool:
        """
        Remove session by ID.
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            True if session was removed, False if it didn't exist
        """
        await self._ensure_started()
        async with self._lock:
            if session_id in self.sessions:
                logger.info(f"Removing session: {session_id}")
                del self.sessions[session_id]
                return True
            return False
    
    async def list_sessions(self) -> Dict[str, Dict]:
        """
        List all active sessions.
        
        Returns:
            Dictionary mapping session IDs to session info
        """
        await self._ensure_started()
        async with self._lock:
            # Clean up expired sessions first
            await self._remove_expired_sessions()
            
            result = {}
            for session_id, session in self.sessions.items():
                result[session_id] = {
                    "session_id": session_id,
                    "directory": str(session.directory),
                    "created_at": session.created_at.isoformat(),
                    "last_accessed": session.last_accessed.isoformat(),
                    "age_seconds": (datetime.now(timezone.utc) - session.created_at).total_seconds()
                }
            
            return result
    
    async def get_stats(self) -> Dict:
        """
        Get session manager statistics.
        
        Returns:
            Dictionary with session statistics
        """
        await self._ensure_started()
        async with self._lock:
            await self._remove_expired_sessions()
            
            return {
                "active_sessions": len(self.sessions),
                "max_sessions": self.max_sessions,
                "timeout_seconds": self.timeout_seconds,
                "cleanup_task_running": not (self._cleanup_task is None or self._cleanup_task.done())
            }
    
    async def shutdown(self) -> None:
        """Shutdown session manager and cleanup resources."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._lock:
            async with self._lock:
                self.sessions.clear()
        else:
            self.sessions.clear()
        
        self._started = False
        logger.info("Session manager shutdown completed")