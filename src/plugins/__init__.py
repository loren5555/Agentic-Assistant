"""Load implementations by application module and configured source."""

from importlib import import_module
from types import ModuleType


def get_plugin(module: str, source: str) -> ModuleType:
    """Import one implementation without constructing its services.

    Args:
        module: Role path matching assistant/components, for example coordination.router.
        source: Configured implementation source, such as local or notion.

    Returns:
        Module exposing its capability implementations.
    """
    plugin = import_module(f"plugins.{module}.{source}")
    return plugin


__all__ = ["get_plugin"]
