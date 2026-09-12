#!/usr/bin/env python3
"""EtherNet 大规模压测 — 验证多智能体总线在分布式环境下的性能。"""
from __future__ import annotations

import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    import ray

    HAS_RAY = True
except ImportError:
    HAS_RAY = False


async def run_stress_test(
    num_agents: int = 50,
    messages_per_agent: int = 100,
    use_ray: bool = False,
):
    """运行压测。

    Args:
        num_agents: 智能体数量
        messages_per_agent: 每个智能体发送的消息数
        use_ray: 是否使用 Ray 分布式模式
    """
    print(f"\n{'='*60}")
    print(f"EtherNet 压测: {num_agents} 智能体 × {messages_per_agent} 消息")
    print(f"模式: {'Ray 分布式' if use_ray and HAS_RAY else '本地单机'}")
    print(f"{'='*60}")

    from ether_ai.ethernet.ray_bus import create_bus, MessageType

    t0 = time.time()
    bus = create_bus(distributed=use_ray)

    # 注册所有智能体
    agent_ids = [f"agent-{i:04d}" for i in range(num_agents)]
    if use_ray and HAS_RAY:
        for aid in agent_ids:
            ray.get(bus.register.remote(aid))
    else:
        for aid in agent_ids:
            bus.register(aid)
    print(f"  ✓ {num_agents} 个智能体注册完成 ({time.time()-t0:.2f}s)")

    # 并发发送消息
    t1 = time.time()
    total_sent = 0
    for i, aid in enumerate(agent_ids):
        for j in range(messages_per_agent):
            target = agent_ids[(i + j + 1) % num_agents]
            msg = {
                "msg_type": MessageType.P2P.value,
                "sender": aid,
                "receiver": target,
                "payload": {"seq": j, "data": f"payload-{i}-{j}"},
            }
            if use_ray and HAS_RAY:
                ray.get(bus.send.remote(msg))
            else:
                bus.send(msg)
            total_sent += 1
    send_time = time.time() - t1
    print(f"  ✓ 发送 {total_sent} 条消息耗时 {send_time:.2f}s "
          f"({total_sent/send_time:.0f} msg/s)")

    # 并发接收消息
    t2 = time.time()
    total_received = 0
    for aid in agent_ids:
        if use_ray and HAS_RAY:
            msgs = ray.get(bus.receive.remote(aid, max_count=messages_per_agent * 2))
        else:
            msgs = bus.receive(aid, max_count=messages_per_agent * 2)
        total_received += len(msgs)
    recv_time = time.time() - t2
    print(f"  ✓ 接收 {total_received} 条消息耗时 {recv_time:.2f}s "
          f"({total_received/max(recv_time,0.001):.0f} msg/s)")

    # 获取统计
    if use_ray and HAS_RAY:
        stats = ray.get(bus.get_stats.remote())
    else:
        stats = bus.get_stats()
    print(f"  ✓ 总线统计: {stats}")

    total_time = time.time() - t0
    print(f"\n  总耗时: {total_time:.2f}s")
    print(f"  吞吐量: {total_sent/max(total_time,0.001):.0f} msg/s")
    print(f"  消息投递率: {total_received}/{total_sent} "
          f"({100*total_received/max(total_sent,1):.1f}%)")

    return {
        "agents": num_agents,
        "messages_sent": total_sent,
        "messages_received": total_received,
        "total_time": total_time,
        "throughput": total_sent / max(total_time, 0.001),
        "mode": "ray" if (use_ray and HAS_RAY) else "local",
    }


async def main():
    results = []
    # 阶梯式压测
    for n_agents, n_msgs in [(10, 50), (50, 100), (100, 200)]:
        r = await run_stress_test(n_agents, n_msgs, use_ray=HAS_RAY)
        results.append(r)

    print(f"\n{'='*60}")
    print("压测汇总")
    print(f"{'='*60}")
    print(f"{'智能体数':>8} {'消息数':>8} {'耗时(s)':>10} {'吞吐(msg/s)':>14}")
    for r in results:
        print(f"{r['agents']:>8} {r['messages_sent']:>8} "
              f"{r['total_time']:>10.2f} {r['throughput']:>14.0f}")


if __name__ == "__main__":
    asyncio.run(main())
