# MCP Tools Server

A secure HTTP server implementing MCP (Model Context Protocol) for meta-cognitive agents. Each tool is implemented as a separate module with strict security controls.

## Features

- **Modular tool architecture** - Each tool is a separate module loaded at startup
- **Security-first design** - Directory access restrictions and file validation
- **HTTP API** - RESTful endpoints for each tool (e.g., `/file_reader/v1`)
- **MCP compliant** - Follows Model Context Protocol standards
- **Configurable** - JSON configuration for security, tools, and server settings

## Architecture

```
src/mcp_tools_server/
├── core/           # Core server infrastructure
├── tools/          # Individual tool modules
├── security/       # Security and validation
└── main.py         # Server entry point
```

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

## Security

All file operations are restricted to configured directories only. See `config/server_config.json` for security settings.