# MCP Tools Server

A secure HTTP server implementing MCP (Model Context Protocol) for meta-cognitive agents. Each tool is implemented as a separate module with strict security controls.

## Features

- **Modular tool architecture** - Each tool is a separate module loaded at startup
- **Security-first design** - Directory access restrictions and file validation
- **HTTP API** - RESTful endpoints for each tool (e.g., `/read_file/v1`)
- **MCP JSON-RPC** - Support for MCP JSON-RPC 2.0 protocol via `/` or `/mcp` endpoints
- **Session management** - Transparent stage isolation for concurrent workflows
- **MCP compliant** - Follows Model Context Protocol standards
- **Configurable** - JSON configuration for security, tools, and server settings

## Available Tools

The server provides the following tools (11 total):

### File Operations
- **read_file** - Read files with security validation
- **write_file** - Create or overwrite files with security validation
- **remove_file** - Remove files with security validation
- **move_file** - Move or rename files with security validation
- **edit_file** - Edit files by exact string replacement
- **find_files** - Find files and directories by name patterns

### Directory Operations
- **list_dir** - List contents of a directory
- **mkdir** - Create a new directory
- **rmdir** - Remove a directory
- **dir_exists** - Check if a directory exists

### Analysis
- **search_content** - Search for text patterns within files in allowed directories

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

### MCP JSON-RPC Endpoints

- **POST /** - MCP JSON-RPC 2.0 endpoint (root path)
- **POST /mcp** - MCP JSON-RPC 2.0 endpoint (conventional path)

Supported MCP methods:
- `initialize` - Initialize MCP connection and get server capabilities
- `tools/list` - List all available tools
- `tools/call` - Call a specific tool with parameters

### Tools

#### read_file
- **Endpoint**: `POST /read_file/v1`
- **Purpose**: Read files with security validation
- **Parameters**:
  - `file_path`: Path to file to read
  - `encoding`: File encoding (default: utf-8)
  - `include_line_numbers`: Include line numbers (default: false)

#### write_file
- **Endpoint**: `POST /write_file/v1`
- **Purpose**: Create or overwrite files with security validation
- **Parameters**:
  - `file_path`: Path to file to create/overwrite
  - `content`: Content to write to file (default: empty string)
  - `encoding`: File encoding (default: utf-8)
  - `create_dirs`: Create parent directories if needed (default: true)

#### list_dir
- **Endpoint**: `POST /list_dir/v1`
- **Purpose**: List contents of a directory
- **Parameters**:
  - `directory_path`: Path to the directory
  - `reason`: Reason for the operation

#### mkdir
- **Endpoint**: `POST /mkdir/v1`
- **Purpose**: Create a new directory
- **Parameters**:
  - `directory_path`: Path to the directory to create
  - `reason`: Reason for the operation

#### rmdir
- **Endpoint**: `POST /rmdir/v1`
- **Purpose`: Remove a directory
- **Parameters**:
  - `directory_path`: Path to the directory to remove
  - `force`: Force remove non-empty directories (default: false)
  - `reason`: Reason for the operation

#### dir_exists
- **Endpoint**: `POST /dir_exists/v1`
- **Purpose**: Check if a directory exists
- **Parameters**:
  - `directory_path`: Path to the directory to check
  - `reason`: Reason for the operation

#### edit_file
- **Endpoint**: `POST /edit_file/v1`
- **Purpose**: Edit a file by replacing an exact string
- **Parameters**:
  - `file_path`: Path to the file to edit
  - `old_content`: Exact text to find (must match exactly once, unless `replace_all=true`)
  - `new_content`: Replacement text
  - `replace_all`: Replace every occurrence instead of requiring uniqueness (default: false)
  - `encoding`: File encoding (default: utf-8)
  - `reason`: Reason for the operation

#### find_files
- **Endpoint**: `POST /find_files/v1`
- **Purpose`: Find files and directories by name patterns
- **Parameters**:
  - `pattern`: Pattern to search for (e.g., '*.py', 'test_*')
  - `reason`: Reason for the operation

#### search_content
- **Endpoint**: `POST /search_content/v1`
- **Purpose**: Search for text patterns within files in allowed directories
- **Parameters**:
  - `search_term`: Text pattern to search for
  - `reason`: Reason for the operation

#### remove_file
- **Endpoint**: `POST /remove_file/v1`
- **Purpose**: Remove files with security validation
- **Parameters**:
  - `file_path`: Path to the file to remove
  - `reason`: Reason for the operation

#### move_file
- **Endpoint**: `POST /move_file/v1`
- **Purpose`: Move or rename files with security validation
- **Parameters**:
  - `source_path`: Path to the source file
  - `destination_path`: Path to the destination
  - `reason`: Reason for the operation

## Configuration

The server is configured via a JSON configuration file. Here's the complete structure with session settings:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 7091,
    "debug": false
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
    "read_file": {"enabled": true},
    "write_file": {"enabled": true},
    "remove_file": {"enabled": true},
    "move_file": {"enabled": true},
    "list_dir": {"enabled": true},
    "mkdir": {"enabled": true},
    "rmdir": {"enabled": true},
    "dir_exists": {"enabled": true},
    "edit_file": {"enabled": true},
    "find_files": {"enabled": true},
    "search_content": {"enabled": true}
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
   curl http://localhost:7091/tools/read_file/schema
   ```

3. **Read a file**:
   ```bash
   curl -X POST http://localhost:7091/read_file/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/tmp/workspace/config.json"}'
   ```

4. **Write a file**:
   ```bash
   curl -X POST http://localhost:7091/write_file/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/tmp/workspace/output.txt", "content": "Hello MCP!"}'
   ```

5. **Auto-fix Python code issues using codex**:
   Codex handles Python code execution and linting directly through its execute_command tool.

6. **Create a directory**:
   ```bash
   curl -X POST http://localhost:7091/mkdir/v1 \
     -H "Content-Type: application/json" \
     -d '{"directory_path": "new_folder", "reason": "create output directory"}'
   ```

7. **List directory contents**:
   ```bash
   curl -X POST http://localhost:7091/list_dir/v1 \
     -H "Content-Type: application/json" \
     -d '{"directory_path": ".", "reason": "list workspace"}'
   ```

8. **Edit a file (string replacement)**:
   ```bash
   curl -X POST http://localhost:7091/edit_file/v1 \
     -H "Content-Type: application/json" \
     -d '{"file_path": "script.py", "old_content": "old line", "new_content": "new line", "reason": "fix typo"}'
   ```

### Session-Based Workflow Examples

9. **Create a session**:
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

10. **Use tools with session context**:
    ```bash
    # Read file within session (relative path)
    curl -X POST http://localhost:7091/read_file/v1 \
      -H "Content-Type: application/json" \
      -H "X-MCP-Session-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
      -d '{"file_path": "data/config.json", "reason": "Reading config in session"}'
    
    # Create directory within session
    curl -X POST http://localhost:7091/mkdir/v1 \
      -H "Content-Type: application/json" \
      -H "X-MCP-Session-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
      -d '{"directory_path": "output", "reason": "Creating output dir"}'
    ```

11. **Check session status**:
    ```bash
    curl http://localhost:7091/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890
    ```

12. **List all active sessions**:
    ```bash
    curl http://localhost:7091/sessions
    ```

13. **Get session statistics**:
    ```bash
    curl http://localhost:7091/sessions/stats
    ```

14. **Clean up session**:
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
curl -X POST http://localhost:7091/read_file/v1 \
  -H "Content-Type: application/json" \
  -H "X-MCP-Session-ID: $SESSION_1" \
  -d '{"file_path": "requirements.txt", "reason": "Analysis stage"}'

curl -X POST http://localhost:7091/write_file/v1 \
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