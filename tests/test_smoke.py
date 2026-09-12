"""冒烟测试 — 验证核心模块可导入、关键行为正确。"""
from __future__ import annotations

import asyncio

from ether_ai import __version__
from ether_ai.ethernet.ray_bus import LocalEtherBus, create_bus
from ether_ai.eval.benchmarks import BENCHMARK_SUITE
from ether_ai.llm.backends import (
    BACKEND_REGISTRY,
    EchoBackend,
    create_backend,
)
from ether_ai.safety.policy_dsl import PolicyDSL, PolicyRule


def test_version():
    assert __version__ == "0.3.0"


def test_backend_registry():
    assert set(BACKEND_REGISTRY) == {"echo", "openai", "hf", "vllm"}
    assert isinstance(create_backend("echo"), EchoBackend)


def test_echo_backend():
    backend = EchoBackend()
    assert backend.is_available()
    resp = asyncio.run(backend.generate("hi"))
    assert resp.text == "[Echo] hi"
    assert resp.model == "echo"


def test_policy_hardcoded_block():
    dsl = PolicyDSL()
    result = dsl.evaluate("self_replicate")
    assert result["allowed"] is False
    assert result["effect"] == "block"


def test_policy_require_approval():
    dsl = PolicyDSL([
        PolicyRule(name="r1", action_pattern="write_file",
                   effect="require_approval", reason="test"),
    ])
    result = dsl.evaluate("write_file")
    assert result["allowed"] is True
    assert result["effect"] == "require_approval"


def test_local_bus():
    bus = LocalEtherBus()
    bus.register("alice")
    bus.register("bob")
    bus.send({"msg_type": "p2p", "sender": "alice",
              "receiver": "bob", "payload": {"x": 1}})
    msgs = bus.receive("bob")
    assert len(msgs) == 1
    assert msgs[0]["payload"]["x"] == 1


def test_create_bus_local():
    bus = create_bus(distributed=False)
    assert isinstance(bus, LocalEtherBus)


def test_benchmark_suite_loaded():
    assert "file_ops" in BENCHMARK_SUITE
    assert len(BENCHMARK_SUITE["file_ops"]) == 3
