"""Ray 分布式 EtherNet 消息总线 — 支持多节点智能体协作。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:
    import ray

    HAS_RAY = True
except ImportError:
    HAS_RAY = False


class MessageType(str, Enum):
    BROADCAST = "broadcast"
    P2P = "p2p"
    REQUEST = "request"
    RESPONSE = "response"
    DELEGATE = "delegate"
    VOTE = "vote"
    DEBATE = "debate"
    AUCTION = "auction"


@dataclass
class Message:
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    msg_type: MessageType = MessageType.BROADCAST
    sender: str = ""
    receiver: str = ""          # 空 = 广播
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


if HAS_RAY:

    @ray.remote
    class RayEtherBus:
        """Ray Actor 实现的分布式消息总线，所有节点共享。"""

        def __init__(self):
            self._mailboxes: dict[str, list[dict]] = {}
            self._audit: list[dict] = []
            self._start_time = time.time()

        def register(self, agent_id: str) -> bool:
            if agent_id not in self._mailboxes:
                self._mailboxes[agent_id] = []
            return True

        def send(self, msg: dict) -> bool:
            msg_id = msg.get("msg_id", uuid.uuid4().hex[:12])
            msg["msg_id"] = msg_id
            msg["timestamp"] = time.time()
            self._audit.append(msg)
            receiver = msg.get("receiver", "")
            if receiver:
                self._mailboxes.setdefault(receiver, []).append(msg)
            else:
                for aid in self._mailboxes:
                    if aid != msg.get("sender"):
                        self._mailboxes[aid].append(msg)
            return True

        def receive(self, agent_id: str, max_count: int = 10) -> list[dict]:
            box = self._mailboxes.get(agent_id, [])
            msgs, self._mailboxes[agent_id] = box[:max_count], box[max_count:]
            return msgs

        def request_response(
            self, sender: str, receiver: str, payload: dict, timeout: float = 30.0
        ) -> dict | None:
            """请求-响应模式：发送请求并等待响应。"""
            req = Message(
                msg_type=MessageType.REQUEST,
                sender=sender,
                receiver=receiver,
                payload=payload,
            )
            self.send(req.__dict__)
            deadline = time.time() + timeout
            while time.time() < deadline:
                msgs = self.receive(sender, max_count=50)
                for m in msgs:
                    if (
                        m.get("msg_type") == MessageType.RESPONSE.value
                        and m.get("payload", {}).get("reply_to") == req.msg_id
                    ):
                        return m["payload"]
                time.sleep(0.05)
            return None

        def delegate(self, sender: str, receiver: str, task: dict) -> dict:
            """委派模式：将任务委托给其他智能体。"""
            msg = Message(
                msg_type=MessageType.DELEGATE,
                sender=sender,
                receiver=receiver,
                payload={"task": task, "delegated_by": sender},
            )
            self.send(msg.__dict__)
            return {"status": "delegated", "msg_id": msg.msg_id}

        def vote(self, sender: str, topic: str, options: list[str], voters: list[str]) -> dict:
            """投票模式：向多个智能体发起投票。"""
            msg = Message(
                msg_type=MessageType.VOTE,
                sender=sender,
                payload={"topic": topic, "options": options, "voters": voters},
            )
            self.send(msg.__dict__)
            return {"status": "voting_started", "msg_id": msg.msg_id}

        def get_stats(self) -> dict:
            return {
                "total_agents": len(self._mailboxes),
                "total_messages": len(self._audit),
                "uptime": time.time() - self._start_time,
                "agents": list(self._mailboxes.keys()),
            }

        def get_audit_log(self, limit: int = 100) -> list[dict]:
            return self._audit[-limit:]

    @ray.remote
    class RayAgent:
        """Ray Actor 包装的智能体，可分布式部署。"""

        def __init__(self, agent_id: str, bus_handle: Any):
            self.agent_id = agent_id
            self.bus = bus_handle

        def register(self):
            ray.get(self.bus.register.remote(self.agent_id))
            return self.agent_id

        def process_messages(self, handler_fn: Any = None) -> list[dict]:
            """拉取并处理消息。handler_fn 为可选的远程处理函数句柄。"""
            msgs = ray.get(self.bus.receive.remote(self.agent_id))
            if handler_fn and msgs:
                results = ray.get(handler_fn.remote(msgs))
                return results
            return msgs

        def send(self, msg_dict: dict):
            ray.get(self.bus.send.remote(msg_dict))


class LocalEtherBus:
    """本地回退总线 — 无 Ray 环境下使用，接口与 RayEtherBus 一致。"""

    def __init__(self):
        self._mailboxes: dict[str, list[dict]] = {}
        self._audit: list[dict] = []

    def register(self, agent_id: str) -> bool:
        self._mailboxes.setdefault(agent_id, [])
        return True

    def send(self, msg: dict) -> bool:
        msg.setdefault("msg_id", uuid.uuid4().hex[:12])
        msg["timestamp"] = time.time()
        self._audit.append(msg)
        receiver = msg.get("receiver", "")
        if receiver:
            self._mailboxes.setdefault(receiver, []).append(msg)
        else:
            for aid in self._mailboxes:
                if aid != msg.get("sender"):
                    self._mailboxes[aid].append(msg)
        return True

    def receive(self, agent_id: str, max_count: int = 10) -> list[dict]:
        box = self._mailboxes.get(agent_id, [])
        msgs, self._mailboxes[agent_id] = box[:max_count], box[max_count:]
        return msgs

    def get_stats(self) -> dict:
        return {
            "total_agents": len(self._mailboxes),
            "total_messages": len(self._audit),
            "agents": list(self._mailboxes.keys()),
        }


def create_bus(distributed: bool = False) -> Any:
    """创建消息总线。distributed=True 时使用 Ray，否则本地回退。"""
    if distributed and HAS_RAY:
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)
        return RayEtherBus.remote()
    return LocalEtherBus()
