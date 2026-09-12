"""AETHER LLM 后端统一接入层 — 支持 HuggingFace / vLLM / OpenAI 兼容接口。"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class BaseLLMBackend(ABC):
    """所有 LLM 后端的抽象基类。"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class EchoBackend(BaseLLMBackend):
    """离线回显后端，用于纯 CPU 测试。"""

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return LLMResponse(text=f"[Echo] {prompt}", model="echo")

    def is_available(self) -> bool:
        return True


class OpenAICompatibleBackend(BaseLLMBackend):
    """OpenAI 兼容接口 — 适配 Ollama / LM Studio / vLLM / OpenAI 官方。"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "",
        model: str = "llama3",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "not-needed")
        self.model = model
        self.timeout = timeout

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
        )

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


class HuggingFaceBackend(BaseLLMBackend):
    """本地 HuggingFace 模型推理（需安装 transformers + torch）。"""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-0.5B-Instruct", device: str = "auto"):
        self.model_name = model_name
        self.device = device
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-generation",
                model=self.model_name,
                device_map=self.device,
                torch_dtype="auto",
            )

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        self._load()
        out = self._pipeline(
            prompt,
            max_new_tokens=kwargs.get("max_tokens", 512),
            temperature=kwargs.get("temperature", 0.7),
            do_sample=True,
        )
        text = out[0]["generated_text"]
        if text.startswith(prompt):
            text = text[len(prompt):]
        return LLMResponse(text=text.strip(), model=self.model_name)

    def is_available(self) -> bool:
        try:
            import transformers  # noqa: F401

            return True
        except ImportError:
            return False


class VLLMBackend(BaseLLMBackend):
    """vLLM 高性能推理后端（需 pip install vllm）。"""

    def __init__(self, model: str = "Qwen/Qwen2.5-7B-Instruct"):
        self.model_name = model
        self._engine = None

    def _load(self):
        if self._engine is None:
            from vllm import LLM

            self._engine = LLM(model=self.model_name)

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        self._load()
        from vllm import SamplingParams

        params = SamplingParams(
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
        )
        outputs = self._engine.generate([prompt], params)
        return LLMResponse(text=outputs[0].outputs[0].text, model=self.model_name)

    def is_available(self) -> bool:
        try:
            import vllm  # noqa: F401

            return True
        except ImportError:
            return False


# ── 后端工厂 ──────────────────────────────────────────────
BACKEND_REGISTRY: dict[str, type[BaseLLMBackend]] = {
    "echo": EchoBackend,
    "openai": OpenAICompatibleBackend,
    "hf": HuggingFaceBackend,
    "vllm": VLLMBackend,
}


def create_backend(name: str, **kwargs: Any) -> BaseLLMBackend:
    """根据配置创建 LLM 后端实例。"""
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未知后端: {name}，可选: {list(BACKEND_REGISTRY)}")
    return cls(**kwargs)
