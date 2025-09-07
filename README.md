# MCP Tools Server

A secure HTTP server implementing MCP (Model Context Protocol) for meta-cognitive agents. Each tool is implemented as a separate module with strict security controls.

## Features

- **Modular tool architecture** - Each tool is a separate module loaded at startup
- **Security-first design** - Directory access restrictions and file validation
- **HTTP API** - RESTful endpoints for each tool (e.g., `/file_reader/v1`)
- **Session management** - Transparent stage isolation for concurrent workflows
- **MCP compliant** - Follows Model Context Protocol standards
- **Configurable** - JSON configuration for security, tools, and server settings

## Architecture

```
src/mcp_tools_server/
├── core/           # Core server infrastructure
│   ├── session.py  # Session management
│   ├── server.py   # FastAPI server
│   └── config.py   # Configuration
├── tools/          # Individual tool modules
├── security/       # Security and validation
└── main.py         # Server entry point
```

## Session Management

The MCP Tools Server supports **session-based isolation** for concurrent workflows. Sessions allow multiple processes to operate in isolated directory contexts without interference.

### Key Concepts

- **Session**: A temporary workspace mapped to a specific directory
- **Session ID**: Unique UUID identifier for each session
- **Session Directory**: The root directory for all operations within a session
- **Transparent Operation**: Tools operate on relative paths, unaware of session complexity

### How Sessions Work

1. **Create Session**: A client creates a session mapped to a specific directory
2. **Use Session Header**: Subsequent tool requests include `X-MCP-Session-ID` header
3. **Automatic Routing**: Server automatically routes tool operations to the session directory
4. **Path Resolution**: Relative paths are resolved against the session directory
5. **Session Cleanup**: Sessions expire automatically or can be manually deleted

### Benefits

- **Stage Isolation**: Different workflow stages can run in separate directories
- **Concurrent Operations**: Multiple processes can run simultaneously without conflicts
- **Clean Abstractions**: LLM agents work with simple relative paths
- **Security**: All existing security validations apply within session scope

## Installation

```bash
pip install -e .
```

## Running

```bash
mcp-tools-server --config config/server_config.json
```

## API Endpoints

### Tool Discovery
- **List Tools**: `GET /tools` - List all available tools with basic info
- **Tool Schema**: `GET /tools/{tool_name}/schema` - Get detailed schema for a specific tool  
- **All Schemas**: `GET /tools/schemas` - Get schemas for all tools (convenient for LLMs)
- **Server Info**: `GET /` - Server info and available tools
- **Health Check**: `GET /health` - Server health status

### Session Management
- **Create Session**: `POST /sessions` - Create a new session for a directory
  - Parameters: `{"directory": "/path/to/session/directory"}`
  - Returns: `{"session_id": "uuid", "directory": "/path", "message": "..."}`
- **Get Session**: `GET /sessions/{session_id}` - Get session information
  - Returns: Session details including creation time, last accessed, directory
- **Delete Session**: `DELETE /sessions/{session_id}` - Remove a session
  - Returns: Success confirmation
- **List Sessions**: `GET /sessions` - List all active sessions
  - Returns: Dictionary of all sessions with their details
- **Session Statistics**: `GET /sessions/stats` - Get session manager statistics
  - Returns: Active session count, limits, and cleanup status

### Tools

#### file_reader
- **Endpoint**: `POST /file_reader/v1`
- **Purpose**: Read files with security validation
- **Parameters**:
  - `file_path`: Path to file to read
  - `encoding`: File encoding (default: utf-8)
  - `include_line_numbers`: Include line numbers (default: false)

#### file_writer
- **Endpoint**: `POST /file_writer/v1`
- **Purpose**: Create or overwrite files with security validation
- **Parameters**:
  - `file_path`: Path to file to create/overwrite
  - `content`: Content to write to file (default: empty string)
  - `encoding`: File encoding (default: utf-8)
  - `create_dirs`: Create parent directories if needed (default: true)

#### python_linter
- **Endpoint**: `POST /python_linter/v1`
- **Purpose**: Run Python linters (Ruff, MyPy, Bandit) on Python files
- **Parameters**:
  - `file_path`: Path to Python file or directory to lint
  - `linter_type`: Linter to use - 'ruff', 'mypy', 'bandit', or 'all' (default: ruff)
  - `fix_issues`: Auto-fix issues (only supported by Ruff, default: false)
  - `config_file`: Optional path to configuration file

#### directory_manager
- **Endpoint**: `POST /directory_manager/v1`
- **Purpose**: Create, remove, and list directories with security validation
- **Parameters**:
  - `operation`: Operation to perform - 'create', 'remove', or 'list'
  - `directory_path`: Path to the directory
  - `create_parents`: Create parent directories if needed (create only, default: true)
  - `force_remove`: Force remove non-empty directories (remove only, default: false)

#### file_editor
- **Endpoint**: `POST /file_editor/v1`
- **Purpose**: Edit files using line-number based operations (edit, insert, delete)
- **Parameters**:
  - `file_path`: Path to the file to edit
  - `operation`: Operation to perform - 'edit', 'insert', or 'delete'
  - `line_number`: Line number to operate on (1-indexed)
  - `line_end`: End line number for range operations (optional)
  - `old_content`: Expected old content for verification (edit/delete operations)
  - `new_content`: New content to insert or replace with (edit/insert operations)
  - `encoding`: File encoding (default: utf-8)

## Configuration

The server is configured via a JSON configuration file. Here's the complete structure with session settings:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 7091,
    "debug": true
  },
  "security": {
    "allowed_directory": "/tmp/workspace",
    "max_file_size_mb": 100,
    "allowed_file_extensions": [
      ".json", ".yaml", ".yml", ".txt", ".py", ".js", ".ts", 
      ".md", ".csv", ".xml", ".html", ".css", ".sql", ".toml"
    ]
  },
  "sessions": {
    "timeout_seconds": 3600,
    "max_sessions": 100
  },
  "logging": {
    "level": "INFO",
    "format": "json"
  },
  "tools": {
    "file_reader": {"enabled": true},
    "file_writer": {"enabled": true},
    "python_linter": {"enabled": true},
    "directory_manager": {"enabled": true},
    "file_editor": {"enabled": true}
  }
}
```

### Configuration Options

- **server**: HTTP server settings (host, port, debug mode)
- **security**: File access restrictions and validation rules
- **sessions**: Session management settings
  - `timeout_seconds`: Session expiration timeout (default: 3600 = 1 hour)
  - `max_sessions`: Maximum concurrent sessions (default: 100)
- **logging**: Logging configuration (level, format)
- **tools**: Tool-specific settings and enable/disable flags

## Example Usage

1. **Discover available tools**:
   ```bash
   curl http://localhost:7091/tools
   ```

2. **Get tool schema**:
   ```bash
   curl http://localhost:7091/tools/file_reader/schema
   ```

3. **Read a file**:
   ```bash
   curl -X POST http://localhost:7091/file_reader/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/tmp/workspace/config.json"}'
   ```

4. **Write a file**:
   ```bash
   curl -X POST http://localhost:7091/file_writer/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/tmp/workspace/output.txt", "content": "Hello MCP!"}'
   ```

5. **Lint Python code**:
   ```bash
   curl -X POST http://localhost:7091/python_linter/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/tmp/workspace/script.py", "linter_type": "all"}'
   ```

6. **Auto-fix Python code issues**:
   ```bash
   curl -X POST http://localhost:7091/python_linter/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/tmp/workspace/script.py", "linter_type": "ruff", "fix_issues": true}'
   ```

7. **Create a directory**:
   ```bash
   curl -X POST http://localhost:7091/directory_manager/v1 \
     -H "Content-Type: application/json" \
     -d '{"operation": "create", "directory_path": "/tmp/workspace/new_folder"}'
   ```

8. **List directory contents**:
   ```bash
   curl -X POST http://localhost:7091/directory_manager/v1 \
     -H "Content-Type: application/json" \
     -d '{"operation": "list", "directory_path": "/tmp/workspace"}'
   ```

9. **Edit a specific line in a file**:
   ```bash
   curl -X POST http://localhost:7091/file_editor/v1 \
     -H "Content-Type: application/json" \
     -d '{"operation": "edit", "file_path": "/tmp/workspace/script.py", "line_number": 5, "old_content": "old line", "new_content": "new line"}'
   ```

### Session-Based Workflow Examples

10. **Create a session**:
    ```bash
    curl -X POST http://localhost:7091/sessions \
      -H "Content-Type: application/json" \
      -d '{"directory": "/tmp/my-session-workspace"}'
    ```
    Response:
    ```json
    {
      "success": true,
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "directory": "/tmp/my-session-workspace",
      "message": "Session created successfully"
    }
    ```

11. **Use tools with session context**:
    ```bash
    # Read file within session (relative path)
    curl -X POST http://localhost:7091/file_reader/v1 \
      -H "Content-Type: application/json" \
      -H "X-MCP-Session-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
      -d '{"file_path": "data/config.json", "reason": "Reading config in session"}'
    
    # Create directory within session
    curl -X POST http://localhost:7091/directory_manager/v1 \
      -H "Content-Type: application/json" \
      -H "X-MCP-Session-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
      -d '{"operation": "create", "directory_path": "output", "reason": "Creating output dir"}'
    ```

12. **Check session status**:
    ```bash
    curl http://localhost:7091/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890
    ```

13. **List all active sessions**:
    ```bash
    curl http://localhost:7091/sessions
    ```

14. **Get session statistics**:
    ```bash
    curl http://localhost:7091/sessions/stats
    ```

15. **Clean up session**:
    ```bash
    curl -X DELETE http://localhost:7091/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890
    ```

### Workflow Integration

Sessions are particularly useful for multi-stage processes:

```bash
# Stage 1: Analysis
SESSION_1=$(curl -s -X POST http://localhost:7091/sessions \
  -H "Content-Type: application/json" \
  -d '{"directory": "/tmp/analysis-stage"}' | jq -r '.session_id')

# Stage 2: Implementation  
SESSION_2=$(curl -s -X POST http://localhost:7091/sessions \
  -H "Content-Type: application/json" \
  -d '{"directory": "/tmp/implementation-stage"}' | jq -r '.session_id')

# Use tools in each stage independently
curl -X POST http://localhost:7091/file_reader/v1 \
  -H "Content-Type: application/json" \
  -H "X-MCP-Session-ID: $SESSION_1" \
  -d '{"file_path": "requirements.txt", "reason": "Analysis stage"}'

curl -X POST http://localhost:7091/file_writer/v1 \
  -H "Content-Type: application/json" \
  -H "X-MCP-Session-ID: $SESSION_2" \
  -d '{"file_path": "implementation.py", "content": "...", "reason": "Implementation stage"}'
```

## Security

All file operations are restricted to configured directories only. The security model includes:

- **Directory Restrictions**: Files can only be accessed within allowed directories
- **File Extension Validation**: Only specified file extensions are permitted
- **File Size Limits**: Maximum file size restrictions prevent abuse
- **Session Isolation**: Each session operates within its own directory scope
- **Path Traversal Protection**: Attempts to access files outside allowed areas are blocked

### Session Security

When using sessions:
- Session directories must exist and be accessible
- All security validations apply within the session directory scope
- Relative paths are resolved against the session directory, not the global allowed directory
- Absolute paths are still validated against security restrictions
- Sessions automatically expire to prevent resource leaks

See `config/server_config.json` for complete security configuration options.