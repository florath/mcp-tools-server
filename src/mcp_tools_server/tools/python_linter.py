"""Python linter tool for MCP tools server."""

import json
import logging
import shutil
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class PythonLinterTool(BaseTool):
    """Tool for running Python linters (Ruff, MyPy, Bandit)."""
    
    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="python_linter",
            description="Run Python linters (Ruff, MyPy, Bandit) on Python files",
            security_validator=security_validator
        )
        self.version = "v1"
        
        # Check available linters
        self.available_linters = self._check_available_linters()
        from ..core.structured_logger import logger as struct_logger
        struct_logger.server_event(f"Available linters: {list(self.available_linters.keys())}")
    
    def _check_available_linters(self) -> Dict[str, str]:
        """Check which linters are available in the system."""
        linters = {}
        
        # Check for Ruff
        if shutil.which("ruff"):
            linters["ruff"] = shutil.which("ruff")
        
        # Check for MyPy
        if shutil.which("mypy"):
            linters["mypy"] = shutil.which("mypy")
        
        # Check for Bandit
        if shutil.which("bandit"):
            linters["bandit"] = shutil.which("bandit")
            
        return linters
    
    def get_info(self) -> Dict[str, Any]:
        """Get tool information."""
        return {
            "name": self.name,
            "version": self.version,
            "description": "Run Python linters (Ruff, MyPy, Bandit) on Python files",
            "available_linters": list(self.available_linters.keys()),
            "parameters": {
                "file_path": {
                    "type": "string",
                    "description": "Path to Python file or directory to lint",
                    "required": True
                },
                "linter_type": {
                    "type": "string", 
                    "description": "Linter to use: 'ruff', 'mypy', 'bandit', or 'all'",
                    "default": "ruff",
                    "enum": ["ruff", "mypy", "bandit", "all"]
                },
                "fix_issues": {
                    "type": "boolean",
                    "description": "Auto-fix issues (only supported by Ruff)",
                    "default": False
                },
                "config_file": {
                    "type": "string",
                    "description": "Optional path to configuration file",
                    "required": False
                }
            }
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to Python file or directory to lint"
                },
                "linter_type": {
                    "type": "string", 
                    "description": "Linter to use: 'ruff', 'mypy', 'bandit', or 'all'",
                    "default": "ruff",
                    "enum": ["ruff", "mypy", "bandit", "all"]
                },
                "fix_issues": {
                    "type": "boolean",
                    "description": "Auto-fix issues (only supported by Ruff)",
                    "default": False
                },
                "config_file": {
                    "type": "string",
                    "description": "Optional path to configuration file"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        }

    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the python linter tool."""
        try:
            file_path = params.get('file_path')
            linter_type = params.get('linter_type', 'ruff')
            fix_issues = params.get('fix_issues', False)
            config_file = params.get('config_file')
            
            if not file_path:
                return {
                    "success": False,
                    "error": "file_path parameter is required"
                }
            
            # Security validation
            try:
                self.security_validator.validate_file_path(file_path)
                if config_file:
                    self.security_validator.validate_file_path(config_file)
            except ValueError as e:
                return {
                    "success": False,
                    "error": f"Security validation failed: {str(e)}"
                }
            
            # Check if file/directory exists
            path = Path(file_path)
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File or directory not found: {file_path}"
                }
            
            results = {}
            
            if linter_type == "all":
                # Run all available linters
                for linter in self.available_linters.keys():
                    result = await self._run_linter(linter, file_path, fix_issues, config_file)
                    results[linter] = result
            else:
                # Run specific linter
                if linter_type not in self.available_linters:
                    return {
                        "success": False,
                        "error": f"Linter '{linter_type}' is not available. Available: {list(self.available_linters.keys())}"
                    }
                
                result = await self._run_linter(linter_type, file_path, fix_issues, config_file)
                results[linter_type] = result
            
            return {
                "success": True,
                "file_path": self._normalize_path_for_response(Path(file_path)),
                "linter_type": linter_type,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error in python_linter tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def _run_linter(self, linter: str, file_path: str, fix_issues: bool = False, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Run a specific linter."""
        try:
            cmd = []
            
            if linter == "ruff":
                cmd = [self.available_linters["ruff"]]
                if fix_issues:
                    cmd.extend(["check", "--fix"])
                else:
                    cmd.append("check")
                
                cmd.extend(["--output-format", "json"])
                
                if config_file:
                    cmd.extend(["--config", config_file])
                    
                cmd.append(file_path)
            
            elif linter == "mypy":
                cmd = [self.available_linters["mypy"]]
                cmd.extend(["--show-error-codes", "--show-column-numbers"])
                
                if config_file:
                    cmd.extend(["--config-file", config_file])
                
                cmd.append(file_path)
            
            elif linter == "bandit":
                cmd = [self.available_linters["bandit"]]
                cmd.extend(["-f", "json"])
                
                if config_file:
                    cmd.extend(["-c", config_file])
                
                if Path(file_path).is_dir():
                    cmd.extend(["-r", file_path])
                else:
                    cmd.append(file_path)
            
            # Run the command
            logger.info(f"Running command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            
            stdout_text = stdout.decode('utf-8') if stdout else ""
            stderr_text = stderr.decode('utf-8') if stderr else ""
            
            # Parse output based on linter
            issues = self._parse_linter_output(linter, stdout_text, stderr_text, process.returncode)
            
            return {
                "linter": linter,
                "success": True,
                "return_code": process.returncode,
                "issues": issues,
                "stdout": stdout_text,
                "stderr": stderr_text
            }
            
        except asyncio.TimeoutError:
            return {
                "linter": linter,
                "success": False,
                "error": "Linter execution timed out (60s limit)"
            }
        except Exception as e:
            logger.error(f"Error running {linter}: {e}")
            return {
                "linter": linter,
                "success": False,
                "error": str(e)
            }
    
    def _parse_linter_output(self, linter: str, stdout: str, stderr: str, return_code: int) -> List[Dict[str, Any]]:
        """Parse linter output into structured format."""
        issues = []
        
        try:
            if linter == "ruff":
                if stdout.strip():
                    try:
                        ruff_output = json.loads(stdout)
                        for issue in ruff_output:
                            issues.append({
                                "file": issue.get("filename"),
                                "line": issue.get("location", {}).get("row"),
                                "column": issue.get("location", {}).get("column"),
                                "rule": issue.get("code"),
                                "message": issue.get("message"),
                                "severity": "error" if issue.get("code", "").startswith("E") else "warning"
                            })
                    except json.JSONDecodeError:
                        issues.append({
                            "message": "Failed to parse Ruff JSON output",
                            "raw_output": stdout
                        })
            
            elif linter == "mypy":
                # MyPy outputs line by line
                for line in stdout.strip().split('\n'):
                    if line.strip() and ':' in line:
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            issues.append({
                                "file": parts[0],
                                "line": int(parts[1]) if parts[1].isdigit() else None,
                                "column": int(parts[2]) if parts[2].isdigit() else None,
                                "message": parts[3].strip(),
                                "severity": "error" if "error:" in line else "note"
                            })
            
            elif linter == "bandit":
                if stdout.strip():
                    try:
                        bandit_output = json.loads(stdout)
                        for issue in bandit_output.get("results", []):
                            issues.append({
                                "file": issue.get("filename"),
                                "line": issue.get("line_number"),
                                "rule": issue.get("test_id"),
                                "message": issue.get("issue_text"),
                                "severity": issue.get("issue_severity", "").lower(),
                                "confidence": issue.get("issue_confidence", "").lower()
                            })
                    except json.JSONDecodeError:
                        issues.append({
                            "message": "Failed to parse Bandit JSON output",
                            "raw_output": stdout
                        })
            
        except Exception as e:
            logger.error(f"Error parsing {linter} output: {e}")
            issues.append({
                "message": f"Error parsing {linter} output: {str(e)}",
                "raw_stdout": stdout,
                "raw_stderr": stderr
            })
        
        return issues