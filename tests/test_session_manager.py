"""Tests for the SessionManager class."""

import asyncio
import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from src.mcp_tools_server.core.session import SessionManager, Session, SessionError


@pytest_asyncio.fixture
async def session_manager():
    """Create a session manager for testing."""
    manager = SessionManager(timeout_seconds=10, max_sessions=5)
    yield manager
    await manager.shutdown()


@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.mark.asyncio
class TestSessionManager:
    """Test cases for SessionManager."""
    
    async def test_create_session_success(self, session_manager, temp_directory):
        """Test successful session creation."""
        session_id = await session_manager.create_session(temp_directory)
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        
        session = await session_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
        assert str(session.directory) == str(Path(temp_directory).resolve())
    
    async def test_create_session_nonexistent_directory(self, session_manager):
        """Test session creation with nonexistent directory."""
        with pytest.raises(SessionError, match="Session directory does not exist"):
            await session_manager.create_session("/nonexistent/directory")
    
    async def test_create_session_file_instead_of_directory(self, session_manager):
        """Test session creation with file instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            with pytest.raises(SessionError, match="not a directory"):
                await session_manager.create_session(temp_file.name)
    
    async def test_get_session_not_found(self, session_manager):
        """Test getting a nonexistent session."""
        result = await session_manager.get_session("nonexistent-session-id")
        assert result is None
    
    async def test_get_session_directory(self, session_manager, temp_directory):
        """Test getting session directory."""
        session_id = await session_manager.create_session(temp_directory)
        
        directory = await session_manager.get_session_directory(session_id)
        assert directory is not None
        assert str(directory) == str(Path(temp_directory).resolve())
        
        # Test nonexistent session
        directory = await session_manager.get_session_directory("nonexistent")
        assert directory is None
    
    async def test_remove_session(self, session_manager, temp_directory):
        """Test session removal."""
        session_id = await session_manager.create_session(temp_directory)
        
        # Verify session exists
        session = await session_manager.get_session(session_id)
        assert session is not None
        
        # Remove session
        removed = await session_manager.remove_session(session_id)
        assert removed is True
        
        # Verify session no longer exists
        session = await session_manager.get_session(session_id)
        assert session is None
        
        # Try to remove non-existent session
        removed = await session_manager.remove_session(session_id)
        assert removed is False
    
    async def test_list_sessions(self, session_manager, temp_directory):
        """Test listing sessions."""
        # Initially no sessions
        sessions = await session_manager.list_sessions()
        assert len(sessions) == 0
        
        # Create sessions
        session_id1 = await session_manager.create_session(temp_directory)
        session_id2 = await session_manager.create_session(temp_directory)
        
        # List sessions
        sessions = await session_manager.list_sessions()
        assert len(sessions) == 2
        assert session_id1 in sessions
        assert session_id2 in sessions
        
        # Verify session info structure
        session_info = sessions[session_id1]
        assert "session_id" in session_info
        assert "directory" in session_info
        assert "created_at" in session_info
        assert "last_accessed" in session_info
        assert "age_seconds" in session_info
    
    async def test_max_sessions_limit(self, temp_directory):
        """Test maximum sessions limit."""
        manager = SessionManager(timeout_seconds=10, max_sessions=2)
        
        try:
            # Create maximum number of sessions
            session1 = await manager.create_session(temp_directory)
            session2 = await manager.create_session(temp_directory)
            
            # Try to create one more (should fail)
            with pytest.raises(SessionError, match="Maximum number of sessions reached"):
                await manager.create_session(temp_directory)
        finally:
            await manager.shutdown()
    
    async def test_session_expiry(self, temp_directory):
        """Test session expiry."""
        # Create manager with very short timeout
        manager = SessionManager(timeout_seconds=1, max_sessions=10)
        
        try:
            session_id = await manager.create_session(temp_directory)
            
            # Session should exist initially
            session = await manager.get_session(session_id)
            assert session is not None
            
            # Wait for expiry
            await asyncio.sleep(2)
            
            # Session should be expired
            session = await manager.get_session(session_id)
            assert session is None
        finally:
            await manager.shutdown()
    
    async def test_session_touch_updates_access_time(self, session_manager, temp_directory):
        """Test that accessing a session updates the last_accessed time."""
        session_id = await session_manager.create_session(temp_directory)
        
        # Get session and note access time
        session1 = await session_manager.get_session(session_id)
        first_access = session1.last_accessed
        
        # Wait a bit and access again
        await asyncio.sleep(0.1)
        session2 = await session_manager.get_session(session_id)
        second_access = session2.last_accessed
        
        # Access time should have been updated
        assert second_access > first_access
    
    async def test_session_stats(self, session_manager, temp_directory):
        """Test session statistics."""
        # Get initial stats
        stats = await session_manager.get_stats()
        assert stats["active_sessions"] == 0
        assert stats["max_sessions"] == 5
        assert stats["timeout_seconds"] == 10
        assert stats["cleanup_task_running"] is True
        
        # Create session and check stats
        session_id = await session_manager.create_session(temp_directory)
        stats = await session_manager.get_stats()
        assert stats["active_sessions"] == 1
    
    async def test_cleanup_task_removes_expired_sessions(self, temp_directory):
        """Test that the cleanup task removes expired sessions."""
        # Create manager with short timeout and cleanup interval
        manager = SessionManager(timeout_seconds=1, max_sessions=10)
        
        try:
            session_id = await manager.create_session(temp_directory)
            
            # Session should exist
            sessions = await manager.list_sessions()
            assert len(sessions) == 1
            
            # Wait for expiry and cleanup
            await asyncio.sleep(2)
            await manager._remove_expired_sessions()
            
            # Session should be cleaned up
            sessions = await manager.list_sessions()
            assert len(sessions) == 0
        finally:
            await manager.shutdown()


@pytest.mark.asyncio
class TestSession:
    """Test cases for Session data class."""
    
    def test_session_is_expired(self):
        """Test session expiry check."""
        now = datetime.now(timezone.utc)
        session = Session("test-id", Path("/tmp"), now, now)
        
        # Should not be expired initially
        assert not session.is_expired(10)
        
        # Should be expired after timeout
        assert session.is_expired(-1)  # Negative timeout means already expired
    
    def test_session_touch(self):
        """Test session touch functionality."""
        now = datetime.now(timezone.utc)
        session = Session("test-id", Path("/tmp"), now, now)
        
        original_access_time = session.last_accessed
        session.touch()
        
        # Access time should be updated
        assert session.last_accessed > original_access_time