"""AETHER HTTP API 层 — 把 AgentKernel 暴露为 REST 服务。

启动:
    uvicorn ether_ai.api:app --reload --port 8765
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ether_ai.agent.kernel import AgentKernel
from ether_ai.config import build_llm_backend
from ether_ai.memory.vector_memory import LocalVectorMemory
from ether_ai.safety.policy_dsl import PolicyDSL

app = FastAPI(title="AETHER", version="0.3.0", description="好奇心驱动的自主智能体内核")

# 全局单例：启动时构建
_policy = PolicyDSL.from_yaml("configs/policies.yaml")
_memory = LocalVectorMemory()
_pending_approvals: dict[str, bool] = {}  # tool_call_id -> approved


def _approver(tc) -> bool:
    """把审批请求挂起，等待 POST /approve 决策。"""
    _pending_approvals[tc.tool_call_id] = False
    # 在同步 context 里简单轮询；生产应换 asyncio.Event
    import time
    for _ in range(300):  # 最多等 30 秒
        if _pending_approvals.get(tc.tool_call_id):
            return True
        time.sleep(0.1)
    return False


def _build_kernel(max_steps: int = 10) -> AgentKernel:
    return AgentKernel(
        max_steps=max_steps,
        llm_backend=build_llm_backend(),
        policy=_policy,
        approver=_approver,
        memory=_memory,
    )


class RunRequest(BaseModel):
    task: str
    max_steps: int = 10


class ApproveRequest(BaseModel):
    tool_call_id: str
    approved: bool


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}


@app.get("/tools")
def list_tools():
    k = _build_kernel()
    return {
        name: tool.description
        for name, tool in k.tools.items()
    }


@app.post("/run")
def run_task(req: RunRequest):
    """同步跑一个任务，返回完整步骤历史。"""
    try:
        kernel = _build_kernel(max_steps=req.max_steps)
        report = kernel.run(req.task)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pending-approvals")
def pending_approvals():
    """列出等待审批的动作。"""
    return {"pending": list(_pending_approvals.keys())}


@app.post("/approve")
def approve(req: ApproveRequest):
    """审批一个挂起的动作。"""
    if req.tool_call_id not in _pending_approvals:
        raise HTTPException(status_code=404, detail="tool_call_id not pending")
    _pending_approvals[req.tool_call_id] = req.approved
    return {"approved": req.approved}


@app.get("/memory")
def memory_dump():
    """查看向量记忆内容。"""
    return {
        "stats": _memory.stats(),
        "records": [r.text for r in _memory._records],
    }
