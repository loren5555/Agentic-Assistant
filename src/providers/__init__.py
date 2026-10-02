"""Load the provider package selected by application configuration."""

from importlib import import_module
from types import ModuleType


def get_provider(name: str) -> ModuleType:
    """Import a provider without constructing its services.

    Args:
        name: Package name under providers, such as notion or codex.

    Returns:
        The package exposing its implementations and resource helpers.
    """
    provider = import_module(f"providers.{name}")
    return provider


__all__ = ["get_provider"]
