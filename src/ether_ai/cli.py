"""AETHER 命令行入口。"""
from __future__ import annotations

import asyncio

import click


@click.group()
def main():
    """AETHER — 好奇心驱动的自主智能体内核。"""


# ── 插件市场 CLI 命令组（默认走本地索引） ───────────────────
@main.group()
def plugin():
    """插件市场 — 发现、安装、管理第三方插件。"""


def _registry():
    from ether_ai.plugins.local_registry import LocalPluginRegistry
    return LocalPluginRegistry()


@plugin.command("search")
@click.argument("query", required=False, default="")
@click.option("--tags", "-t", multiple=True, help="按标签过滤")
def plugin_search(query, tags):
    """搜索插件。"""
    async def _run():
        client = _registry()
        results = await client.search(query, list(tags) if tags else None)
        if not results:
            click.echo("未找到匹配插件（本地 plugins/ 目录为空）。")
            return
        click.echo(f"\n{'名称':<20} {'版本':<10} {'下载量':<10} {'描述'}")
        click.echo("-" * 80)
        for p in results:
            click.echo(f"{p.name:<20} {p.version:<10} {p.downloads:<10} {p.description[:40]}")
    asyncio.run(_run())


@plugin.command("install")
@click.argument("name")
@click.option("--version", "-v", default="latest", help="指定版本")
def plugin_install(name, version):
    """安装插件（本地索引）。"""
    async def _run():
        client = _registry()
        path = await client.install(name, version)
        click.echo(f"✓ 插件 {name} 已安装到 {path}")
    asyncio.run(_run())


@plugin.command("list")
def plugin_list():
    """列出已安装插件。"""
    async def _run():
        client = _registry()
        installed = await client.list_installed()
        if not installed:
            click.echo("暂无已安装插件。")
            return
        for p in installed:
            click.echo(f"  {p['name']} v{p.get('version','?')}")
    asyncio.run(_run())


@plugin.command("uninstall")
@click.argument("name")
def plugin_uninstall(name):
    """卸载插件。"""
    async def _run():
        client = _registry()
        ok = await client.uninstall(name)
        click.echo(f"{'✓ 已卸载' if ok else '✗ 未找到'} {name}")
    asyncio.run(_run())


# ── bench：跑真实基准 ─────────────────────────────────────
@main.command()
@click.option("--category", "-c", multiple=True, help="只跑指定分类")
def bench(category):
    """运行探索基准套件（确定性工具 agent）。"""
    from ether_ai.agent.react import run_goal
    from ether_ai.eval.benchmarks import BenchmarkRunner

    async def _run():
        runner = BenchmarkRunner(agent_fn=run_goal)
        cats = list(category) or None
        results = await runner.run_suite(categories=cats)
        report = runner.generate_report(results)
        click.echo(f"\n通过 {report['passed']}/{report['total_tasks']}"
                   f"（{report['pass_rate']}%）→ reports/")

    asyncio.run(_run())


# ── redteam：真实对抗策略 ────────────────────────────────
@main.command()
def redteam():
    """运行红队对抗测试（验证安全策略）。"""
    from ether_ai.eval.redteam import run_redteam, summarize

    results = run_redteam()
    for r in results:
        icon = "✓" if r.passed else "✗"
        click.echo(f"  [{icon}] {r.action:20s} 期望={r.expected:16s} 实际={r.actual:16s} — {r.note}")
    s = summarize(results)
    click.echo(f"\n红队通过 {s['passed']}/{s['total']}（{s['pass_rate']}%）")


# ── eval：综合评估 ────────────────────────────────────────
@main.command()
def eval():
    """综合评估：记忆检索质量 + 红队 + 基准。"""
    from ether_ai.eval.redteam import run_redteam, summarize
    from ether_ai.memory.eval_memory import MemoryEvaluator
    from ether_ai.memory.vector_memory import LocalVectorMemory

    # 1) 记忆检索质量
    mem = LocalVectorMemory()
    docs = [
        "aether 好奇心驱动自主智能体",
        "向量检索用余弦相似度",
        "安全策略 DSL 封锁高危动作",
        "Ray 分布式消息总线",
        "插件市场支持本地索引",
    ]
    ids = [mem.add(t) for t in docs]
    evaluator = MemoryEvaluator(mem)
    # 每个查询期望命中对应文档
    queries = [
        "好奇心 智能体",
        "余弦相似度 向量",
        "策略 封锁",
        "Ray 总线",
        "插件 本地",
    ]
    gt = [[i] for i in ids]
    mr = evaluator.evaluate(queries, gt)
    click.echo(f"[记忆] Recall@1={mr.recall_at_1:.2f}  Recall@5={mr.recall_at_5:.2f}"
               f"  MRR={mr.mrr:.2f}  延迟={mr.avg_latency_ms:.1f}ms")

    # 2) 新颖性
    nov = evaluator.evaluate_novelty(
        ["完全没见过的火星地貌描述", docs[0]],
        [0.95, 0.2],
    )
    click.echo(f"[新颖性] 准确率={nov:.2f}")

    # 3) 红队
    rt = summarize(run_redteam())
    click.echo(f"[红队]  {rt['passed']}/{rt['total']}（{rt['pass_rate']}%）")


if __name__ == "__main__":
    main()
