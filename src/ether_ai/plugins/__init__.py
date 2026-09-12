"""插件市场 — 发现、安装、管理第三方插件。"""

from ether_ai.plugins.local_registry import LocalPluginRegistry
from ether_ai.plugins.registry_client import PluginInfo, PluginRegistryClient

__all__ = ["LocalPluginRegistry", "PluginInfo", "PluginRegistryClient"]
