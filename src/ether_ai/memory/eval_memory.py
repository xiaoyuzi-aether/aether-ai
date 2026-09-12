"""记忆系统检索质量评估 — 量化 FAISS/Chroma 的召回率与新颖性计算准确性。"""
from __future__ import annotations

import time
import numpy as np  # noqa: F401  (保留，便于扩展)
from dataclasses import dataclass


@dataclass
class MemoryEvalResult:
    backend: str
    total_queries: int
    recall_at_1: float
    recall_at_5: float
    mrr: float          # Mean Reciprocal Rank
    avg_latency_ms: float
    novelty_accuracy: float


class MemoryEvaluator:
    """记忆系统评估器。

    用法:
        evaluator = MemoryEvaluator(memory_backend)
        result = evaluator.evaluate(queries, ground_truth)
    """

    def __init__(self, memory_backend: any):
        self.memory = memory_backend

    def evaluate(
        self,
        queries: list[str],
        ground_truth: list[list[int]],
        k_values: tuple[int, ...] = (1, 5, 10),
    ) -> MemoryEvalResult:
        """评估检索质量。

        Args:
            queries: 查询文本列表
            ground_truth: 每个查询对应的正确记忆 ID 列表
            k_values: 计算 Recall@K 的 K 值
        """
        recalls = {k: 0 for k in k_values}
        reciprocal_ranks = []
        latencies = []

        for query, gt_ids in zip(queries, ground_truth):
            t0 = time.time()
            results = self.memory.retrieve(query, top_k=max(k_values))
            latency = (time.time() - t0) * 1000
            latencies.append(latency)

            result_ids = [r.get("id") for r in results]

            # Recall@K
            for k in k_values:
                top_k_ids = set(result_ids[:k])
                if top_k_ids & set(gt_ids):
                    recalls[k] += 1

            # MRR
            rr = 0.0
            for rank, rid in enumerate(result_ids, start=1):
                if rid in gt_ids:
                    rr = 1.0 / rank
                    break
            reciprocal_ranks.append(rr)

        n = max(len(queries), 1)
        return MemoryEvalResult(
            backend=getattr(self.memory, "backend_name", "unknown"),
            total_queries=n,
            recall_at_1=recalls.get(1, 0) / n,
            recall_at_5=recalls.get(5, 0) / n,
            mrr=sum(reciprocal_ranks) / n,
            avg_latency_ms=sum(latencies) / n,
            novelty_accuracy=0.0,  # 由子类填充
        )

    def evaluate_novelty(self, observations: list[str], expected_novelty: list[float]) -> float:
        """评估新颖性计算的准确性。

        Args:
            observations: 观测列表
            expected_novelty: 预期的新颖性分数（0-1）
        """
        errors = []
        for obs, expected in zip(observations, expected_novelty):
            actual = self.memory.compute_novelty(obs)
            errors.append(abs(actual - expected))
        return 1.0 - (sum(errors) / max(len(errors), 1))
