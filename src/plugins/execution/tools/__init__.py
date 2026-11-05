"""Load configured tools independently of the agent using them.

Input origin:
    Local agent settings map capability.source names to plugin options.
Output destination:
    Native PydanticAI toolsets passed to Agent(toolsets=...).
Responsibilities:
    Load each plugin's create_toolset(options). Plugins own descriptions,
    implementations, and resources; tools may delegate to other agents or use
    MCP. This loader neither selects a tool call nor runs a tool itself.
"""

from collections.abc import Mapping

from pydantic_ai.toolsets import AbstractToolset

from plugins import get_plugin


def load_toolsets(definitions: Mapping[str, dict[str, object]]) -> list[AbstractToolset]:
    """Construct the toolsets explicitly enabled for one agent.

    Args:
        definitions: Capability.source module names mapped to plugin options.

    Returns:
        Toolsets whose lifecycle and calls are managed by PydanticAI.
    """
    toolsets = []
    for name, options in definitions.items():
        plugin = get_plugin("execution.tools", name)
        toolset: AbstractToolset = plugin.create_toolset(options)
        toolsets.append(toolset)
    return toolsets
