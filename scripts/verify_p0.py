"""P0 端到端验证脚本。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))

from ether_ai.agent.kernel import AgentKernel
from ether_ai.agent.tools_real import REAL_TOOLS
from ether_ai.safety.policy_dsl import PolicyDSL, PolicyRule
from ether_ai.memory.vector_memory import LocalVectorMemory
from ether_ai.llm.backends import EchoBackend

print("=== 1. 真实工具 ===")
print(REAL_TOOLS["python_exec"].run(expression="sum(range(1,101))"))
print(REAL_TOOLS["file_list"].run(path="src/ether_ai/agent"))

print("\n=== 2. 策略 + 自动审批（拒绝写文件）===")
def deny_write(tc):
    print(f"  [approver] 拒绝 {tc.tool_name}")
    return False

dsl = PolicyDSL([PolicyRule(name="w", action_pattern="file_write",
                           effect="require_approval", reason="写文件需审批")])
k = AgentKernel(max_steps=3, policy=dsl, approver=deny_write)
k.run("请计算 2+2")

print("\n=== 3. 记忆持久化 ===")
m = LocalVectorMemory(dim=64)
m.add("AETHER 好奇心驱动")
m.add("向量检索余弦相似度")
m.save("tests/_tmp_mem")
m2 = LocalVectorMemory.load("tests/_tmp_mem")
print(f"  恢复后记录数: {len(m2._records)}")
hits = [r["text"] for r in m2.retrieve("好奇心", top_k=2)]
print(f"  检索命中: {hits}")

print("\n=== 4. LLM 规划器（echo 后端应自动回退规则）===")
k2 = AgentKernel(max_steps=3, llm_backend=EchoBackend())
k2.run("计算 3*3")
