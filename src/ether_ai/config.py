"""运行时配置加载 — 从 YAML 读取 LLM/ curiosity/ 策略等配置。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ether_ai.llm.backends import BaseLLMBackend, create_backend


DEFAULT_CONFIG_PATHS = [
    Path("configs/llm.yaml"),
    Path(__file__).resolve().parent.parent.parent / "configs" / "llm.yaml",
]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载 YAML 配置文件，找不到时返回默认 echo 配置。"""
    candidates = [Path(path)] if path else DEFAULT_CONFIG_PATHS
    for p in candidates:
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return data.get("llm", data)
    # 回退默认
    return {"backend": "echo", "temperature": 0.7, "max_tokens": 2048}


def build_llm_backend(config: dict[str, Any] | None = None) -> BaseLLMBackend:
    """根据配置字典构建 LLM 后端。

    - backend=echo → EchoBackend
    - backend=openai → 读 openai 子配置
    - backend=hf/vllm → 读对应子配置
    - 若指定后端不可用，自动回退到 echo。
    """
    cfg = config or load_config()
    name = cfg.get("backend", "echo")
    sub = cfg.get(name, {}) or {}

    try:
        backend = create_backend(name, **sub)
    except TypeError:
        # 子配置字段与后端构造函数不匹配时，用空参重试
        backend = create_backend(name)

    if name != "echo" and not backend.is_available():
        from rich import print as rprint
        rprint(f"[yellow]⚠ 后端 {name} 不可用，回退到 echo。[/yellow]")
        return create_backend("echo")
    return backend
