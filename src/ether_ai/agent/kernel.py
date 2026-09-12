"""
kernel.py
智能体内核 — 感知 → 规划 → 执行 → 反思 的完整回路。
max_steps 预算约束下的自主任务循环。
纯标准库实现，无外部依赖。Python 3.10+。
"""
from __future__ import annotations

import time
import json
import uuid
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════════
# 1. 状态与数据结构
# ═══════════════════════════════════════════════════════════════════
class Phase(str, Enum):
    PERCEPTION = "perception"
    PLANNING = "planning"
    EXECUTION = "execution"
    REFLECTION = "reflection"


class StepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolCall:
    """执行阶段的具体工具调用。"""
    tool_name: str
    arguments: dict[str, Any]
    tool_call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class Observation:
    """感知阶段接收到的环境/工具反馈。"""
    content: str
    source: str = "environment"
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReflectionResult:
    """反思阶段的评估结果。"""
    status: StepStatus
    reason: str
    should_continue: bool = True
    updated_plan: str | None = None


@dataclass
class StepRecord:
    """单步循环的历史记录，用于记忆和反思。"""
    step_id: int
    phase: Phase
    thought: str
    action: ToolCall | None = None
    observation: Observation | None = None
    reflection: ReflectionResult | None = None
    duration: float = 0.0


@dataclass
class AgentState:
    """智能体的全局状态。"""
    task: str
    max_steps: int = 10
    current_step: int = 0
    done: bool = False
    history: list[StepRecord] = field(default_factory=list)
    short_term_memory: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def add_record(self, record: StepRecord):
        self.history.append(record)
        # 维护一个短时记忆窗口
        self.short_term_memory.append(f"[Step {record.step_id}] {record.thought}")
        if len(self.short_term_memory) > 5:
            self.short_term_memory.pop(0)

    def get_context(self, last_n: int = 3) -> str:
        """获取最近 N 步的上下文，供感知和规划使用。"""
        recent = self.history[-last_n:]
        if not recent:
            return "无历史记录。"
        lines = []
        for r in recent:
            lines.append(f"步骤 {r.step_id}: {r.thought}")
            if r.action:
                lines.append(f"  执行: {r.action.tool_name}({r.action.arguments})")
            if r.observation:
                lines.append(f"  观察: {r.observation.content[:80]}")
        return "\n".join(lines)

    def budget_remaining(self) -> int:
        return max(0, self.max_steps - self.current_step)


# ═══════════════════════════════════════════════════════════════════
# 2. 工具集（模拟外部能力）
# ═══════════════════════════════════════════════════════════════════
class BaseTool:
    name: str = "base"
    description: str = "基础工具"

    def run(self, **kwargs) -> str:
        raise NotImplementedError


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "计算数学表达式。参数: expression"

    def run(self, expression: str = "", **kwargs) -> str:
        try:
            # 安全评估：仅允许数字和基本运算符
            if not re.match(r"^[\d\s\+\-\*\/\(\)\.]+$", expression):
                return f"错误: 表达式包含非法字符 '{expression}'"
            result = eval(expression, {"__builtins__": {}}, {})
            return f"计算结果: {expression} = {result}"
        except Exception as e:
            return f"计算失败: {e}"


class SearchTool(BaseTool):
    name = "search"
    description = "搜索知识库。参数: query"

    # 模拟一个小型知识库
    KNOWLEDGE = {
        "python": "Python 是一种解释型、面向对象的高级编程语言。",
        "aether": "AETHER 是一个好奇心驱动的自主智能体内核与生态协议。",
        "jepa": "JEPA (Joint Embedding Predictive Architecture) 是 LeCun 提出的世界模型架构。",
        "mesh": "去中心化 Mesh 网络是一种无中心节点的 P2P 拓扑结构。",
    }

    def run(self, query: str = "", **kwargs) -> str:
        query_lower = query.lower()
        for key, val in self.KNOWLEDGE.items():
            if key in query_lower:
                return f"知识库匹配 [{key}]: {val}"
        return f"未在知识库中找到 '{query}' 的相关信息。"


class MemoryTool(BaseTool):
    name = "memory"
    description = "读写长期记忆。参数: action(store/retrieve), content"

    def __init__(self):
        self._store: list[str] = []

    def run(self, action: str = "retrieve", content: str = "", **kwargs) -> str:
        if action == "store":
            self._store.append(content)
            return f"已存储到长期记忆: {content[:50]}"
        elif action == "retrieve":
            if not self._store:
                return "长期记忆为空。"
            return "长期记忆内容:\n" + "\n".join(f"- {c}" for c in self._store[-5:])
        return f"未知操作: {action}"


class FinishTool(BaseTool):
    name = "finish"
    description = "标记任务完成。参数: summary"

    def run(self, summary: str = "", **kwargs) -> str:
        return f"任务已完成。总结: {summary}"


# ═══════════════════════════════════════════════════════════════════
# 3. 智能体内核
# ═══════════════════════════════════════════════════════════════════
class AgentKernel:
    """智能体内核。
    严格实现 感知 → 规划 → 执行 → 反思 的闭环。
    受 max_steps 预算约束，自主决定任务是否完成。
    """

    def __init__(
        self,
        max_steps: int = 10,
        llm_backend=None,
        policy=None,
        approver=None,
        memory=None,
    ):
        self.max_steps = max_steps
        self.llm = llm_backend  # BaseLLMBackend 或 None（None=规则模式）
        self.policy = policy  # PolicyDSL 或 None（不做策略检查）
        # approver: Callable[[ToolCall], bool]；返回 True 才放行
        self.approver = approver or self._default_approver
        self.memory = memory  # LocalVectorMemory 或 None
        self.tools: dict[str, BaseTool] = {
            "calculator": CalculatorTool(),
            "search": SearchTool(),
            "memory": MemoryTool(),
            "finish": FinishTool(),
        }
        # 挂上真实外部工具
        from ether_ai.agent.tools_real import REAL_TOOLS
        self.tools.update(REAL_TOOLS)
        self.state: AgentState | None = None

    @staticmethod
    def _default_approver(tool_call: ToolCall) -> bool:
        """默认审批：命令行 y/n。CI/API 场景可注入自定义 approver。"""
        try:
            ans = input(f"  ⚠️  审批: 允许执行 {tool_call.tool_name}{tool_call.arguments}? [y/N] ")
            return ans.strip().lower() in ("y", "yes")
        except EOFError:
            return False

    # ── 核心循环 ─────────────────────────────────────────────────
    def run(self, task: str) -> dict[str, Any]:
        """运行完整的自主任务循环。"""
        self.state = AgentState(task=task, max_steps=self.max_steps)
        print(f"\n{'='*60}")
        print(f"🚀 启动任务: {task}")
        print(f"   预算约束: max_steps={self.max_steps}")
        print(f"{'='*60}")

        while not self.state.done and self.state.budget_remaining() > 0:
            self.state.current_step += 1
            step_id = self.state.current_step
            step_start = time.time()
            print(f"\n--- Step {step_id}/{self.max_steps} ---")

            # 1. 感知 (Perception)
            perception = self._perceive()
            print(f"  👁️  感知: {perception[:100]}...")

            # 2. 规划 (Planning)
            thought, tool_call = self._plan(perception)
            print(f"  🧠 规划: {thought}")
            if tool_call:
                print(f"     决策调用工具: {tool_call.tool_name}({tool_call.arguments})")

            # 3. 执行 (Execution)
            observation = None
            if tool_call:
                observation = self._execute(tool_call)
                print(f"  ⚙️  执行: {observation.content[:100]}...")

            # 4. 反思 (Reflection)
            reflection = self._reflect(thought, tool_call, observation)
            print(f"  🤔 反思: [{reflection.status.value}] {reflection.reason}")

            # 记录
            record = StepRecord(
                step_id=step_id,
                phase=Phase.REFLECTION,
                thought=thought,
                action=tool_call,
                observation=observation,
                reflection=reflection,
                duration=time.time() - step_start,
            )
            self.state.add_record(record)

            # 终止条件
            if not reflection.should_continue:
                self.state.done = True
                print(f"\n  ✅ 任务在 Step {step_id} 提前完成。")
                break

        # 循环结束后的处理
        if not self.state.done:
            print(f"\n  ⚠️ 达到 max_steps={self.max_steps} 预算上限，任务未完成。")
            self.state.done = True
        return self._summarize()

    # ── 四大阶段实现 ─────────────────────────────────────────────
    def _perceive(self) -> str:
        """感知阶段：整合任务、历史记忆和最近观察。"""
        ctx = self.state.get_context(last_n=3)
        perception = (
            f"当前任务: {self.state.task}\n"
            f"剩余步数: {self.state.budget_remaining()}\n"
            f"最近历史:\n{ctx}"
        )
        return perception

    def _plan(self, perception: str) -> tuple[str, ToolCall | None]:
        """规划阶段：优先用 LLM，失败回退规则引擎。"""
        # 0) LLM 规划分支
        if self.llm is not None:
            llm_plan = self._plan_with_llm(perception)
            if llm_plan is not None:
                return llm_plan
        # 1..5) 规则引擎（原逻辑）
        task = self.state.task.lower()
        history_text = " ".join(r.thought for r in self.state.history).lower()
        history_actions = " ".join(
            (r.action.tool_name if r.action else "") for r in self.state.history
        ).lower()
        memory_tool = self.tools["memory"]

        # 规则 1：如果任务包含计算，调用计算器（算过一次就 finish）
        math_match = re.search(r"[\d\s\+\-\*\/\(\)\.]+", task)
        if math_match and ("计算" in task or "等于" in task or "=" in task):
            if "calculator" in history_actions:
                return "计算已完成，准备总结。", ToolCall("finish", {"summary": f"计算结果已得出。"})
            expr = math_match.group().strip()
            if expr:
                return f"任务需要计算，提取表达式 '{expr}'。", ToolCall("calculator", {"expression": expr})

        # 规则 2：如果需要搜索知识
        if "搜索" in task or "查找" in task or "什么是" in task or "介绍" in task:
            if "search" not in history_actions:
                # 提取查询关键词
                query = task.replace("搜索", "").replace("查找", "").replace("什么是", "").strip()
                return f"任务需要搜索知识，查询 '{query}'。", ToolCall("search", {"query": query})

        # 规则 3：如果需要记忆
        if "记住" in task or "存储" in task:
            if "store" not in history_text:
                return "任务要求存储信息到长期记忆。", ToolCall("memory", {"action": "store", "content": task})

        # 规则 4：如果之前搜索过，准备总结
        if "search" in history_actions and "finish" not in history_actions:
            return "已获取信息，准备总结并完成任务。", ToolCall("finish", {"summary": f"完成了对任务 '{self.state.task}' 的探索。"})

        # 规则 5：兜底策略
        if self.state.budget_remaining() <= 1:
            return "预算即将耗尽，强制结束任务。", ToolCall("finish", {"summary": "预算耗尽，提前结束。"})

        return "没有明确规则匹配，尝试搜索任务关键词。", ToolCall("search", {"query": self.state.task[:20]})

    def _plan_with_llm(self, perception: str) -> tuple[str, ToolCall | None] | None:
        """用 LLM 生成下一步动作。输出 JSON: {"thought","tool","args"}。
        解析失败或工具不存在时返回 None，回退规则引擎。
        """
        import json as _json
        tool_desc = "\n".join(f"  - {n}: {t.description}" for n, t in self.tools.items())
        prompt = (
            f"你是 AETHER 智能体。请决定下一步动作。\n"
            f"任务上下文:\n{perception}\n\n"
            f"可用工具:\n{tool_desc}\n\n"
            f"仅输出 JSON: {{\"thought\": \"...\", \"tool\": \"工具名\", \"args\": {{...}}}}。"
            f"完成任务时 tool 用 \"finish\"。"
        )
        try:
            import asyncio
            resp = asyncio.run(self.llm.generate(prompt, max_tokens=256, temperature=0.2))
            text = resp.text.strip()
            # 提取 JSON（容忍 ```json 包裹）
            m = __import__("re").search(r"\{.*\}", text, __import__("re").DOTALL)
            if not m:
                return None
            data = _json.loads(m.group())
            tool_name = data.get("tool", "")
            if tool_name not in self.tools:
                return None
            return (
                data.get("thought", f"LLM 决定调 {tool_name}"),
                ToolCall(tool_name, data.get("args", {})),
            )
        except Exception:
            return None

    def _execute(self, tool_call: ToolCall) -> Observation:
        """执行阶段：先过策略，再审批，最后调用工具。"""
        # 1) 策略检查
        if self.policy is not None:
            verdict = self.policy.evaluate(tool_call.tool_name)
            if verdict["effect"] == "block":
                return Observation(
                    content=f"BLOCKED by policy: {verdict['reason']}",
                    source="policy",
                )
            if verdict["effect"] == "require_approval":
                if not self.approver(tool_call):
                    return Observation(
                        content=f"REJECTED by human: {tool_call.tool_name}",
                        source="approval",
                    )
        # 2) 调用工具
        tool = self.tools.get(tool_call.tool_name)
        if not tool:
            return Observation(
                content=f"错误: 未找到工具 '{tool_call.tool_name}'",
                source="system"
            )
        try:
            result = tool.run(**tool_call.arguments)
            # 3) 写入持久记忆（如果接了 memory）
            if self.memory is not None and tool_call.tool_name not in ("finish",):
                self.memory.add(f"{tool_call.tool_name} → {result[:100]}")
            return Observation(content=result, source=tool_call.tool_name)
        except Exception as e:
            return Observation(content=f"工具执行异常: {e}", source="system")

    def _reflect(
        self,
        thought: str,
        tool_call: ToolCall | None,
        observation: Observation | None,
    ) -> ReflectionResult:
        """反思阶段：评估执行结果，决定是否继续。"""
        if tool_call is None:
            return ReflectionResult(
                status=StepStatus.SKIPPED,
                reason="未规划任何动作。",
                should_continue=True,
            )
        if observation is None:
            return ReflectionResult(
                status=StepStatus.FAILED,
                reason="执行阶段未产生观察结果。",
                should_continue=True,
            )
        # 成功调用 finish 工具
        if tool_call.tool_name == "finish":
            return ReflectionResult(
                status=StepStatus.SUCCESS,
                reason="任务已标记完成。",
                should_continue=False,
            )
        # 检查观察结果是否包含错误
        if "错误" in observation.content or "失败" in observation.content:
            return ReflectionResult(
                status=StepStatus.FAILED,
                reason=f"工具执行报错: {observation.content[:50]}",
                should_continue=True,
            )
        # 正常成功
        return ReflectionResult(
            status=StepStatus.SUCCESS,
            reason="执行成功，继续下一步。",
            should_continue=True,
        )

    # ── 总结 ─────────────────────────────────────────────────────
    def _summarize(self) -> dict[str, Any]:
        """生成任务执行报告。"""
        total_time = time.time() - self.state.start_time
        report = {
            "task": self.state.task,
            "done": self.state.done,
            "steps_used": self.state.current_step,
            "max_steps": self.state.max_steps,
            "total_time": round(total_time, 3),
            "history": [
                {
                    "step": r.step_id,
                    "thought": r.thought,
                    "action": r.action.tool_name if r.action else None,
                    "observation": r.observation.content if r.observation else None,
                    "reflection": r.reflection.status.value if r.reflection else None,
                }
                for r in self.state.history
            ],
        }
        print(f"\n{'='*60}")
        print(f"📊 任务执行报告")
        print(f"   状态: {'完成 ✅' if report['done'] else '未完成 ⚠️'}")
        print(f"   步数: {report['steps_used']}/{report['max_steps']}")
        print(f"   耗时: {report['total_time']}s")
        print(f"{'='*60}")
        return report


# ═══════════════════════════════════════════════════════════════════
# 4. 演示与测试
# ═══════════════════════════════════════════════════════════════════
def demo():
    print("=" * 64)
    print("智能体内核 (Agent Kernel) — 感知 → 规划 → 执行 → 反思")
    print("=" * 64)

    # 测试 1: 计算任务
    kernel1 = AgentKernel(max_steps=5)
    kernel1.run("请计算 123 * 456 等于多少")

    # 测试 2: 搜索任务
    kernel2 = AgentKernel(max_steps=5)
    kernel2.run("搜索什么是 AETHER")

    # 测试 3: 多步复合任务（预算受限）
    kernel3 = AgentKernel(max_steps=4)
    kernel3.run("记住 我喜欢 Python，然后搜索 JEPA")

    # 测试 4: 预算耗尽
    kernel4 = AgentKernel(max_steps=2)
    kernel4.run("这是一个无法完成的任务，需要很多步骤")


if __name__ == "__main__":
    demo()
