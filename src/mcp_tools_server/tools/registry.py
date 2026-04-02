"""Tool registry for loading and managing tools."""

import logging
from typing import Dict, Any, List

from ..core.config import Config
from ..core.structured_logger import logger
from ..security.validator import SecurityValidator
from .file_reader import FileReaderTool
from .file_writer import FileWriterTool
from .file_remover import FileRemoverTool
from .file_mover import FileMoverTool
from .directory_list import DirectoryListTool
from .directory_create import DirectoryCreateTool
from .directory_remove import DirectoryRemoveTool
from .directory_exists import DirectoryExistsTool
from .file_edit import FileEditTool
from .file_finder import FileFinderTool
from .content_searcher import ContentSearcherTool
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
        
        # Load file_mover tool
        if getattr(self.config.tools, 'file_mover', {}).get('enabled', True):
            self.tools['file_mover'] = FileMoverTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded file_mover tool")
        
        
        # Load directory tools (split from directory_manager)
        if getattr(self.config.tools, 'directory_list', {}).get('enabled', True):
            self.tools['directory_list'] = DirectoryListTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded directory_list tool")

            self.tools['directory_create'] = DirectoryCreateTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded directory_create tool")

            self.tools['directory_remove'] = DirectoryRemoveTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded directory_remove tool")

            self.tools['directory_exists'] = DirectoryExistsTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded directory_exists tool")

        # Load file_edit tool (exact-string replacement)
        if getattr(self.config.tools, 'file_edit', {}).get('enabled', True):
            self.tools['file_edit'] = FileEditTool(
                security_validator=self.security_validator
            )
            logger.server_event("Loaded file_edit tool")
        
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