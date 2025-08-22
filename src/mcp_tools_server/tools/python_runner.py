"""Python runner tool for MCP tools server."""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class PythonRunnerTool(BaseTool):
    """Tool for executing Python code and scripts."""
    
    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="python_runner",
            description="Execute Python code or scripts with security restrictions",
            security_validator=security_validator
        )
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute (alternative to script_path)"
                },
                "script_path": {
                    "type": "string",
                    "description": "Path to Python script file to execute (alternative to code)"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command line arguments to pass to the script",
                    "default": []
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for script execution (must be in allowed directories)"
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout for script execution in seconds",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300
                },
                "capture_output": {
                    "type": "boolean",
                    "description": "Capture stdout and stderr output",
                    "default": True
                },
                "environment_vars": {
                    "type": "object",
                    "description": "Additional environment variables to set",
                    "default": {}
                }
            },
            "required": [],
            "oneOf": [
                {"required": ["code"]},
                {"required": ["script_path"]}
            ]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the python runner tool."""
        try:
            code = params.get('code')
            script_path = params.get('script_path')
            args = params.get('args', [])
            working_directory = params.get('working_directory')
            timeout_seconds = params.get('timeout_seconds', 30)
            capture_output = params.get('capture_output', True)
            environment_vars = params.get('environment_vars', {})
            
            # Validate that either code or script_path is provided
            if not code and not script_path:
                return {
                    "success": False,
                    "error": "Either 'code' or 'script_path' parameter is required"
                }
            
            if code and script_path:
                return {
                    "success": False,
                    "error": "Cannot specify both 'code' and 'script_path' parameters"
                }
            
            if timeout_seconds < 1 or timeout_seconds > 300:
                return {
                    "success": False,
                    "error": "timeout_seconds must be between 1 and 300"
                }
            
            # Validate script path if provided
            script_file_path = None
            if script_path:
                try:
                    self.security_validator.validate_file_path(script_path)
                    script_file_path = Path(script_path).resolve()
                    if not script_file_path.exists():
                        return {
                            "success": False,
                            "error": f"Script file does not exist: {script_path}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Security validation failed for script path: {str(e)}"
                    }
            
            # Validate working directory if provided
            work_dir = None
            if working_directory:
                try:
                    self.security_validator.validate_directory_path_for_creation(working_directory)
                    work_dir = Path(working_directory).resolve()
                    if not work_dir.exists():
                        return {
                            "success": False,
                            "error": f"Working directory does not exist: {working_directory}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Security validation failed for working directory: {str(e)}"
                    }
            else:
                # Use allowed directory as default working directory
                if self.security_validator.allowed_dir:
                    work_dir = self.security_validator.allowed_dir
                else:
                    work_dir = Path.cwd()
            
            # Execute the Python code/script
            result = await self._run_python(
                code=code,
                script_path=script_file_path,
                args=args,
                working_directory=work_dir,
                timeout_seconds=timeout_seconds,
                capture_output=capture_output,
                environment_vars=environment_vars
            )
            
            return {
                "success": True,
                "execution_type": "code" if code else "script",
                "script_path": str(script_file_path) if script_file_path else None,
                "working_directory": str(work_dir),
                "timeout_seconds": timeout_seconds,
                **result
            }
            
        except Exception as e:
            logger.error(f"Error in python_runner tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def _run_python(
        self,
        code: Optional[str] = None,
        script_path: Optional[Path] = None,
        args: list = None,
        working_directory: Path = None,
        timeout_seconds: int = 30,
        capture_output: bool = True,
        environment_vars: dict = None
    ) -> Dict[str, Any]:
        """Execute Python code or script."""
        if args is None:
            args = []
        if environment_vars is None:
            environment_vars = {}
        
        temp_file = None
        try:
            # Prepare command
            cmd = ["python3"]
            
            if code:
                # Create temporary file for code execution
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.py', delete=False, 
                    dir=str(working_directory) if working_directory else None
                )
                temp_file.write(code)
                temp_file.flush()
                temp_file.close()
                
                cmd.append(temp_file.name)
                script_used = temp_file.name
            else:
                cmd.append(str(script_path))
                script_used = str(script_path)
            
            # Add arguments
            cmd.extend(args)
            
            # Prepare environment
            env = os.environ.copy()
            env.update(environment_vars)
            
            # Ensure PYTHONPATH includes the working directory
            if working_directory:
                pythonpath = env.get('PYTHONPATH', '')
                if pythonpath:
                    env['PYTHONPATH'] = f"{working_directory}:{pythonpath}"
                else:
                    env['PYTHONPATH'] = str(working_directory)
            
            logger.info(f"Executing Python: {' '.join(cmd)}")
            
            # Execute the command
            if capture_output:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(working_directory) if working_directory else None,
                    env=env
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=timeout_seconds
                    )
                    
                    stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ""
                    stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""
                    
                    return {
                        "return_code": process.returncode,
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "timed_out": False,
                        "command": ' '.join(cmd)
                    }
                    
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return {
                        "return_code": -1,
                        "stdout": "",
                        "stderr": f"Process timed out after {timeout_seconds} seconds",
                        "timed_out": True,
                        "command": ' '.join(cmd)
                    }
            else:
                # Execute without capturing output
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(working_directory) if working_directory else None,
                    env=env
                )
                
                try:
                    return_code = await asyncio.wait_for(
                        process.wait(), timeout=timeout_seconds
                    )
                    
                    return {
                        "return_code": return_code,
                        "stdout": "",
                        "stderr": "",
                        "timed_out": False,
                        "command": ' '.join(cmd),
                        "note": "Output not captured (capture_output=False)"
                    }
                    
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return {
                        "return_code": -1,
                        "stdout": "",
                        "stderr": "",
                        "timed_out": True,
                        "command": ' '.join(cmd),
                        "note": "Process timed out, output not captured"
                    }
                    
        except FileNotFoundError:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": "Python interpreter not found. Ensure python3 is installed and in PATH.",
                "timed_out": False,
                "command": ' '.join(cmd) if 'cmd' in locals() else "python3"
            }
        except Exception as e:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "timed_out": False,
                "command": ' '.join(cmd) if 'cmd' in locals() else "python3"
            }
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass