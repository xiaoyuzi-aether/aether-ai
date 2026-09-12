"""agent kernel + 记忆持久化 + 真实工具单测。"""
from __future__ import annotations

from pathlib import Path

from ether_ai.agent.kernel import AgentKernel, ToolCall
from ether_ai.agent.tools_real import PythonExecTool, FileWriteTool, FileReadTool
from ether_ai.memory.vector_memory import LocalVectorMemory
from ether_ai.safety.policy_dsl import PolicyDSL, PolicyRule


# ── kernel ────────────────────────────────────────────────
def test_kernel_calculation_task():
    k = AgentKernel(max_steps=5)
    report = k.run("请计算 23 * 4 等于多少")
    assert report["done"]
    assert report["steps_used"] <= 3
    actions = [h["action"] for h in report["history"]]
    assert "calculator" in actions


def test_kernel_finish_early():
    k = AgentKernel(max_steps=10)
    report = k.run("搜索什么是 AETHER")
    assert report["done"]
    assert report["steps_used"] <= 3


def test_kernel_policy_blocks():
    dsl = PolicyDSL([
        PolicyRule(name="x", action_pattern="self_replicate", effect="block", reason="no"),
    ])
    k = AgentKernel(max_steps=3, policy=dsl)
    obs = k._execute(ToolCall("self_replicate", {}))
    assert "BLOCKED" in obs.content


def test_kernel_approver_rejects():
    calls = []
    def always_reject(tc):
        calls.append(tc.tool_name)
        return False
    dsl = PolicyDSL([
        PolicyRule(name="w", action_pattern="file_write", effect="require_approval", reason="x"),
    ])
    k = AgentKernel(max_steps=3, policy=dsl, approver=always_reject)
    obs = k._execute(ToolCall("file_write", {"path": "x.txt", "content": "y"}))
    assert "REJECTED" in obs.content
    assert calls == ["file_write"]


# ── 真实工具 ──────────────────────────────────────────────
def test_python_exec_sandbox():
    t = PythonExecTool()
    assert "5050" in t.run(expression="sum(range(1,101))")
    assert "错误" in t.run(expression="__import__('os').system('echo hi')")


def test_file_write_read(tmp_path: Path):
    p = tmp_path / "note.txt"
    w = FileWriteTool()
    r = FileReadTool()
    w.run(path=str(p), content="hello aether")
    out = r.run(path=str(p))
    assert "hello aether" in out


# ── 记忆持久化 ─────────────────────────────────────────────
def test_memory_save_load(tmp_path: Path):
    m = LocalVectorMemory(dim=32)
    m.add("alpha 第一条")
    m.add("beta 第二条")
    m.save(tmp_path / "mem")
    m2 = LocalVectorMemory.load(tmp_path / "mem")
    assert len(m2._records) == 2
    hits = [h["text"] for h in m2.retrieve("alpha", top_k=1)]
    assert hits[0] == "alpha 第一条"
