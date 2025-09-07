"""Tool registry for loading and managing tools."""

import logging
from typing import Dict, Any, List

from ..core.config import Config
from ..core.structured_logger import logger
from ..security.validator import SecurityValidator
from .file_reader import FileReaderTool
from .file_writer import FileWriterTool
from .file_remover import FileRemoverTool
from .python_linter import PythonLinterTool
from .directory_manager import DirectoryManagerTool
from .file_editor import FileEditorTool
from .file_finder import FileFinderTool
from .content_searcher import ContentSearcherTool
from .python_runner import PythonRunnerTool




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
        
        # Load file_reader tool
        if self.config.tools.file_reader.get('enabled', True):
            max_files = self.config.tools.file_reader.get('max_files_per_request', 10)
            self.tools['file_reader'] = FileReaderTool(
                security_validator=self.security_validator,
                max_files_per_request=max_files
            )
            logger.server_event("Loaded file_reader tool")
        
        # Load file_writer tool
        if getattr(self.config.tools, 'file_writer', {}).get('enabled', True):
            self.tools['file_writer'] = FileWriterTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded file_writer tool")
        
        # Load file_remover tool
        if getattr(self.config.tools, 'file_remover', {}).get('enabled', True):
            self.tools['file_remover'] = FileRemoverTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded file_remover tool")
        
        # Load python_linter tool
        if getattr(self.config.tools, 'python_linter', {}).get('enabled', True):
            self.tools['python_linter'] = PythonLinterTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded python_linter tool")
        
        # Load directory_manager tool
        if getattr(self.config.tools, 'directory_manager', {}).get('enabled', True):
            self.tools['directory_manager'] = DirectoryManagerTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded directory_manager tool")
        
        # Load file_editor tool
        if getattr(self.config.tools, 'file_editor', {}).get('enabled', True):
            self.tools['file_editor'] = FileEditorTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded file_editor tool")
        
        # Load file_finder tool
        if getattr(self.config.tools, 'file_finder', {}).get('enabled', True):
            self.tools['file_finder'] = FileFinderTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded file_finder tool")
        
        # Load content_searcher tool
        if getattr(self.config.tools, 'content_searcher', {}).get('enabled', True):
            self.tools['content_searcher'] = ContentSearcherTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded content_searcher tool")
        
        # Load python_runner tool
        if getattr(self.config.tools, 'python_runner', {}).get('enabled', True):
            self.tools['python_runner'] = PythonRunnerTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded python_runner tool")
        
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