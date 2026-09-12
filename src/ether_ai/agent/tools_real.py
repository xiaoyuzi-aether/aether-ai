"""真实外部工具集 — 文件/HTTP/代码执行。

这些工具替换 kernel.py 里的玩具工具，让 AgentKernel 能与真实环境交互。
高危工具（write_file/web_fetch/python_exec）会被 PolicyDSL 标记为需审批。
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import httpx

from ether_ai.agent.kernel import BaseTool


class FileReadTool(BaseTool):
    name = "file_read"
    description = "读取本地文件。参数: path"

    def run(self, path: str = "", **kwargs) -> str:
        try:
            text = Path(path).read_text(encoding="utf-8")
            preview = text[:500]
            return f"读取 {path}（{len(text)} 字符）:\n{preview}"
        except Exception as e:
            return f"错误: 无法读取 {path}: {e}"


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "写入本地文件。参数: path, content"

    def run(self, path: str = "", content: str = "", **kwargs) -> str:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"已写入 {path}（{len(content)} 字符）"
        except Exception as e:
            return f"错误: 无法写入 {path}: {e}"


class FileListTool(BaseTool):
    name = "file_list"
    description = "列出目录。参数: path（默认当前目录）"

    def run(self, path: str = ".", **kwargs) -> str:
        try:
            entries = sorted(os.listdir(path or "."))
            return f"{path or '.'} 下 {len(entries)} 项:\n" + "\n".join(f"  {e}" for e in entries[:30])
        except Exception as e:
            return f"错误: {e}"


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "HTTP GET 抓取网页。参数: url"

    def run(self, url: str = "", **kwargs) -> str:
        if not url.startswith(("http://", "https://")):
            return f"错误: 非法 URL '{url}'"
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                r = client.get(url)
                body = r.text[:500]
                return f"GET {url} → {r.status_code}（{len(r.text)} 字符）:\n{body}"
        except Exception as e:
            return f"错误: 抓取失败: {e}"


class PythonExecTool(BaseTool):
    """沙箱执行 Python 表达式。仅允许字面量和内置函数。"""
    name = "python_exec"
    description = "沙箱执行 Python 表达式。参数: expression（返回值）"

    _ALLOWED_NODES = {
        ast.Expression, ast.Constant,
        ast.List, ast.Dict, ast.Tuple, ast.Set,
        ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not,
        ast.Eq, ast.NotEq, ast.Lt, ast.Gt,
        ast.Call, ast.Name, ast.Load,
    }
    _ALLOWED_FUNCS = {"sum", "range", "min", "max", "len", "abs", "round", "sorted"}

    def run(self, expression: str = "", **kwargs) -> str:
        import builtins
        try:
            tree = ast.parse(expression, mode="eval")
            for node in ast.walk(tree):
                if type(node) not in self._ALLOWED_NODES:
                    return f"错误: 不允许的语法节点 {type(node).__name__}"
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id not in self._ALLOWED_FUNCS:
                        return f"错误: 不允许调用 {node.func.id}"
            sandbox_globals = {
                name: getattr(builtins, name) for name in self._ALLOWED_FUNCS
            }
            result = eval(compile(tree, "<sandbox>", "eval"), sandbox_globals, {})
            return f"结果: {result!r}"
        except Exception as e:
            return f"错误: 执行失败: {e}"


REAL_TOOLS: dict[str, BaseTool] = {
    "file_read": FileReadTool(),
    "file_write": FileWriteTool(),
    "file_list": FileListTool(),
    "web_fetch": WebFetchTool(),
    "python_exec": PythonExecTool(),
}
