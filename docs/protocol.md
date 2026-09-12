# AETHER 生态协议

本文档定义 AETHER 各组件之间的接口约定。任何想接入内核的插件或外部服务，都应遵循以下协议。

## 1. 智能体内核接口

`AgentKernel.run(task: str) -> dict` 的返回结构：

```json
{
  "task": "原任务",
  "done": true,
  "steps_used": 3,
  "max_steps": 10,
  "total_time": 0.042,
  "history": [
    {
      "step": 1,
      "thought": "规划思路",
      "action": "tool_name",
      "observation": "工具返回",
      "reflection": "success"
    }
  ]
}
```

## 2. 工具协议

任何工具必须实现：

```python
class BaseTool:
    name: str
    description: str
    def run(self, **kwargs) -> str: ...
```

高危工具必须在 `configs/policies.yaml` 注册规则：
- `block`：永久封锁
- `require_approval`：人类在环
- `allow`：直接放行

## 3. 消息协议（EtherNet）

```
Message {
  msg_id: str (12 hex)
  msg_type: HELLO | HEARTBEAT | CFP | BID | AWARD | RESULT | GOSSIP | P2P | VOTE
  sender: node_id
  receiver: node_id | "" (广播)
  payload: dict
  ttl: int (gossip 用)
}
```

合约网拍卖流程：
1. Coordinator 广播 `CFP`
2. 节点基于负载自动 `BID`
3. Coordinator 选 `price × eta` 最小者 `AWARD`
4. Worker 完成后回 `RESULT`

## 4. 拜占庭容错

多数投票阈值默认 0.67。提交 `(node_id, value)` 列表：
- 最大桶占比 ≥ 阈值 → 接受该值
- 其余节点标记为 faulty，累计 3 次以上不可信

## 5. 插件协议

插件目录结构：
```
plugins/<name>/
  plugin.json          # PluginInfo 元数据
  <name>-<version>.aether-plugin
```

`plugin.json` 必填字段：`name`, `version`, `description`。
安装时校验 SHA256（远程索引模式）。

## 6. 好奇心奖励公式

```
r_int = w₁·N(v) + w₂·PE(v) + w₃·IG(v)
total = task_reward + β · r_int
```

约束 `w₁ + w₂ + w₃ = 1.0`（全零为合法消融配置）。
推荐配置见 `docs/curiosity_tuning.md`。

## 7. 版本兼容

| AETHER 版本 | 协议版本 |
|-------------|----------|
| 0.3.0       | v1（本文档） |
