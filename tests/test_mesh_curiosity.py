"""mesh + curiosity 模块单测。"""
from __future__ import annotations

import random

from ether_ai.curiosity.world_model import (
    CuriosityConfig,
    CuriosityEngine,
    GridWorld,
    HashEmbedder,
    LightweightJEPA,
)
from ether_ai.ethernet.decentralized_mesh import (
    AgentNode,
    ByzantineFaultTolerance,
    DecentralizedCoordinator,
    MeshNetwork,
    Task,
)


# ── mesh ─────────────────────────────────────────────────
def test_mesh_topology():
    net = MeshNetwork()
    a, b, c = AgentNode(), AgentNode(), AgentNode()
    net.add_node(a); net.add_node(b); net.add_node(c)
    net.connect(a.node_id, b.node_id)
    net.connect(b.node_id, c.node_id)
    assert len(net.neighbors(b.node_id)) == 2
    assert net.stats()["total_nodes"] == 3


def test_auction_allocates():
    random.seed(1)
    net = MeshNetwork()
    nodes = [AgentNode(capabilities=frozenset({"compute"})) for _ in range(4)]
    for n in nodes:
        net.add_node(n)
    coord = DecentralizedCoordinator(net)
    winner = coord.run_auction_round(Task(payload="x"), max_wait=0.01)
    assert winner in [n.node_id for n in nodes]


def test_bft_detects_faulty():
    bft = ByzantineFaultTolerance(threshold=0.6)
    subs = [("n1", 42), ("n2", 42), ("n3", 42), ("n4", "wrong")]
    canon, faulty = bft.collect_and_decide("r1", subs)
    assert canon == 42
    assert faulty == ["n4"]


def test_dead_node_excluded():
    net = MeshNetwork(heartbeat_timeout=0.01)
    a, b = AgentNode(), AgentNode()
    net.add_node(a); net.add_node(b)
    a.mark_dead()
    alive = net.alive_nodes()
    assert all(n.node_id != a.node_id for n in alive)
    assert b.node_id in [n.node_id for n in alive]


# ── curiosity ──────────────────────────────────────────────
def test_jepa_loss_decreases():
    wm = LightweightJEPA(embed_dim=32, hidden=64, lr=1e-2)
    emb = HashEmbedder(dim=32)
    losses = []
    for _ in range(50):
        s = emb.embed("state-a")
        a = emb.embed("action-up")
        s2 = emb.embed("state-b")
        losses.append(wm.update(s, a, s2))
    # 训练后期 loss 不应比前期高
    assert sum(losses[-10:]) < sum(losses[:10])


def test_curiosity_novelty_high_on_new():
    cfg = CuriosityConfig()
    emb = HashEmbedder(dim=32)
    wm = LightweightJEPA(embed_dim=32)
    eng = CuriosityEngine(wm, emb, cfg)
    eng._memory.append(emb.embed("known thing"))
    assert eng.novelty(emb.embed("known thing")) < 0.2
    assert eng.novelty(emb.embed("completely new mars landscape")) > 0.5


def test_gridworld_coverage():
    env = GridWorld(size=3)
    env.reset()
    for _ in range(50):
        env.step("up")
        env.step("right")
    assert env.coverage() > 0.5
