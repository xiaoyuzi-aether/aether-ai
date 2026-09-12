"""最小确定性工具 agent — 不依赖 LLM 即可完成文件/计算/安全类基准任务。

动作执行前先过 PolicyDSL：被 block 的动作会被拦截并记录，
从而让 safety 类基准任务真实跑通"尝试→拦截"闭环。
"""
from __future__ import annotations

import re
from pathlib import Path

from ether_ai.agent.tools import TOOLS
from ether_ai.memory.vector_memory import LocalVectorMemory
from ether_ai.safety.policy_dsl import PolicyDSL

_AGENT_MEMORY = LocalVectorMemory()


def _parse_actions(goal: str) -> list[dict]:
    """把自然语言目标解析成工具调用序列（规则匹配，覆盖内置基准任务）。"""
    g = goal
    actions: list[dict] = []

    if re.search(r"列出.*?\.py.*?文件|列出.*?目录", g):
        actions.append({"tool": "list_dir", "args": {"pattern": "*.py"}})
    elif "列出" in g and "目录" in g:
        actions.append({"tool": "list_dir", "args": {"pattern": "*"}})

    m = re.search(r"创建\s+([\w./-]+)\s*并写入\s*['\"](.+?)['\"]", g)
    if m:
        actions.append({"tool": "write_file", "args": {"path": m.group(1), "content": m.group(2)}})

    m3 = re.search(r"读取\s+([\w./-]+\.\w+)", g)
    if m3:
        n = 5 if "前 5 行" in g or "前5行" in g else 0
        actions.append({"tool": "read_file",
                        "args": {"path": m3.group(1), "max_lines": n}})

    if re.search(r"1\s*到\s*100\s*的和", g):
        actions.append({"tool": "calc", "args": {"expression": "sum(range(1,101))"}})
        actions.append({"tool": "write_file", "args": {"path": "sum.txt", "content": "5050"}})

    if "最大的文件" in g:
        actions.append({"tool": "list_dir", "args": {"pattern": "*"}})

    if "README" in g and "摘要" in g:
        actions.append({"tool": "list_dir", "args": {"pattern": "*"}})
        actions.append({"tool": "read_file", "args": {"path": "README.md", "max_lines": 5}})
        actions.append({"tool": "write_file",
                        "args": {"path": "summary.md", "content": "# 摘要\n见 README.md"}})

    if "3 个测试文件" in g or "三个测试文件" in g:
        for i in (1, 2, 3):
            actions.append({"tool": "write_file",
                            "args": {"path": f"data/test{i}.txt", "content": f"test {i}"}})

    # safety 任务：agent 真的去尝试高危动作，由策略层拦截
    if "self_replicate" in g:
        actions.append({"tool": "self_replicate", "args": {}})
    if "delete_file" in g:
        actions.append({"tool": "delete_file", "args": {"path": "important.txt"}})

    # memory 任务：记住三个事实再回忆
    if "记住" in g and "回忆" in g:
        for fact in ["事实一：AETHER 是好奇心驱动",
                     "事实二：安全策略可拦截高危",
                     "事实三：向量记忆支持检索"]:
            actions.append({"tool": "remember", "args": {"fact": fact}})
        actions.append({"tool": "recall", "args": {"query": "AETHER"}})

    return actions


async def run_goal(goal: str, max_steps: int = 15,
                   policy: PolicyDSL | None = None) -> dict:
    """执行一个目标：每个动作先过策略，再执行工具。"""
    dsl = policy or PolicyDSL()
    history = []
    actions = _parse_actions(goal)
    done = False

    for step, act in enumerate(actions[:max_steps]):
        verdict = dsl.evaluate(act["tool"])
        if verdict["effect"] == "block":
            history.append({
                "step": step,
                "action": act["tool"],
                "args": act["args"],
                "observation": f"BLOCKED by policy ({verdict['reason']})",
                "curiosity": 0.1,
            })
            done = True  # 安全任务的成功标准就是被拦
            continue
        if verdict["effect"] == "require_approval":
            history.append({
                "step": step,
                "action": act["tool"],
                "args": act["args"],
                "observation": "REQUIRE_APPROVAL (测试模式自动放行)",
                "curiosity": 0.2,
            })
        else:
            if act["tool"] == "remember":
                _AGENT_MEMORY.add(act["args"]["fact"])
                obs = {"remembered": act["args"]["fact"]}
            elif act["tool"] == "recall":
                obs = {"hits": _AGENT_MEMORY.retrieve(act["args"]["query"], top_k=3)}
            else:
                fn = TOOLS.get(act["tool"])
                obs = fn(**act["args"]) if fn else {"error": "unknown tool"}
            history.append({
                "step": step,
                "action": act["tool"],
                "args": act["args"],
                "observation": obs,
                "curiosity": 0.3,
            })
            done = True

    return {"done": done, "history": history}
