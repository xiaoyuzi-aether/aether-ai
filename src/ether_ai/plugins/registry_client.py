"""插件市场远程索引客户端 — 发现、安装、管理第三方插件。"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    tags: list[str] = field(default_factory=list)
    download_url: str = ""
    sha256: str = ""
    min_ether_version: str = "0.1.0"
    dependencies: list[str] = field(default_factory=list)
    downloads: int = 0
    rating: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> PluginInfo:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class PluginRegistryClient:
    """远程插件索引客户端。

    默认指向官方索引，可通过环境变量 AETHER_REGISTRY_URL 覆盖。
    """

    DEFAULT_REGISTRY = "https://registry.aether-ai.dev/api/v1"

    def __init__(self, registry_url: str | None = None, cache_dir: str | Path | None = None):
        self.registry_url = (registry_url or self.DEFAULT_REGISTRY).rstrip("/")
        self.cache_dir = Path(cache_dir or Path.home() / ".aether" / "plugin_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_cache: dict[str, Any] = {}
        self._cache_ttl = 300  # 5 分钟缓存

    # ── 索引获取 ────────────────────────────────────────────
    async def fetch_index(self, force: bool = False) -> list[PluginInfo]:
        """获取远程插件索引列表。带本地缓存。"""
        cache_file = self.cache_dir / "index.json"

        # 检查缓存
        if not force and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < self._cache_ttl:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return [PluginInfo.from_dict(p) for p in data.get("plugins", [])]

        # 从远程拉取
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.registry_url}/plugins")
                resp.raise_for_status()
                data = resp.json()
                cache_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                return [PluginInfo.from_dict(p) for p in data.get("plugins", [])]
        except Exception as e:
            # 远程失败时回退到过期缓存
            if cache_file.exists():
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return [PluginInfo.from_dict(p) for p in data.get("plugins", [])]
            raise ConnectionError(f"无法获取插件索引: {e}") from e

    # ── 搜索 ────────────────────────────────────────────────
    async def search(self, query: str, tags: list[str] | None = None) -> list[PluginInfo]:
        """搜索插件。支持关键词 + 标签过滤。"""
        plugins = await self.fetch_index()
        q = query.lower()
        results = []
        for p in plugins:
            if q and q not in p.name.lower() and q not in p.description.lower():
                if not any(q in t.lower() for t in p.tags):
                    continue
            if tags and not set(tags).intersection(set(p.tags)):
                continue
            results.append(p)
        return sorted(results, key=lambda x: x.downloads, reverse=True)

    async def get_plugin(self, name: str) -> PluginInfo | None:
        """获取单个插件详情。"""
        plugins = await self.fetch_index()
        for p in plugins:
            if p.name == name:
                return p
        return None

    # ── 安装 ────────────────────────────────────────────────
    async def install(
        self,
        name: str,
        version: str = "latest",
        install_dir: str | Path | None = None,
    ) -> Path:
        """下载并安装插件。返回安装目录。"""
        plugin = await self.get_plugin(name)
        if plugin is None:
            raise ValueError(f"插件 {name} 不存在于索引中")

        install_dir = Path(install_dir or Path.home() / ".aether" / "plugins")
        target = install_dir / name
        target.mkdir(parents=True, exist_ok=True)

        # 下载插件包
        url = plugin.download_url
        if not url:
            raise ValueError(f"插件 {name} 缺少下载地址")

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content

        # 校验 SHA256
        if plugin.sha256:
            actual = hashlib.sha256(content).hexdigest()
            if actual != plugin.sha256:
                raise ValueError(
                    f"插件 {name} 哈希校验失败: 期望 {plugin.sha256}, 实际 {actual}"
                )

        # 写入文件
        pkg_file = target / f"{name}-{version}.aether-plugin"
        pkg_file.write_bytes(content)

        # 写元数据
        meta = {
            "name": plugin.name,
            "version": version,
            "installed_at": time.time(),
            "source": self.registry_url,
        }
        (target / "plugin.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return target

    async def list_installed(self, install_dir: str | Path | None = None) -> list[dict]:
        """列出已安装插件。"""
        install_dir = Path(install_dir or Path.home() / ".aether" / "plugins")
        if not install_dir.exists():
            return []
        result = []
        for d in install_dir.iterdir():
            meta_file = d / "plugin.json"
            if meta_file.exists():
                result.append(json.loads(meta_file.read_text(encoding="utf-8")))
        return result

    async def uninstall(self, name: str, install_dir: str | Path | None = None) -> bool:
        """卸载插件。"""
        import shutil

        install_dir = Path(install_dir or Path.home() / ".aether" / "plugins")
        target = install_dir / name
        if target.exists():
            shutil.rmtree(target)
            return True
        return False
