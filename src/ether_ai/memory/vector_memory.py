"""本地向量记忆后端 — 基于 numpy 哈希嵌入 + 余弦相似度，无外部依赖。

用于在没有 FAISS/Chroma/sentence-transformers 的环境下提供真实可检索、
可计算新颖性的记忆层。嵌入采用字符 n-gram 哈希，确定性、零下载。
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


def _text_to_vector(text: str, dim: int = 256) -> np.ndarray:
    """字符 trigram 哈希到固定维向量，L2 归一化。"""
    vec = np.zeros(dim, dtype=np.float32)
    t = (text or "").lower()
    if len(t) < 3:
        grams = [t] if t else []
    else:
        grams = [t[i:i + 3] for i in range(len(t) - 2)]
    for g in grams:
        h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


@dataclass
class MemoryRecord:
    id: int
    text: str
    vector: np.ndarray
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0


class LocalVectorMemory:
    """真实可检索的本地向量记忆。

    接口对齐 MemoryEvaluator 的预期：
        .retrieve(query, top_k) -> [{"id": int, "text": str, "score": float}]
        .compute_novelty(observation) -> float
    """

    backend_name = "local-numpy-vector"

    def __init__(self, dim: int = 256):
        self.dim = dim
        self._records: list[MemoryRecord] = []
        self._matrix: np.ndarray | None = None

    def add(self, text: str) -> int:
        """写入一条记忆，返回其 id。"""
        rec = MemoryRecord(
            id=len(self._records),
            text=text,
            vector=_text_to_vector(text, self.dim),
        )
        self._records.append(rec)
        self._matrix = np.stack([r.vector for r in self._records])
        return rec.id

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """余弦相似度检索，返回 top_k。"""
        if not self._records or self._matrix is None:
            return []
        q = _text_to_vector(query, self.dim)
        sims = self._matrix @ q  # 向量已归一化，点积即余弦
        order = np.argsort(-sims)[:top_k]
        results = []
        for idx in order:
            self._records[int(idx)].access_count += 1
            results.append({
                "id": int(self._records[int(idx)].id),
                "text": self._records[int(idx)].text,
                "score": float(sims[int(idx)]),
            })
        return results

    def compute_novelty(self, observation: str) -> float:
        """新颖性：0~1。与库中最相似记忆的余弦距离越大越新。

        空库 → 1.0（全新）；高度相似 → 趋近 0。
        """
        if not self._records or self._matrix is None:
            return 1.0
        q = _text_to_vector(observation, self.dim)
        best = float(np.max(self._matrix @ q))
        # 余弦范围 [-1,1]，映射到 [0,1] 新颖度
        return round(1.0 - (best + 1.0) / 2.0, 4)

    def stats(self) -> dict:
        return {
            "backend": self.backend_name,
            "records": len(self._records),
            "dim": self.dim,
        }

    # ── 持久化 ─────────────────────────────────────────────────
    def save(self, path: str | Path) -> Path:
        """把记忆落盘到 .npz（向量）+ .json（文本元数据）。"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._matrix is not None and self._records:
            np.savez(
                path.with_suffix(".npz"),
                matrix=self._matrix,
                dim=np.array(self.dim),
            )
        meta = {
            "records": [
                {"id": r.id, "text": r.text, "timestamp": r.timestamp,
                 "access_count": r.access_count}
                for r in self._records
            ],
        }
        path.with_suffix(".json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> LocalVectorMemory:
        """从 save() 写的文件恢复记忆。"""
        path = Path(path)
        mem = cls()
        meta_path = path.with_suffix(".json")
        npz_path = path.with_suffix(".npz")
        if not meta_path.exists():
            return mem
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if npz_path.exists():
            data = np.load(npz_path)
            matrix = data["matrix"]
            mem.dim = int(data["dim"])
        else:
            matrix = None
        for i, rec in enumerate(meta["records"]):
            vec = matrix[i] if matrix is not None else _text_to_vector(rec["text"], mem.dim)
            mem._records.append(MemoryRecord(
                id=rec["id"], text=rec["text"], vector=vec,
                timestamp=rec["timestamp"], access_count=rec["access_count"],
            ))
        mem._matrix = matrix
        return mem
