import logging
from typing import Dict, List, Optional
from langchain.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class MCPClient:
    """
    An asynchronous client for interacting with a Multi-Server MCP environment.
    This client directly exposes the async methods of the underlying
    langchain_mcp_adapters client and caches the retrieved tools.
    """

    def __init__(self, server_config: Dict[str, Dict[str, str]]) -> None:
        """
        Initializes the asynchronous MCP client.

        Args:
            server_config: A dictionary defining the MCP server connections.
        """
        self._client = MultiServerMCPClient(connections=server_config)
        self._tools: Optional[List[StructuredTool]] = None

    async def get_tools(self) -> List[StructuredTool]:
        """
        Asynchronously retrieves and caches the tools from all configured MCP servers.

        The tools returned are native LangChain async StructuredTools, which can be
        used directly by an AgentExecutor.
        """
        if self._tools is None:
            logger.info("No cached tools found. Fetching from MCP servers...")
            self._tools = await self._client.get_tools()
            logger.info(f"Successfully fetched {len(self._tools)} tools.")
        return self._tools

    async def list_tool_names(self) -> List[str]:
        """
        Asynchronously returns a list of available tool names.
        """
        tools = await self.get_tools()
        return [tool.name for tool in tools]