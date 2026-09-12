# 好奇心引擎调参指南

## 公式

| 参数 | 含义 | 默认值 | 取值范围 |
|------|------|--------|----------|
| w₁ | 新颖性权重 | 0.4 | 0.0–1.0 |
| w₂ | 预测误差权重 | 0.3 | 0.0–1.0 |
| w₃ | 信息增益权重 | 0.3 | 0.0–1.0 |
| β  | 内在奖励缩放 | 0.5 | 0.0–1.0 |

约束：w₁ + w₂ + w₃ = 1.0

## 按任务类型的推荐配置

### 探索型任务（如 Explore-10）

目标：最大化环境覆盖与发现新信息。

```yaml
curiosity:
  w1_novelty: 0.5
  w2_prediction_error: 0.2
  w3_info_gain: 0.3
  beta: 0.7
```

### 推理型任务

```yaml
curiosity:
  w1_novelty: 0.2
  w2_prediction_error: 0.3
  w3_info_gain: 0.5
  beta: 0.2
```

### 规划型任务

```yaml
curiosity:
  w1_novelty: 0.1
  w2_prediction_error: 0.1
  w3_info_gain: 0.8
  beta: 0.1
  max_bonus: 0.1          # 内在奖励上限，防止好奇驱动越界
```

### 协作型任务（多智能体）

```yaml
curiosity:
  w1_novelty: 0.3
  w2_prediction_error: 0.4
  w3_info_gain: 0.3
  beta: 0.5
  social_bonus: 0.15      # 协作行为额外奖励
```
