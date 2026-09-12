"""
world_model.py
世界模型 + 好奇心深度耦合。
核心思路：世界模型在嵌入空间预测下一状态，预测误差驱动好奇心。
依赖：numpy（必须），torch（可选，用于 RSSM 接口）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import numpy as np


# ═══════════════════════════════════════════════════════════════════
# 1. 配置
# ═══════════════════════════════════════════════════════════════════
@dataclass
class CuriosityConfig:
    """好奇心引擎配置。对应 AETHER 的 r_int 公式。"""
    w_novelty: float = 0.4          # w₁: 新颖性权重
    w_prediction_error: float = 0.3 # w₂: 预测误差权重
    w_info_gain: float = 0.3        # w₃: 信息增益权重
    beta: float = 0.5               # 内在奖励缩放
    max_bonus: float = 1.0          # 内在奖励上限
    embedding_dim: int = 64         # 嵌入空间维度

    def validate(self):
        s = self.w_novelty + self.w_prediction_error + self.w_info_gain
        # 全零是合法的消融配置（β=0 时好奇心完全关闭）
        if s == 0.0:
            return
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"w1+w2+w3 必须等于 1.0，当前 {s}")


# ═══════════════════════════════════════════════════════════════════
# 2. 轻量嵌入器（无外部模型依赖）
# ═══════════════════════════════════════════════════════════════════
class HashEmbedder:
    """基于哈希的确定性嵌入器。零依赖，用于离线测试和教学。
    生产环境可替换为 sentence-transformers 或 JEPA encoder。
    """

    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, obs: Any) -> np.ndarray:
        """将任意观测映射为 L2 归一化的 dim 维向量。"""
        s = self._to_string(obs)
        rng = np.random.RandomState(hash(s) % (2**31))
        v = rng.randn(self.dim).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-8)

    def embed_batch(self, obs_list: list[Any]) -> np.ndarray:
        return np.stack([self.embed(o) for o in obs_list])

    @staticmethod
    def _to_string(obs: Any) -> str:
        if isinstance(obs, np.ndarray):
            return f"arr{obs.shape}{obs.tobytes()[:64].hex()}"
        return str(obs)[:256]


# ═══════════════════════════════════════════════════════════════════
# 3. 轻量世界模型（JEPA 风格：嵌入空间预测）
# ═══════════════════════════════════════════════════════════════════
class LightweightJEPA:
    """JEPA 风格世界模型：在嵌入空间预测下一状态的嵌入。
    核心：predictor(embed(s), embed(a)) ≈ embed(s')
    用在线梯度下降训练，无需 PyTorch。
    对应前沿：LeCun 的 JEPA 架构通过预测自身对输入的表示来学习世界结构。
    这里用轻量 MLP + numpy 实现最小版本，便于直接运行。
    """

    def __init__(self, embed_dim: int = 64, action_dim: int = 64, hidden: int = 128,
                 lr: float = 1e-3):
        # 注意：CuriosityEngine 用同一个 HashEmbedder 把 action 也 embed 成
        # embed_dim 维，因此 action_dim 必须与 embed_dim 一致，否则 matmul 维度不匹配。
        action_dim = embed_dim
        self.embed_dim = embed_dim
        self.action_dim = action_dim
        self.hidden = hidden
        self.lr = lr
        # 2 层 MLP： [e(s), e(a)] → hidden → e(s')
        in_dim = embed_dim + action_dim
        self.W1 = np.random.randn(in_dim, hidden).astype(np.float32) * 0.1
        self.b1 = np.zeros(hidden, dtype=np.float32)
        self.W2 = np.random.randn(hidden, embed_dim).astype(np.float32) * 0.1
        self.b2 = np.zeros(embed_dim, dtype=np.float32)
        self._loss_history: list[float] = []
        self._step = 0

    # ── 前向 ─────────────────────────────────────────────────────
    def predict(self, state_emb: np.ndarray, action_emb: np.ndarray) -> np.ndarray:
        x = np.concatenate([state_emb, action_emb])
        h = np.maximum(0, x @ self.W1 + self.b1)   # ReLU
        out = h @ self.W2 + self.b2
        return out

    def prediction_error(self, state_emb: np.ndarray, action_emb: np.ndarray,
                         next_emb: np.ndarray) -> float:
        pred = self.predict(state_emb, action_emb)
        return float(np.linalg.norm(pred - next_emb))

    # ── 训练 ─────────────────────────────────────────────────────
    def update(self, state_emb: np.ndarray, action_emb: np.ndarray,
               next_emb: np.ndarray) -> float:
        """一步在线梯度下降。返回当前损失。"""
        x = np.concatenate([state_emb, action_emb])
        # 前向
        z1 = x @ self.W1 + self.b1
        h = np.maximum(0, z1)
        pred = h @ self.W2 + self.b2
        # 损失 = MSE
        diff = pred - next_emb
        loss = float(np.mean(diff ** 2))
        self._loss_history.append(loss)
        self._step += 1
        # 反向
        d_pred = 2.0 * diff / self.embed_dim
        dW2 = np.outer(h, d_pred)
        db2 = d_pred
        d_h = d_pred @ self.W2.T
        d_z1 = d_h * (z1 > 0).astype(np.float32)
        dW1 = np.outer(x, d_z1)
        db1 = d_z1
        # 更新
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1
        return loss

    def train_step(self, transitions: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
                   epochs: int = 1) -> float:
        """批量训练。transitions: [(s_emb, a_emb, s'_emb), ...]"""
        total = 0.0
        for _ in range(epochs):
            for s, a, s_next in transitions:
                total += self.update(s, a, s_next)
        return total / max(len(transitions) * epochs, 1)

    def stats(self) -> dict:
        recent = self._loss_history[-100:]
        return {
            "steps": self._step,
            "avg_loss_100": round(float(np.mean(recent)), 6) if recent else 0.0,
            "min_loss": round(float(np.min(self._loss_history)), 6) if self._loss_history else 0.0,
        }


# ═══════════════════════════════════════════════════════════════════
# 4. 好奇心引擎（与 JEPA 深度耦合）
# ═══════════════════════════════════════════════════════════════════
class CuriosityEngine:
    """好奇心引擎。
    r_int = w₁·N(v) + w₂·PE(v) + w₃·IG(v)
    其中：
      - N(v): 新颖性 = 1 - 与最近记忆中最大余弦相似度
      - PE(v): 预测误差 = 世界模型预测嵌入与真实嵌入的 L2 距离
      - IG(v): 信息增益 = 预测误差的变化率（学习进度）
    关键耦合：PE 直接来自 JEPA 世界模型的输出，而非外部注入。
    """

    def __init__(self, world_model: LightweightJEPA, embedder: HashEmbedder,
                 config: CuriosityConfig | None = None):
        self.wm = world_model
        self.embedder = embedder
        self.cfg = config or CuriosityConfig()
        self.cfg.validate()
        self._memory: list[np.ndarray] = []        # 嵌入记忆
        self._memory_max = 500
        self._pe_history: list[float] = []          # 预测误差历史，用于信息增益
        self._ig_window = 20

    # ── 三个分量的计算 ──────────────────────────────────────────
    def novelty(self, emb: np.ndarray) -> float:
        """新颖性：与记忆中最相似嵌入的 1 - 余弦相似度。"""
        if not self._memory:
            return 1.0
        mem = np.stack(self._memory)
        sims = mem @ emb   # 已归一化，点积即余弦
        return float(1.0 - np.max(sims))

    def prediction_error(self, state_emb: np.ndarray, action_emb: np.ndarray,
                         next_emb: np.ndarray) -> float:
        """预测误差：直接调用 JEPA 世界模型。"""
        return self.wm.prediction_error(state_emb, action_emb, next_emb)

    def information_gain(self, current_pe: float) -> float:
        """信息增益：预测误差的下降速度。PE 下降越快，IG 越高。"""
        self._pe_history.append(current_pe)
        if len(self._pe_history) < 2:
            return 0.0
        window = self._pe_history[-self._ig_window:]
        if len(window) < 2:
            return 0.0
        # 线性趋势的负斜率 = 学习进度
        x = np.arange(len(window), dtype=np.float32)
        y = np.array(window, dtype=np.float32)
        slope = float(np.polyfit(x, y, 1)[0])
        # 归一化到 [0, 1]：下降越快越接近 1
        return float(np.clip(-slope / (abs(y[0]) + 1e-6), 0.0, 1.0))

    # ── 综合内在奖励 ─────────────────────────────────────────────
    def intrinsic_reward(
        self,
        state: Any,
        action: Any,
        next_state: Any,
    ) -> tuple[float, dict[str, float]]:
        """计算内在奖励。返回 (r_int, 分量明细)。
        同时在线更新世界模型（这使好奇心与学习耦合：好奇心驱动模型改进，
        模型改进又改变好奇心的输入）。
        """
        s_emb = self.embedder.embed(state)
        a_emb = self.embedder.embed(action)
        ns_emb = self.embedder.embed(next_state)
        # 分量
        n = self.novelty(ns_emb)
        pe = self.prediction_error(s_emb, a_emb, ns_emb)
        ig = self.information_gain(pe)
        # 在线更新世界模型
        self.wm.update(s_emb, a_emb, ns_emb)
        # 写入记忆
        self._memory.append(ns_emb)
        if len(self._memory) > self._memory_max:
            self._memory.pop(0)
        # 加权
        r_int = (self.cfg.w_novelty * n
                 + self.cfg.w_prediction_error * pe
                 + self.cfg.w_info_gain * ig)
        r_int = min(r_int, self.cfg.max_bonus)
        components = {
            "novelty": round(n, 4),
            "prediction_error": round(pe, 4),
            "info_gain": round(ig, 4),
            "r_int": round(r_int, 4),
        }
        return r_int, components

    def total_reward(self, task_reward: float, r_int: float) -> float:
        return task_reward + self.cfg.beta * r_int

    def reset_episode(self):
        """新 episode 开始时清空短时记忆，保留世界模型权重。"""
        self._memory.clear()
        self._pe_history.clear()


# ═══════════════════════════════════════════════════════════════════
# 5. RSSM 集成接口（可选，torch 依赖）
# ═══════════════════════════════════════════════════════════════════
class RSSMWorldModel:
    """DreamerV3 RSSM 接口占位。
    生产环境用 torch + ray.rllib 的 DreamerV3 实现替换：
        from ray.rllib.algorithms.dreamerv3.torch.models.dreamer_model import DreamerModel
    这里提供一个纯接口定义，使 CuriosityEngine 可以通过
    prediction_error() 方法透明切换后端。
    """

    def __init__(self, embed_dim: int = 64, deter_size: int = 128, stoch_size: int = 32):
        self.embed_dim = embed_dim
        self.deter_size = deter_size
        self.stoch_size = stoch_size
        self._available = False
        try:
            import torch  # noqa: F401
            self._available = True
        except ImportError:
            pass

    def is_available(self) -> bool:
        return self._available

    def prediction_error(self, state_emb: np.ndarray, action_emb: np.ndarray,
                         next_emb: np.ndarray) -> float:
        """如果 torch 可用，这里应调用 RSSM 的 prior/posterior 计算 KL 散度；
        否则回退到 L2 距离。
        """
        return float(np.linalg.norm(next_emb - state_emb))

    def update(self, state_emb: np.ndarray, action_emb: np.ndarray,
               next_emb: np.ndarray) -> float:
        return 0.0


# ═══════════════════════════════════════════════════════════════════
# 6. 简单环境（用于演示）
# ═══════════════════════════════════════════════════════════════════
class GridWorld:
    """5×5 网格世界。智能体从 (0,0) 出发，探索陌生格子获得内在奖励。"""

    def __init__(self, size: int = 5):
        self.size = size
        self.pos = [0, 0]
        self.visited = set()

    def reset(self) -> tuple[int, int]:
        self.pos = [0, 0]
        self.visited = {tuple(self.pos)}
        return tuple(self.pos)

    def step(self, action: str) -> tuple[tuple[int, int], float, bool]:
        x, y = self.pos
        if action == "up":
            y = min(self.size - 1, y + 1)
        elif action == "down":
            y = max(0, y - 1)
        elif action == "left":
            x = max(0, x - 1)
        elif action == "right":
            x = min(self.size - 1, x + 1)
        self.pos = [x, y]
        state = tuple(self.pos)
        # 任务奖励：到达右上角
        task_reward = 1.0 if state == (self.size - 1, self.size - 1) else 0.0
        self.visited.add(state)
        done = task_reward > 0
        return state, task_reward, done

    def coverage(self) -> float:
        return len(self.visited) / (self.size * self.size)


# ═══════════════════════════════════════════════════════════════════
# 7. 演示
# ═══════════════════════════════════════════════════════════════════
def demo():
    print("=" * 64)
    print("世界模型 + 好奇心深度耦合 — 演示")
    print("=" * 64)

    cfg = CuriosityConfig(w_novelty=0.4, w_prediction_error=0.3,
                          w_info_gain=0.3, beta=0.5)
    embedder = HashEmbedder(dim=cfg.embedding_dim)
    world_model = LightweightJEPA(embed_dim=cfg.embedding_dim)
    curiosity = CuriosityEngine(world_model, embedder, cfg)
    env = GridWorld(size=5)
    actions = ["up", "down", "left", "right"]

    print(f"\n[配置] w1={cfg.w_novelty} w2={cfg.w_prediction_error} "
          f"w3={cfg.w_info_gain} β={cfg.beta}")

    # 训练循环
    for episode in range(5):
        state = env.reset()
        curiosity.reset_episode()
        total_r = 0.0
        steps = 0
        for step in range(30):
            action = random.choice(actions)
            next_state, task_r, done = env.step(action)
            r_int, components = curiosity.intrinsic_reward(state, action, next_state)
            r_total = curiosity.total_reward(task_r, r_int)
            total_r += r_total
            steps += 1
            if done:
                break
            state = next_state
        wm_stats = world_model.stats()
        print(f"  ep{episode}  steps={steps:2d}  R={total_r:6.2f}  "
              f"coverage={env.coverage():.0%}  "
              f"wm_loss={wm_stats['avg_loss_100']:.6f}")

    # 好奇心分量追踪
    print("\n[好奇心分量追踪 — 最后 5 步]")
    state = (0, 0)
    for i in range(5):
        action = random.choice(actions)
        ns, _, _ = env.step(action)
        _, comp = curiosity.intrinsic_reward(state, action, ns)
        print(f"  step{i}: novelty={comp['novelty']:.3f} "
              f"pe={comp['prediction_error']:.3f} "
              f"ig={comp['info_gain']:.3f} → r_int={comp['r_int']:.3f}")
        state = ns

    print(f"\n[世界模型统计] {world_model.stats()}")
    print(f"  最终覆盖率: {env.coverage():.0%}")

    # 对比：关闭好奇心
    print("\n[消融] 关闭好奇心（β=0）...")
    cfg_no = CuriosityConfig(w_novelty=0.0, w_prediction_error=0.0,
                             w_info_gain=0.0, beta=0.0)
    wm2 = LightweightJEPA(embed_dim=cfg.embedding_dim)
    cur2 = CuriosityEngine(wm2, embedder, cfg_no)
    env2 = GridWorld(size=5)
    for ep in range(5):
        env2.reset()
        cur2.reset_episode()
        for step in range(30):
            action = random.choice(actions)
            ns, tr, done = env2.step(action)
            cur2.intrinsic_reward((0, 0), action, ns)
            if done:
                break
    print(f"  β=0 覆盖率: {env2.coverage():.0%}  vs  "
          f"β={cfg.beta} 覆盖率: {env.coverage():.0%}")

    print("\n" + "=" * 64)
    print("演示完成。核心: LightweightJEPA → prediction_error → CuriosityEngine")
    print("=" * 64)


if __name__ == "__main__":
    demo()
