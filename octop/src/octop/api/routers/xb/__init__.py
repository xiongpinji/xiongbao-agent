# SPDX-License-Identifier: MIT
# 熊宝 Agent (XiongBao Agent) — WorkBuddy 改造路由适配层
#
# 在不改 octop.contrib.workbuddy 源码的前提下，把 console_server.py 的
# 分发逻辑（api_payload / api_post / api_get_task_path /
# api_get_project_path / api_get_extra / api_post_extra）整段挂到 FastAPI。
#
# 账号体系：复用 octop 原生 JWT（octop.api.deps.current_user）。
# 租户隔离：每个 octop user 对应一个 TenantContext（tenant_id=user_id,
#            role=user.role），存储根切到 ~/.octop/users/<uid>/xb/。
"""Xiongbao (熊宝 Agent) WorkBuddy-parity API adapter."""

from __future__ import annotations

import importlib
import logging
import sys
import types
from pathlib import Path

# The contrib/ tree lives at <repo>/octop/contrib/, NOT inside the installed
# ``octop`` package (the octop wheel only ships src/octop). Register a shim
# top-level package ``octop_contrib`` whose __path__ points at the contrib/
# tree, so we can ``import octop_contrib.workbuddy ...`` without colliding
# with the installed ``octop`` package on sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[5]
assert (_REPO_ROOT / "contrib" / "workbuddy" / "__init__.py").is_file(), (
    f"Could not locate repo root from {Path(__file__)!s}"
)
if "octop_contrib" not in sys.modules:
    _shim = types.ModuleType("octop_contrib")
    _shim.__path__ = [str(_REPO_ROOT / "contrib")]
    sys.modules["octop_contrib"] = _shim
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request

from octop.api.deps import current_user
import octop_contrib.workbuddy  # noqa: F401  (registers subpackages on sys.modules)
from octop_contrib.workbuddy.console_parity_api import (
    api_get_extra,
    api_post_extra,
)
from octop_contrib.workbuddy.console_server import (
    api_get_project_path,
    api_get_task_path,
    api_payload,
    api_post,
)
from octop_contrib.workbuddy.tenant import TenantContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _XbRoots:
    """Per-user Xiongbao (熊宝 Agent) filesystem layout under ~/.octop."""

    root: Path
    tasks: Path
    projects: Path
    skills: Path
    knowledge: Path
    cowrite: Path
    library: Path
    models: Path
    shared: Path
    goal_craft: Path
    worktrees: Path

    @classmethod
    def for_user(cls, user_id: str, *, base: Path | None = None) -> "_XbRoots":
        base = base or Path(os.environ.get("OCTOP_HOME") or Path.home() / ".octop")
        users_root = base / "users"
        root = users_root / user_id / "xb"
        paths = {
            "root": root,
            "tasks": root / "tasks",
            "projects": root / "projects",
            "skills": root / "skills",
            "knowledge": root / "knowledge",
            "cowrite": root / "cowrite",
            "library": root / "library",
            "models": root / "models",
            "shared": root / "shared",
            "goal_craft": root / "goal_craft",
            "worktrees": root / "worktrees",
        }
        for p in paths.values():
            p.mkdir(parents=True, exist_ok=True)
        return cls(**paths)


# --- 环境替换（让 workbuddy 的代码以 "当前用户" 为视角运行） ---

_OLD_ENV: dict[str, str | None] | None = None
_OLD_CWD: Path | None = None


def _build_ctx(user: Any) -> TenantContext:
    """Map octop user → TenantContext (tenant_id == user_id for isolation)."""
    role = getattr(getattr(user, "role", None), "value", None) or "user"
    return TenantContext(
        tenant_id=str(getattr(user, "id", user.username)),
        user_id=str(user.username),
        role=str(role),
    )


def _patch_workbuddy_runtime(*, roots: _XbRoots, user: Any) -> None:
    """Switch octop.contrib.workbuddy globals to per-user roots.

    Workbuddy module-level helpers read these at call time, so we mutate them
    before each request and restore in the finally block.
    """
    import octop_contrib.workbuddy.console_parity_api as _parity
    import octop_contrib.workbuddy.console_server as _server

    # Tenant-context-shaped object — workbuddy only reads .tenant_id/.user_id/.role
    ctx = _build_ctx(user)
    # Bind a module-level ctx accessor on console_server for its helpers.
    _server._ctx_for_request = ctx  # type: ignore[attr-defined]
    _parity._ctx_for_request = ctx  # type: ignore[attr-defined]
    # Redirect "artifacts/<sub>" roots to per-user location
    global _OLD_ENV, _OLD_CWD
    _OLD_ENV = _OLD_ENV or {}
    _OLD_CWD = Path.cwd()
    # Switch cwd into the user's xb root so relative Path("artifacts/...") calls
    # land in the right place.
    os.chdir(roots.root)
    # workbuddy reads WB_TENANT_REGISTRY / WB_LLM_MODEL for fallback paths
    for k, v in (
        ("WB_TENANT_REGISTRY", str(roots.root / "_registry.json")),
        ("WB_LLM_MODEL", os.environ.get("WB_LLM_MODEL", "")),
        ("WB_CONSOLE_SECRET", os.environ.get("WB_CONSOLE_SECRET", "") or "xb-octop-shared-secret"),
    ):
        _OLD_ENV.setdefault(k, os.environ.get(k))
        if v:
            os.environ[k] = v


def _unpatch_workbuddy_runtime() -> None:
    global _OLD_ENV, _OLD_CWD
    try:
        if _OLD_CWD is not None:
            os.chdir(_OLD_CWD)
    except Exception:
        pass
    if _OLD_ENV:
        for k, prev in _OLD_ENV.items():
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev
        _OLD_ENV = None
    _OLD_CWD = None


# --- Catch-all dispatch: 把 workbuddy 的 (path, ctx, query) 三参分派器包成 FastAPI handler ---

router = APIRouter()


@router.api_route(
    "/xiongbao/v1/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def xb_catch_all(
    full_path: str,
    request: Request,
    user: Any = Depends(current_user),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """熊宝 Agent API 适配入口 —— 把 WorkBuddy 路由搬到 FastAPI。"""
    from starlette.responses import JSONResponse

    roots = _XbRoots.for_user(str(user.username))
    _patch_workbuddy_runtime(roots=roots, user=user)

    # 构造 query 形参（workbuddy 期望 dict[str, list[str]]）
    qp: dict[str, list[str]] = {}
    for k, v in request.query_params.multi_items():
        qp.setdefault(k, []).append(v)

    method = request.method.upper()
    path = "/api/" + full_path  # WorkBuddy API paths start with /api/
    body_obj: dict[str, Any] = {}
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            raw = await request.body()
            if raw:
                import json as _json

                try:
                    body_obj = _json.loads(raw.decode("utf-8"))
                except Exception:
                    body_obj = {}
        except Exception:
            body_obj = {}

    ctx = _build_ctx(user)

    try:
        logger.warning("XB_HIT method=%s path=%s full=%s", method, path, full_path)
        if method == "GET":
            # try task/project subroutes first
            if path.startswith("/api/tasks/"):
                code, payload = api_get_task_path(path, ctx, qp)
            elif path.startswith("/api/projects/"):
                code, payload = api_get_project_path(path, ctx)
            elif path in {
                "/api/health",
                "/api/ops",
                "/api/status",
                "/api/hub",
                "/api/tasks",
                "/api/projects",
                "/api/skills",
                "/api/connectors",
                "/api/channels",
                "/api/harbor",
                "/api/runtime",
                "/api/tenant",
                "/api/enterprise",
            }:
                # api_payload returns dict directly
                payload = api_payload(path, ctx, qp)
                code = 200
            else:
                # extras: models / knowledge / cowrite / library / memory / team / worktree / channels
                code, payload = api_get_extra(path, ctx, qp)
        else:
            # POST/PUT/PATCH/DELETE
            code, payload = api_post(path, qp, body_obj, ctx)
            if code == 404:
                code, payload = api_post_extra(path, ctx, body_obj)

        if isinstance(payload, Mapping):
            return JSONResponse(content=dict(payload), status_code=code)
        return JSONResponse(content={"ok": False, "error": "unexpected payload type"}, status_code=500)
    except Exception as exc:  # noqa: BLE001
        logger.exception("xb_catch_all failed: %s %s", method, path)
        return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=500)
    finally:
        _unpatch_workbuddy_runtime()
