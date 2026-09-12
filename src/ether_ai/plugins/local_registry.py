"""本地插件索引后端 — 从本地 plugins/ 目录读取元数据，不依赖远程服务。"""
from __future__ import annotations

import json
from pathlib import Path

from ether_ai.plugins.registry_client import PluginInfo


class LocalPluginRegistry:
    """本地文件系统插件索引。

    目录结构约定：
        plugins/
            my-plugin/
                plugin.json        # PluginInfo 字段
                my-plugin-1.0.0.aether-plugin
    """

    def __init__(self, root: str | Path = "plugins"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def fetch_index(self) -> list[PluginInfo]:
        if not self.root.exists():
            return []
        result = []
        for d in sorted(self.root.iterdir()):
            meta = d / "plugin.json"
            if meta.exists():
                data = json.loads(meta.read_text(encoding="utf-8"))
                result.append(PluginInfo.from_dict(data))
        return result

    async def search(self, query: str, tags: list[str] | None = None) -> list[PluginInfo]:
        plugins = await self.fetch_index()
        q = query.lower()
        out = []
        for p in plugins:
            if q and q not in p.name.lower() and q not in p.description.lower():
                if not any(q in t.lower() for t in p.tags):
                    continue
            if tags and not set(tags).intersection(set(p.tags)):
                continue
            out.append(p)
        return sorted(out, key=lambda x: x.downloads, reverse=True)

    async def list_installed(self) -> list[dict]:
        result = []
        for d in sorted(self.root.iterdir()):
            meta = d / "plugin.json"
            if meta.exists():
                result.append(json.loads(meta.read_text(encoding="utf-8")))
        return result

    async def install(self, name: str, version: str = "latest") -> Path:
        target = self.root / name
        target.mkdir(parents=True, exist_ok=True)
        return target

    async def uninstall(self, name: str) -> bool:
        import shutil
        target = self.root / name
        if target.exists():
            shutil.rmtree(target)
            return True
        return False
