"""Tool registry for loading and managing tools."""

import logging
from typing import Dict, Any, List

from ..core.config import Config
from ..core.structured_logger import logger
from ..security.validator import SecurityValidator
from .read_file import ReadFileTool
from .write_file import WriteFileTool
from .remove_file import RemoveFileTool
from .move_file import MoveFileTool
from .list_dir import ListDirTool
from .mkdir import MkdirTool
from .rmdir import RmdirTool
from .dir_exists import DirExistsTool
from .edit_file import EditFileTool
from .find_files import FindFilesTool
from .search_content import SearchContentTool
# Analysis tools and python tools removed - python tools can be handled by codex directly




class ToolRegistry:
    """Registry for managing all available tools."""
    
    def __init__(self, config: Config, security_validator: SecurityValidator):
        self.config = config
        self.security_validator = security_validator
        self.tools: Dict[str, Any] = {}
        
        self._load_tools()
    
    def _load_tools(self):
        """Load all enabled tools."""
        logger.server_event("Loading tools...")
        
        # Load read_file tool
        if self.config.tools.read_file.get('enabled', True):
            max_files = self.config.tools.read_file.get('max_files_per_request', 10)
            self.tools['read_file'] = ReadFileTool(
                security_validator=self.security_validator,
                max_files_per_request=max_files
            )
            logger.server_event("Loaded read_file tool")
        
        # Load write_file tool
        if getattr(self.config.tools, 'write_file', {}).get('enabled', True):
            self.tools['write_file'] = WriteFileTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded write_file tool")
        
        # Load remove_file tool
        if getattr(self.config.tools, 'remove_file', {}).get('enabled', True):
            self.tools['remove_file'] = RemoveFileTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded remove_file tool")
        
        # Load move_file tool
        if getattr(self.config.tools, 'move_file', {}).get('enabled', True):
            self.tools['move_file'] = MoveFileTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded move_file tool")
        
        
        # Load directory tools
        if getattr(self.config.tools, 'list_dir', {}).get('enabled', True):
            self.tools['list_dir'] = ListDirTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded list_dir tool")

            self.tools['mkdir'] = MkdirTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded mkdir tool")

            self.tools['rmdir'] = RmdirTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded rmdir tool")

            self.tools['dir_exists'] = DirExistsTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded dir_exists tool")

        # Load edit_file tool (exact-string replacement)
        if getattr(self.config.tools, 'edit_file', {}).get('enabled', True):
            self.tools['edit_file'] = EditFileTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded edit_file tool")
        
        # Load find_files tool
        if getattr(self.config.tools, 'find_files', {}).get('enabled', True):
            self.tools['find_files'] = FindFilesTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded find_files tool")
        
        # Load search_content tool
        if getattr(self.config.tools, 'search_content', {}).get('enabled', True):
            self.tools['search_content'] = SearchContentTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded search_content tool")
        

        # Analysis tools removed - they were confusing LLMs and causing them to
        # add conflicts instead of resolving them

        # Add more tools here as they are implemented
        # Example:
        # if self.config.tools.code_parser.get('enabled', False):
        #     self.tools['code_parser'] = CodeParserTool(...)

        logger.server_event(f"Loaded {len(self.tools)} tools: {list(self.tools.keys())}")
    
    def get_tool(self, name: str) -> Any:
        """Get tool by name."""
        return self.tools.get(name)
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())
    
    def get_tools_info(self) -> Dict[str, Any]:
        """Get information about all loaded tools."""
        return {
            name: tool.get_info() 
            for name, tool in self.tools.items()
        }