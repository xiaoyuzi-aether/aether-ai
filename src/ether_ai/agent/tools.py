"""最小 agent 工具集 — 供 ToolAgent 执行文件/计算类任务。"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def list_dir(pattern: str = "*", cwd: str = ".") -> dict:
    """列出目录下匹配 pattern 的文件。"""
    p = Path(cwd)
    if not p.exists():
        return {"files": [], "count": 0}
    files = [f.name for f in p.glob(pattern) if f.is_file()]
    return {"files": sorted(files), "count": len(files)}


def read_file(path: str, max_lines: int = 0) -> dict:
    """读取文件内容。max_lines>0 时只取前 N 行。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": str(e), "content": ""}
    if max_lines > 0:
        text = "\n".join(text.splitlines()[:max_lines])
    return {"ok": True, "content": text, "lines": len(text.splitlines())}


def write_file(path: str, content: str) -> dict:
    """写入文件。"""
    try:
        Path(path).write_text(content, encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def calc(expression: str) -> dict:
    """安全计算算术表达式。"""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return {"ok": False, "error": "非法字符"}
    try:
        val = eval(expression, {"__builtins__": {}}, {})
        return {"ok": True, "result": val}
    except Exception as e:
        return {"ok": False, "error": str(e)}


TOOLS: dict[str, Any] = {
    "list_dir": list_dir,
    "read_file": read_file,
    "write_file": write_file,
    "calc": calc,
}
