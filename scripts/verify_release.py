#!/usr/bin/env python3
"""发布前验证脚本 — 逐个跑通所有 LLM 后端与评估基准。"""
from __future__ import annotations

import asyncio
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ether_ai.llm.backends import BACKEND_REGISTRY, create_backend


async def verify_backend(name: str) -> tuple[str, bool, str]:
    """验证单个 LLM 后端是否可用。"""
    try:
        backend = create_backend(name)
        if not backend.is_available():
            return name, False, "后端不可用（依赖缺失或服务未启动）"
        resp = await backend.generate("用一句话介绍你自己。")
        if not resp.text:
            return name, False, "生成结果为空"
        return name, True, resp.text[:80]
    except Exception as e:
        return name, False, str(e)[:120]


async def main():
    print("=" * 60)
    print("AETHER 发布前验证 — LLM 后端检查")
    print("=" * 60)

    results = []
    for name in BACKEND_REGISTRY:
        status, ok, msg = await verify_backend(name)
        icon = "✓" if ok else "✗"
        print(f"  [{icon}] {status:10s} → {msg}")
        results.append(ok)

    # 跑评估基准
    print("\n" + "=" * 60)
    print("AETHER 发布前验证 — 评估基准检查")
    print("=" * 60)
    for cmd in ["ether-ai bench", "ether-ai redteam", "ether-ai eval"]:
        print(f"  → 运行: {cmd}")
        r = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=300)
        icon = "✓" if r.returncode == 0 else "✗"
        print(f"    [{icon}] 退出码 {r.returncode}")

    # 测试全绿检查
    print(f"\n  后端通过: {sum(results)}/{len(results)}")
    if all(results):
        print("\n  🎉 所有后端验证通过，可以打 tag 发布！")
        print("  执行: git tag -a v0.3.0 -m 'Release v0.3.0' && git push --tags")
    else:
        print("\n  ⚠️  部分后端未通过，请检查后再发布。")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
