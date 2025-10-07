import logging
from typing import Dict, List, Optional
from langchain.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Asynchronous client for interacting with a Multi-Server MCP environment.
    Supports enabling/disabling specific MCP servers dynamically.
    """

    def __init__(self, server_config: Dict[str, Dict[str, str]]) -> None:
        """
        Initialize the MCP client.

        Args:
            server_config: Dictionary mapping server names to connection information.
        """
        self._server_config: Dict[str, Dict[str, str]] = server_config
        self._active_servers: List[str] = list(server_config.keys())  # all active by default
        self._client: MultiServerMCPClient = MultiServerMCPClient(connections=server_config)
        self._tools_cache: Optional[List[StructuredTool]] = None
        self._tools_per_server: Dict[str, List[StructuredTool]] = {}

    # --- Active Server Controls ---

    def list_servers(self) -> Dict[str, Dict[str, str]]:
        """
        Get all configured MCP servers.

        Returns:
            Dictionary mapping server names to connection information.
        """
        return self._server_config

    def get_active_servers(self) -> List[str]:
        """
        Get the currently active MCP servers.

        Returns:
            List of active server names.
        """
        return self._active_servers

    def set_active_servers(self, servers: List[str]) -> None:
        """
        Dynamically activate specific MCP servers.

        Args:
            servers: List of server names to activate. Only valid servers are activated.

        Notes:
            Resets the cached tools so they will be refetched on the next request.
            Also removes cached tools for any servers that are no longer active.
        """
        valid: List[str] = [s for s in servers if s in self._server_config]
        logger.info(f"[MCPClient] Setting active MCP servers: {valid}")
        self._active_servers = valid
        self._tools_cache = None  # reset cache

        # Clear cached per-server tools for servers that are no longer active
        for server in list(self._tools_per_server.keys()):
            if server not in valid:
                self._tools_per_server.pop(server, None)

    # --- Tool Management ---

    async def get_tools(self, refresh: bool = False) -> List[StructuredTool]:
        """
        Fetch and cache tools from all active MCP servers.

        Args:
            refresh: If True, forces a refetch of tools even if cached.

        Returns:
            List of StructuredTool instances available from the active servers.
        """
        if self._tools_cache is not None and not refresh:
            logger.info(f"[MCPClient] Returning cached tools: {len(self._tools_cache)}")
            return self._tools_cache

        logger.info(f"[MCPClient] Fetching tools from active MCP servers: {self._active_servers}")
        all_tools: List[StructuredTool] = []

        for server_name in self._active_servers:
            try:
                # Fetch tools from this specific server
                server_tools: List[StructuredTool] = await self._client.get_tools(server_name=server_name)
                logger.info(
                    f"[MCPClient] {len(server_tools)} tools fetched from server '{server_name}': "
                    f"{[t.name for t in server_tools]}"
                )

                # Cache per-server
                self._tools_per_server[server_name] = server_tools
                all_tools.extend(server_tools)
            except Exception as e:
                logger.warning(f"[MCPClient] Failed to fetch tools from server '{server_name}': {e}")

        self._tools_cache = all_tools
        logger.info(f"[MCPClient] Total tools returned: {len(all_tools)}")
        return all_tools

    async def list_tool_names(self, refresh: bool = False) -> List[str]:
        """
        List the names of all available tools from active MCP servers.

        Args:
            refresh: If True, forces a refetch of tools before listing names.

        Returns:
            List of tool names.
        """
        tools: List[StructuredTool] = await self.get_tools(refresh=refresh)
        return [tool.name for tool in tools]
