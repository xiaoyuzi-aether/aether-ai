"""
decentralized_mesh.py
去中心化多智能体协调 — P2P 拓扑 + 合约网拍卖 + 拜占庭容错。
纯标准库实现，无外部依赖。Python 3.10+。
"""
from __future__ import annotations

import heapq
import random
import time
import uuid
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════════
# 1. 消息与协议
# ═══════════════════════════════════════════════════════════════════
class MsgType(str, Enum):
    HELLO = "hello"
    HEARTBEAT = "heartbeat"
    CFP = "cfp"              # Call For Proposal（合约网）
    BID = "bid"
    AWARD = "award"
    RESULT = "result"
    GOSSIP = "gossip"


@dataclass
class Message:
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    msg_type: MsgType = MsgType.HELLO
    sender: str = ""
    target: str = ""          # 空 = 广播
    payload: dict[str, Any] = field(default_factory=dict)
    ttl: int = 3              # gossip 最大跳数
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# 2. 节点
# ═══════════════════════════════════════════════════════════════════
class NodeStatus(str, Enum):
    ALIVE = "alive"
    SUSPECT = "suspect"
    DEAD = "dead"


@dataclass
class AgentNode:
    """一个自治节点。能力集决定它能接受哪些任务。"""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    capabilities: frozenset[str] = frozenset({"compute"})
    status: NodeStatus = NodeStatus.ALIVE
    last_heartbeat: float = field(default_factory=time.time)
    workload: float = 0.0      # 0.0 ~ 1.0，用于拍卖出价
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_alive(self, timeout: float = 5.0) -> bool:
        if self.status == NodeStatus.DEAD:
            return False
        return (time.time() - self.last_heartbeat) < timeout

    def touch(self):
        self.last_heartbeat = time.time()
        if self.status == NodeStatus.SUSPECT:
            self.status = NodeStatus.ALIVE

    def mark_dead(self):
        self.status = NodeStatus.DEAD


# ═══════════════════════════════════════════════════════════════════
# 3. P2P 网络（邻接表 + gossip 传播）
# ═══════════════════════════════════════════════════════════════════
class MeshNetwork:
    """去中心化 P2P 网络。无中心协调者，每个节点维护自己的邻接表。"""

    def __init__(self, heartbeat_timeout: float = 5.0):
        self._nodes: dict[str, AgentNode] = {}
        self._adjacency: dict[str, set[str]] = defaultdict(set)
        self._inbox: dict[str, list[Message]] = defaultdict(list)
        self._audit: list[Message] = []
        self._seen_gossip: set[str] = set()
        self._lock = threading.RLock()
        self.heartbeat_timeout = heartbeat_timeout
        self._start_time = time.time()

    # ── 拓扑 ─────────────────────────────────────────────────────
    def add_node(self, node: AgentNode) -> str:
        with self._lock:
            self._nodes[node.node_id] = node
            self._adjacency[node.node_id]  # 确保存在
        return node.node_id

    def connect(self, a: str, b: str, directed: bool = False):
        with self._lock:
            self._adjacency[a].add(b)
            if not directed:
                self._adjacency[b].add(a)

    def neighbors(self, node_id: str) -> set[str]:
        return self._adjacency.get(node_id, set()).copy()

    def alive_nodes(self) -> list[AgentNode]:
        return [n for n in self._nodes.values() if n.is_alive(self.heartbeat_timeout)]

    # ── 消息路由 ──────────────────────────────────────────────────
    def send(self, msg: Message) -> int:
        """发送消息。target 为空则广播给邻居。返回投递节点数。"""
        with self._lock:
            self._audit.append(msg)
            sender = msg.sender
            targets = [msg.target] if msg.target else list(self._adjacency.get(sender, []))
            delivered = 0
            for t in targets:
                if t in self._nodes and self._nodes[t].is_alive(self.heartbeat_timeout):
                    self._inbox[t].append(msg)
                    delivered += 1
            return delivered

    def broadcast(self, sender: str, msg_type: MsgType, payload: dict) -> int:
        return self.send(Message(msg_type=msg_type, sender=sender, payload=payload))

    def gossip(self, sender: str, msg_type: MsgType, payload: dict, ttl: int = 3) -> int:
        """带 TTL 的 gossip 传播。同一 msg_id 只处理一次。"""
        msg = Message(msg_type=msg_type, sender=sender, payload=payload, ttl=ttl)
        if msg.msg_id in self._seen_gossip:
            return 0
        self._seen_gossip.add(msg.msg_id)
        delivered = self.send(msg)
        if msg.ttl > 1:
            for n in self._adjacency.get(sender, []):
                if n in self._nodes and self._nodes[n].is_alive(self.heartbeat_timeout):
                    # 转发时不增加审计重复
                    self._inbox[n].append(
                        Message(msg_type=msg_type, sender=sender, payload=payload,
                                ttl=msg.ttl - 1, msg_id=msg.msg_id)
                    )
        return delivered

    def receive(self, node_id: str, max_count: int = 20) -> list[Message]:
        with self._lock:
            box = self._inbox.get(node_id, [])
            msgs, self._inbox[node_id] = box[:max_count], box[max_count:]
        return msgs

    # ── 心跳与存活检测 ───────────────────────────────────────────
    def heartbeat(self, node_id: str):
        if node_id in self._nodes:
            self._nodes[node_id].touch()

    def sweep_dead(self) -> list[str]:
        """将超时未心跳的节点标记为 SUSPECT/DEAD。返回被标记的节点。"""
        now = time.time()
        marked = []
        for n in self._nodes.values():
            if n.status == NodeStatus.DEAD:
                continue
            age = now - n.last_heartbeat
            if age > self.heartbeat_timeout * 2:
                n.mark_dead()
                marked.append(n.node_id)
            elif age > self.heartbeat_timeout:
                n.status = NodeStatus.SUSPECT
                marked.append(n.node_id)
        return marked

    # ── 统计 ─────────────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "total_nodes": len(self._nodes),
            "alive": len(self.alive_nodes()),
            "dead": sum(1 for n in self._nodes.values() if n.status == NodeStatus.DEAD),
            "edges": sum(len(v) for v in self._adjacency.values()) // 2,
            "messages": len(self._audit),
            "uptime": round(time.time() - self._start_time, 2),
        }


# ═══════════════════════════════════════════════════════════════════
# 4. 合约网拍卖（Contract Net Protocol）
# ═══════════════════════════════════════════════════════════════════
@dataclass
class Task:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    payload: Any = None
    required_capability: str = "compute"
    priority: float = 0.0


class ContractNetAuction:
    """去中心化任务分配：CFP → BID → AWARD → RESULT。
    每个节点基于自身工作负载和能力独立出价，无中心调度器。
    """

    def __init__(self, net: MeshNetwork):
        self.net = net
        self._pending: dict[str, dict] = {}   # task_id -> {cfp, bids, awarded_to}
        self._results: dict[str, Any] = {}

    # ── 发起拍卖 ─────────────────────────────────────────────────
    def call_for_proposal(self, coordinator: str, task: Task) -> str:
        """广播 CFP。返回 task_id。"""
        self._pending[task.task_id] = {
            "coordinator": coordinator,
            "task": task,
            "bids": {},
            "awarded_to": None,
        }
        self.net.broadcast(coordinator, MsgType.CFP, {
            "task_id": task.task_id,
            "required_capability": task.required_capability,
            "priority": task.priority,
        })
        return task.task_id

    # ── 节点出价 ─────────────────────────────────────────────────
    def submit_bid(self, node_id: str, task_id: str, bid_price: float, eta: float = 1.0):
        """节点提交出价。bid_price 越低越有竞争力。"""
        if task_id not in self._pending:
            return
        self._pending[task_id]["bids"][node_id] = {
            "price": bid_price,
            "eta": eta,
            "timestamp": time.time(),
        }

    def auto_bid(self, node: AgentNode, task_id: str, task: Task):
        """节点根据自身负载和能力自动出价。
        价格 = 基础成本 × (1 + 工作负载) / 能力匹配度
        """
        if task.required_capability not in node.capabilities:
            return  # 能力不足，不出价
        base = 1.0
        load_factor = 1.0 + node.workload * 2.0
        capability_bonus = 1.0 if task.required_capability in node.capabilities else 2.0
        price = base * load_factor / capability_bonus
        eta = 0.5 + node.workload
        self.submit_bid(node.node_id, task_id, round(price, 3), round(eta, 3))

    # ── 授予 ─────────────────────────────────────────────────────
    def award(self, task_id: str) -> str | None:
        """选择出价最低的存活节点。返回被授予的 node_id。"""
        if task_id not in self._pending:
            return None
        entry = self._pending[task_id]
        bids = entry["bids"]
        if not bids:
            return None
        # 过滤掉已死节点
        valid = {
            nid: b for nid, b in bids.items()
            if nid in self.net._nodes and self.net._nodes[nid].is_alive(self.net.heartbeat_timeout)
        }
        if not valid:
            return None
        # 综合价格和 ETA：price × eta 最小者胜
        winner = min(valid.items(), key=lambda kv: kv[1]["price"] * kv[1]["eta"])[0]
        entry["awarded_to"] = winner
        self.net.send(Message(
            msg_type=MsgType.AWARD,
            sender=entry["coordinator"],
            target=winner,
            payload={"task_id": task_id},
        ))
        return winner

    # ── 结果回收 ─────────────────────────────────────────────────
    def submit_result(self, node_id: str, task_id: str, result: Any):
        self._results[task_id] = {"worker": node_id, "result": result}
        if task_id in self._pending:
            self._pending[task_id]["result"] = result

    def get_result(self, task_id: str) -> Any:
        return self._results.get(task_id, {}).get("result")

    def pending_count(self) -> int:
        return len(self._pending)


# ═══════════════════════════════════════════════════════════════════
# 5. 拜占庭容错（多数投票 + 偏差检测）
# ═══════════════════════════════════════════════════════════════════
class ByzantineFaultTolerance:
    """多数投票共识 + 故障节点标记。
    接收 (node_id, value) 列表，返回 (canonical_value, faulty_nodes)。
    相同值的节点数超过 threshold 比例时，该值被接受；否则取众数。
    """

    def __init__(self, threshold: float = 0.67):
        self.threshold = threshold
        self._faulty_history: dict[str, int] = defaultdict(int)

    def collect_and_decide(
        self,
        round_id: str,
        submissions: list[tuple[str, Any]],
    ) -> tuple[Any, list[str]]:
        """submissions: [(node_id, value), ...]"""
        if not submissions:
            return None, []
        # 按值的哈希聚类（兼容不可哈希值用 repr）
        buckets: dict[str, list[tuple[str, Any]]] = defaultdict(list)
        for nid, val in submissions:
            key = self._safe_key(val)
            buckets[key].append((nid, val))
        total = len(submissions)
        # 找最大桶
        best_key = max(buckets, key=lambda k: len(buckets[k]))
        best_bucket = buckets[best_key]
        best_count = len(best_bucket)
        best_value = best_bucket[0][1]
        # 达到阈值则接受
        if best_count / total >= self.threshold:
            canonical = best_value
        else:
            canonical = best_value  # 未达阈值仍取众数，但标记为低置信
        # 标记偏差节点
        faulty = []
        for nid, val in submissions:
            if self._safe_key(val) != best_key:
                faulty.append(nid)
                self._faulty_history[nid] += 1
        return canonical, faulty

    def is_trusted(self, node_id: str, max_faults: int = 3) -> bool:
        return self._faulty_history.get(node_id, 0) < max_faults

    @staticmethod
    def _safe_key(v: Any) -> str:
        try:
            return f"{type(v).__name__}:{v}"
        except Exception:
            return repr(v)


# ═══════════════════════════════════════════════════════════════════
# 6. 协调器（整合拍卖 + BFT + 心跳）
# ═══════════════════════════════════════════════════════════════════
class DecentralizedCoordinator:
    """去中心化协调器：节点自治，通过消息达成任务分配与结果共识。"""

    def __init__(self, net: MeshNetwork):
        self.net = net
        self.auction = ContractNetAuction(net)
        self.bft = ByzantineFaultTolerance(threshold=0.67)

    def run_auction_round(
        self,
        task: Task,
        max_wait: float = 0.5,
    ) -> str | None:
        """一轮完整拍卖：CFP → 收集 BID → AWARD。"""
        alive = self.net.alive_nodes()
        if not alive:
            return None
        coordinator = random.choice(alive).node_id
        task_id = self.auction.call_for_proposal(coordinator, task)
        # 所有存活节点自动出价
        for node in alive:
            self.auction.auto_bid(node, task_id, task)
        time.sleep(max_wait)  # 模拟网络延迟
        winner = self.auction.award(task_id)
        if winner and winner in self.net._nodes:
            self.net._nodes[winner].workload = min(1.0, self.net._nodes[winner].workload + 0.2)
        return winner

    def run_bft_round(
        self,
        round_id: str,
        workers: list[str],
        work_fn: Callable[[str], Any],
        faulty_ids: set[str] | None = None,
    ) -> tuple[Any, list[str]]:
        """让 workers 各自计算结果，再 BFT 投票。faulty_ids 中的节点返回错误值。"""
        faulty_ids = faulty_ids or set()
        submissions = []
        for wid in workers:
            if wid in faulty_ids:
                submissions.append((wid, f"FAULTY_{wid}"))
            else:
                submissions.append((wid, work_fn(wid)))
        return self.bft.collect_and_decide(round_id, submissions)

    def stats(self) -> dict:
        return {
            "network": self.net.stats(),
            "pending_auctions": self.auction.pending_count(),
            "faulty_nodes": dict(self.bft._faulty_history),
        }


# ═══════════════════════════════════════════════════════════════════
# 7. 演示
# ═══════════════════════════════════════════════════════════════════
def demo():
    print("=" * 64)
    print("去中心化多智能体协调 — 演示")
    print("=" * 64)

    # 1. 构建 8 节点部分连接 mesh
    random.seed(42)
    net = MeshNetwork()
    caps = ["compute", "compute", "compute", "vision", "vision", "language"]
    nodes = []
    for i in range(8):
        n = AgentNode(capabilities=frozenset({random.choice(caps), "compute"}))
        net.add_node(n)
        nodes.append(n)

    # 每个节点连接 3 个随机邻居（小世界拓扑）
    for n in nodes:
        for peer in random.sample([x for x in nodes if x != n], k=3):
            net.connect(n.node_id, peer.node_id)

    print(f"\n[拓扑] {net.stats()}")

    coord = DecentralizedCoordinator(net)

    # 2. 拍卖分配任务
    print("\n[拍卖] 分配 5 个任务 ...")
    for i in range(5):
        task = Task(payload=f"job-{i}", required_capability="compute", priority=i)
        winner = coord.run_auction_round(task)
        print(f"  task-{i} → 授予 {winner}  (出价竞争)")

    # 3. 模拟节点故障 + 存活检测
    print("\n[容错] 模拟节点故障 ...")
    dead = nodes[2].node_id
    nodes[2].mark_dead()
    print(f"  节点 {dead} 已标记 DEAD")
    print(f"  存活节点: {len(net.alive_nodes())}/{len(nodes)}")

    # 故障后再拍卖，确认不再分配给它
    task = Task(payload="after-failure", required_capability="compute")
    winner = coord.run_auction_round(task)
    print(f"  故障后拍卖 winner={winner}，不是 dead={dead}: {winner != dead}")

    # 4. BFT 投票
    print("\n[BFT] 5 个 worker 计算结果，其中 1 个拜占庭 ...")
    workers = [n.node_id for n in net.alive_nodes()[:5]]
    faulty = {workers[3]}  # 第 4 个是故障节点

    def work(wid: str) -> int:
        return sum(range(10))

    canonical, faulty_detected = coord.run_bft_round(
        "round-1", workers, work, faulty_ids=faulty
    )
    print(f"  正确值: {canonical}")
    print(f"  检测到故障节点: {faulty_detected}")
    print(f"  与预期故障集一致: {set(faulty_detected) == faulty}")

    # 5. 汇总
    print(f"\n[统计] {coord.stats()}")
    print("\n" + "=" * 64)
    print("演示完成。核心组件: MeshNetwork / ContractNetAuction / BFT")
    print("=" * 64)


if __name__ == "__main__":
    demo()
