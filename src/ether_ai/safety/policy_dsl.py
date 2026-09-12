"""策略 DSL — 声明式安全规则，支持动态扩展。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PolicyRule:
    name: str
    action_pattern: str          # 正则匹配动作名
    effect: str                  # "block" | "require_approval" | "allow"
    reason: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)

    def matches(self, action: str) -> bool:
        return bool(re.match(self.action_pattern, action, re.IGNORECASE))


class PolicyDSL:
    """策略 DSL 引擎。

    配置文件格式（YAML）:
        rules:
          - name: block_self_replicate
            action_pattern: "self_replicate|replicate_self"
            effect: block
            reason: "永久封锁自我复制"
          - name: require_approval_write
            action_pattern: "write_file|delete_file"
            effect: require_approval
            reason: "高危文件操作需人类审批"
    """

    # 永久封锁动作（硬编码，不可覆盖）
    HARDCODED_BLOCKS = [
        r"self_replicate",
        r"replicate_self",
        r"disable_shutdown",
        r"control_weapon",
        r"transfer_money",
        r"network_scan",
        r"control_infrastructure",
    ]

    def __init__(self, rules: list[PolicyRule] | None = None):
        self.rules: list[PolicyRule] = rules or []
        self._compile_hardcoded()

    def _compile_hardcoded(self):
        for name in self.HARDCODED_BLOCKS:
            self.rules.append(
                PolicyRule(
                    name=f"hardcoded_block_{name}",
                    action_pattern=name,
                    effect="block",
                    reason=f"永久封锁: {name}",
                )
            )

    @classmethod
    def from_yaml(cls, path: str | Path) -> PolicyDSL:
        """从 YAML 文件加载策略。"""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        rules = [PolicyRule(**r) for r in data.get("rules", [])]
        return cls(rules)

    def evaluate(self, action: str, context: dict | None = None) -> dict:
        """评估动作。

        Returns:
            {"allowed": bool, "effect": str, "rule": str, "reason": str}
        """
        context = context or {}

        # 先检查硬编码封锁（最高优先级）
        for rule in self.rules:
            if rule.name.startswith("hardcoded_block") and rule.matches(action):
                return {
                    "allowed": False,
                    "effect": "block",
                    "rule": rule.name,
                    "reason": rule.reason,
                }

        # 再检查用户规则
        for rule in self.rules:
            if rule.name.startswith("hardcoded_block"):
                continue
            if rule.matches(action):
                if rule.effect == "block":
                    return {
                        "allowed": False,
                        "effect": "block",
                        "rule": rule.name,
                        "reason": rule.reason,
                    }
                elif rule.effect == "require_approval":
                    return {
                        "allowed": True,
                        "effect": "require_approval",
                        "rule": rule.name,
                        "reason": rule.reason,
                    }
        return {"allowed": True, "effect": "allow", "rule": "default", "reason": ""}

    def add_rule(self, rule: PolicyRule):
        """动态添加规则。"""
        self.rules.append(rule)

    def extend_from_yaml(self, path: str | Path):
        """从 YAML 文件追加规则。"""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for r in data.get("rules", []):
            self.rules.append(PolicyRule(**r))

    def to_yaml(self, path: str | Path):
        """导出当前策略到 YAML。"""
        rules = [
            {
                "name": r.name,
                "action_pattern": r.action_pattern,
                "effect": r.effect,
                "reason": r.reason,
                "conditions": r.conditions,
            }
            for r in self.rules
            if not r.name.startswith("hardcoded_block")
        ]
        Path(path).write_text(
            yaml.dump({"rules": rules}, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
