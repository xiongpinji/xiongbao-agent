# SPDX-License-Identifier: MIT
"""Minimal Nunjucks-compatible renderer for WorkBuddy official ``.tpl`` files.

Supports a practical subset used by vendor templates:
- ``{{ var }}`` / ``{{ nested.path }}``
- ``{% if cond %}`` / ``{% else %}`` / ``{% endif %}`` (inline or multiline)
- Truthiness: missing/empty/False/None → false
- Equality: ``Var == 'x'`` / ``Var != 'x'``

Does **not** implement filters, loops, or macros.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"(\{\{.*?\}\}|\{%.*?%\})", re.DOTALL)


def default_templates_root(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[4]
    return root / "vendor" / "workbuddy-experts" / "templates"


def _lookup(ctx: dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.strip().split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (str, bytes, list, tuple, dict, set)):
        return len(value) > 0
    return bool(value)


def _eval_cond(expr: str, ctx: dict[str, Any]) -> bool:
    expr = expr.strip()
    for op in ("==", "!="):
        if op in expr:
            left, right = expr.split(op, 1)
            left_v = _lookup(ctx, left.strip())
            right_s = right.strip().strip("'\"")
            if op == "==":
                return str(left_v if left_v is not None else "") == right_s
            return str(left_v if left_v is not None else "") != right_s
    return _truthy(_lookup(ctx, expr))


def _subst_vars(text: str, ctx: dict[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(0)[2:-2].strip()
        val = _lookup(ctx, inner)
        if val is None:
            return ""
        return str(val)

    return re.sub(r"\{\{.*?\}\}", repl, text, flags=re.DOTALL)


def render(template: str, context: dict[str, Any] | None = None) -> str:
    ctx = dict(context or {})
    parts = _TOKEN_RE.split(template)
    out: list[str] = []
    # stack: (emitting_bool, seen_else)
    stack: list[tuple[bool, bool]] = []

    def emitting() -> bool:
        return all(item[0] for item in stack)

    for part in parts:
        if not part:
            continue
        if part.startswith("{%") and part.endswith("%}"):
            inner = part[2:-2].strip()
            if inner.startswith("if "):
                parent_ok = emitting()
                cond = _eval_cond(inner[3:], ctx) if parent_ok else False
                stack.append((parent_ok and cond, False))
                continue
            if inner == "else":
                if not stack:
                    raise ValueError("orphan {% else %}")
                emitting_now, seen_else = stack[-1]
                if seen_else:
                    raise ValueError("duplicate {% else %}")
                parent_ok = all(item[0] for item in stack[:-1])
                stack[-1] = (parent_ok and not emitting_now, True)
                continue
            if inner == "endif":
                if not stack:
                    raise ValueError("orphan {% endif %}")
                stack.pop()
                continue
            # unknown tag — ignore when emitting
            continue
        if part.startswith("{{") and part.endswith("}}"):
            if emitting():
                out.append(_subst_vars(part, ctx))
            continue
        if emitting():
            out.append(part)

    if stack:
        raise ValueError("unclosed {% if %}")
    return "".join(out)


def render_file(path: Path | str, context: dict[str, Any] | None = None) -> str:
    return render(Path(path).read_text(encoding="utf-8"), context)


def list_official_templates(root: Path | None = None) -> list[Path]:
    base = root or default_templates_root()
    if not base.is_dir():
        return []
    return sorted(base.glob("*.tpl"))
