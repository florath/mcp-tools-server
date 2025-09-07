"""Tests for session management endpoints."""

import pytest
import tempfile
import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.mcp_tools_server.core.config import Config, ServerConfig, SecurityConfig, SessionsConfig
from src.mcp_tools_server.core.server import MCPToolsServer


@pytest.fixture
def test_config():
    """Create test configuration."""
    return Config(
        server=ServerConfig(host="127.0.0.1", port=8000, debug=True),
        security=SecurityConfig(allowed_directory="", max_file_size_mb=10, allowed_file_extensions=[]),
        sessions=SessionsConfig(timeout_seconds=3600, max_sessions=10),
        tools={}
    )


@pytest.fixture
def mcp_server(test_config):
    """Create MCP server for testing."""
    return MCPToolsServer(test_config)


@pytest.fixture
def client(mcp_server):
    """Create test client."""
    return TestClient(mcp_server.app)


@pytest.fixture
def temp_directory():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


class TestSessionEndpoints:
    """Test cases for session management endpoints."""
    
    def test_create_session_success(self, client, temp_directory):
        """Test successful session creation."""
        response = client.post("/sessions", json={"directory": temp_directory})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data
        assert data["directory"] == temp_directory
        assert "message" in data
        
        # Session ID should be a valid UUID
        session_id = data["session_id"]
        assert len(session_id) == 36
        assert session_id.count("-") == 4
    
    def test_create_session_missing_directory(self, client):
        """Test session creation without directory parameter."""
        response = client.post("/sessions", json={})
        
        assert response.status_code == 400
        data = response.json()
        assert "directory parameter is required" in data["error"]
    
    def test_create_session_nonexistent_directory(self, client):
        """Test session creation with nonexistent directory."""
        response = client.post("/sessions", json={"directory": "/nonexistent/path"})
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "does not exist" in data["error"]
    
    def test_get_session_success(self, client, temp_directory):
        """Test successful session retrieval."""
        # Create session first
        create_response = client.post("/sessions", json={"directory": temp_directory})
        session_id = create_response.json()["session_id"]
        
        # Get session info
        response = client.get(f"/sessions/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session_id"] == session_id
        assert data["directory"] == str(Path(temp_directory).resolve())
        assert "created_at" in data
        assert "last_accessed" in data
        assert "age_seconds" in data
    
    def test_get_session_not_found(self, client):
        """Test getting nonexistent session."""
        response = client.get("/sessions/nonexistent-session-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "Session not found" in data["error"]
    
    def test_delete_session_success(self, client, temp_directory):
        """Test successful session deletion."""
        # Create session first
        create_response = client.post("/sessions", json={"directory": temp_directory})
        session_id = create_response.json()["session_id"]
        
        # Delete session
        response = client.delete(f"/sessions/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]
        
        # Verify session is gone
        get_response = client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 404
    
    def test_delete_session_not_found(self, client):
        """Test deleting nonexistent session."""
        response = client.delete("/sessions/nonexistent-session-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "Session not found" in data["error"]
    
    def test_list_sessions_empty(self, client):
        """Test listing sessions when none exist."""
        response = client.get("/sessions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["sessions"] == {}
        assert data["total_count"] == 0
    
    def test_list_sessions_with_sessions(self, client, temp_directory):
        """Test listing sessions with active sessions."""
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            response = client.post("/sessions", json={"directory": temp_directory})
            session_ids.append(response.json()["session_id"])
        
        # List sessions
        response = client.get("/sessions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_count"] == 3
        
        # Verify all sessions are listed
        sessions = data["sessions"]
        for session_id in session_ids:
            assert session_id in sessions
            session_info = sessions[session_id]
            assert "directory" in session_info
            assert "created_at" in session_info
            assert "last_accessed" in session_info
            assert "age_seconds" in session_info
    
    def test_session_stats(self, client, temp_directory):
        """Test session statistics endpoint."""
        # Get initial stats
        response = client.get("/sessions/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stats" in data
        
        stats = data["stats"]
        assert "active_sessions" in stats
        assert "max_sessions" in stats
        assert "timeout_seconds" in stats
        assert "cleanup_task_running" in stats
        
        initial_count = stats["active_sessions"]
        
        # Create session and check stats again
        client.post("/sessions", json={"directory": temp_directory})
        
        response = client.get("/sessions/stats")
        stats = response.json()["stats"]
        assert stats["active_sessions"] == initial_count + 1


class TestSessionIntegration:
    """Integration tests for session functionality with tools."""
    
    def test_file_reader_with_session(self, client, temp_directory):
        """Test file reader tool with session context."""
        # Create test file in session directory
        test_file = Path(temp_directory) / "test.txt"
        test_file.write_text("Hello from session!")
        
        # Create session
        session_response = client.post("/sessions", json={"directory": temp_directory})
        session_id = session_response.json()["session_id"]
        
        # Use file reader with session header
        headers = {"X-MCP-Session-ID": session_id}
        file_response = client.post(
            "/file_reader/v1",
            json={
                "file_path": "test.txt",
                "reason": "Testing session-aware file reading"
            },
            headers=headers
        )
        
        assert file_response.status_code == 200
        data = file_response.json()
        assert data["success"] is True
        assert data["result"]["content"] == "Hello from session!"
    
    def test_file_reader_without_session_header(self, client, temp_directory):
        """Test file reader tool without session header (should use default security)."""
        # Create test file in session directory
        test_file = Path(temp_directory) / "test.txt"
        test_file.write_text("Hello without session!")
        
        # Try to read file without session (should fail if not in allowed directory)
        file_response = client.post(
            "/file_reader/v1",
            json={
                "file_path": str(test_file),
                "reason": "Testing non-session file reading"
            }
        )
        
        # This will depend on the security configuration
        # In our test setup with empty allowed_directory, this might fail or succeed
        # The important thing is that it doesn't crash
        assert file_response.status_code in [200, 400, 403]
    
    def test_session_with_invalid_session_id(self, client, temp_directory):
        """Test tool call with invalid session ID."""
        # Create test file
        test_file = Path(temp_directory) / "test.txt"
        test_file.write_text("Hello world!")
        
        # Use file reader with invalid session header
        headers = {"X-MCP-Session-ID": "invalid-session-id"}
        file_response = client.post(
            "/file_reader/v1",
            json={
                "file_path": "test.txt",
                "reason": "Testing with invalid session ID"
            },
            headers=headers
        )
        
        # Should work but without session context (falls back to default security)
        # The response depends on default security settings
        assert file_response.status_code in [200, 400, 403]
    
    def test_directory_manager_with_session(self, client, temp_directory):
        """Test directory manager with session context."""
        # Create session
        session_response = client.post("/sessions", json={"directory": temp_directory})
        session_id = session_response.json()["session_id"]
        
        # Use directory manager to list session directory
        headers = {"X-MCP-Session-ID": session_id}
        list_response = client.post(
            "/directory_manager/v1",
            json={
                "operation": "list",
                "directory_path": ".",
                "reason": "Testing session-aware directory listing"
            },
            headers=headers
        )
        
        assert list_response.status_code == 200
        data = list_response.json()
        assert data["success"] is True
        assert "result" in data