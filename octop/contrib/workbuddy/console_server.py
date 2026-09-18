# SPDX-License-Identifier: MIT
"""WorkBuddy Console v17 — multi-tenant auth + product shell APIs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from .connectors import probe_status as connectors_probe
from .console_events import iter_sse_frames
from .console_parity_api import api_get_extra, api_post_extra, normalize_members, require_role, save_project_meta
from .console_workspace import read_preview, resolve_download, save_upload, workspace_payload
from .enterprise.probe import enterprise_probe
from .hub import hub_status
from .project import ProjectSpace
from .skills import SkillCatalog, install_from_vendor, install_skill
from .task import TaskStore
from .tenant import (
    TenantContext,
    TenantRegistry,
    TenantRoots,
    auth_required,
    exchange_casdoor_token,
    issue_token,
    parse_bearer,
    verify_token,
)

_CONSOLE_DIR = Path(__file__).resolve().parent / "console"
_SHELL = _CONSOLE_DIR / "shell.html"
_OPS = _CONSOLE_DIR / "ops.html"
_LEGACY = _CONSOLE_DIR / "index.html"
_STATIC_EXT = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8"}

_PUBLIC_GET = {"/api/health"}
_API_GET_EXACT = {
    "/api/health",
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
    "/api/models",
    "/api/knowledge",
    "/api/cowrite",
    "/api/library",
    "/api/memory",
    "/api/team",
}


def _registry() -> TenantRegistry:
    return TenantRegistry(os.environ.get("WB_TENANT_REGISTRY") or "artifacts/tenants/_registry.json")


def _roots_for(ctx: TenantContext | None) -> TenantRoots | None:
    if ctx is None:
        return None
    roots = TenantRoots(ctx.tenant_id, ctx.user_id)
    roots.ensure()
    return roots


def _tasks_root_for(ctx: TenantContext | None) -> Path:
    roots = _roots_for(ctx)
    if roots is not None:
        return roots.tasks
    return Path("artifacts/tasks")


def _projects_root_for(ctx: TenantContext | None) -> Path:
    roots = _roots_for(ctx)
    if roots is not None:
        return roots.projects
    return Path("artifacts/projects")


def _run_task_kwargs(ctx: TenantContext | None) -> dict[str, Any]:
    roots = _roots_for(ctx)
    kb = roots.knowledge if roots else Path("artifacts/knowledge")
    goals = Path("artifacts/goal_craft")
    if roots is not None:
        goals = roots.root / "goal_craft"
        goals.mkdir(parents=True, exist_ok=True)
    return {
        "tasks_root": _tasks_root_for(ctx),
        "goals_root": goals,
        "kb_root": kb,
        "projects_root": _projects_root_for(ctx),
    }


def _llm_model() -> str:
    return (
        (os.environ.get("WB_LLM_MODEL") or "").strip()
        or (os.environ.get("OPENAI_MODEL") or "").strip()
        or ""
    )


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", ""}


def _task_summary(t: Any) -> dict[str, Any]:
    return {
        "task_id": t.task_id,
        "title": t.title,
        "status": t.status,
        "mode": t.mode,
        "project_id": t.project_id or "",
        "updated_at": t.updated_at,
        "pinned": bool(t.meta.get("pinned")),
        "archived": bool(t.meta.get("archived")),
        "message_count": len(t.messages),
    }


def _task_detail(t: Any) -> dict[str, Any]:
    data = t.to_dict()
    data["pinned"] = bool(t.meta.get("pinned"))
    data["archived"] = bool(t.meta.get("archived"))
    return data


def api_payload(path: str, ctx: TenantContext | None, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    query = query or {}
    if path == "/api/health":
        return {
            "ok": True,
            "auth_required": auth_required(),
            "v": 17,
            "model": _llm_model() or None,
        }
    if path in {"/api/status", "/api/hub"}:
        data = hub_status()
        if ctx is not None:
            data["tenant"] = ctx.to_claims()
            data["tasks"] = {
                "root": str(_tasks_root_for(ctx)),
                "count": sum(
                    1 for p in _tasks_root_for(ctx).iterdir() if (p / "task.json").is_file()
                )
                if _tasks_root_for(ctx).is_dir()
                else 0,
            }
        return data
    if path == "/api/tenant":
        if ctx is None:
            return {"ok": False, "error": "unauthorized"}
        rec = _registry().get(ctx.tenant_id)
        if rec is None:
            return {"ok": False, "error": "tenant not found"}
        return {
            "ok": True,
            "tenant_id": rec.tenant_id,
            "name": rec.name,
            "role": ctx.role,
            "quota": rec.quota.to_dict(),
            "roots": TenantRoots(ctx.tenant_id, ctx.user_id).to_dict(),
        }
    if path == "/api/tasks":
        store = TaskStore(_tasks_root_for(ctx))
        q = (query.get("q") or [""])[0]
        status = (query.get("status") or [""])[0] or None
        project_id = (query.get("project_id") or [""])[0] or None
        include_archived = (query.get("archived") or ["0"])[0] in {"1", "true", "yes"}
        rows = []
        for t in store.list_tasks(status=status, query=q or None, include_archived=include_archived):
            if project_id and (t.project_id or "") != project_id:
                continue
            rows.append(_task_summary(t))
        return {"ok": True, "count": len(rows), "tasks": rows}
    if path == "/api/projects":
        space = ProjectSpace(_projects_root_for(ctx))
        rows = []
        for p in space.list_projects():
            skills = space.list_skills(p.project_id)
            rows.append({**p.to_dict(), "skill_count": len(skills), "skills": skills[:20]})
        return {"ok": True, "count": len(rows), "projects": rows}
    if path == "/api/skills":
        cat = SkillCatalog()
        n = cat.scan()
        items = [
            {
                "id": m.id,
                "name": m.name,
                "description": (m.description_zh or m.description)[:120],
            }
            for m in cat.list()[:80]
        ]
        installed_root = Path("artifacts/skillhub/installed")
        installed = []
        if installed_root.is_dir():
            installed = [p.name for p in installed_root.iterdir() if p.is_dir()]
        return {"ok": True, "total": n, "skills": items, "installed": installed}
    if path == "/api/connectors":
        return {"ok": True, **connectors_probe()}
    if path == "/api/harbor":
        from .bench.harbor import harbor_status, harness_mount_probe

        return {
            "ok": True,
            "status": harbor_status().to_dict(),
            "harness": harness_mount_probe(),
            "hint": "POST /api/harbor/dry-run",
        }
    if path == "/api/enterprise":
        return {"ok": True, "v": 17, **enterprise_probe()}
    if path == "/api/runtime":
        data = hub_status()
        return {
            "ok": True,
            "v": data.get("v"),
            "model": _llm_model() or None,
            "runtime": data.get("runtime"),
            "tasks": data.get("tasks"),
            "hint": "POST /api/runtime/run-task",
        }
    return {"ok": False, "error": "not found"}


def api_get_task_path(path: str, ctx: TenantContext | None, query: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
    """Handle /api/tasks/<id> and /api/tasks/<id>/workspace|preview|download."""
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "tasks":
        return 404, {"ok": False, "error": "not found"}
    task_id = unquote(parts[2])
    store = TaskStore(_tasks_root_for(ctx))
    try:
        rec = store.get(task_id)
    except FileNotFoundError:
        return 404, {"ok": False, "error": "task not found"}
    task_dir = store._dir(task_id)  # noqa: SLF001
    if len(parts) == 3:
        return 200, {"ok": True, "task": _task_detail(rec)}
    if parts[3] == "workspace":
        return 200, workspace_payload(task_dir, rec.to_dict())
    if parts[3] == "preview":
        rel = (query.get("path") or [""])[0]
        if not rel:
            return 400, {"ok": False, "error": "path required"}
        return 200, read_preview(task_dir, rel)
    if parts[3] == "download":
        # JSON metadata only; binary download handled in _Handler
        rel = (query.get("path") or [""])[0]
        if not rel:
            return 400, {"ok": False, "error": "path required"}
        target, err = resolve_download(task_dir, rel)
        if err:
            return 404, {"ok": False, "error": err}
        assert target is not None
        return 200, {
            "ok": True,
            "path": rel,
            "bytes": target.stat().st_size,
            "download_url": f"/api/tasks/{quote(task_id)}/download?path={quote(rel)}&raw=1",
        }
    return 404, {"ok": False, "error": "not found"}


def api_get_project_path(path: str, ctx: TenantContext | None) -> tuple[int, dict[str, Any]]:
    """Handle /api/projects/<id> and /api/projects/<id>/skills."""
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "projects":
        return 404, {"ok": False, "error": "not found"}
    project_id = unquote(parts[2])
    space = ProjectSpace(_projects_root_for(ctx))
    try:
        meta = space.load(project_id)
    except FileNotFoundError:
        return 404, {"ok": False, "error": "project not found"}
    if len(parts) == 3:
        return 200, {
            "ok": True,
            "project": {
                **meta.to_dict(),
                "members": normalize_members(list(meta.members or [])),
                "skill_count": len(space.list_skills(project_id)),
                "skills": space.skill_details(project_id),
                "memory_preview": space.memory_text(project_id, limit=400),
            },
        }
    if parts[3] == "skills":
        return 200, {"ok": True, "project_id": project_id, "skills": space.skill_details(project_id)}
    return 404, {"ok": False, "error": "not found"}


def api_post(path: str, query: dict[str, list[str]], body: dict[str, Any], ctx: TenantContext | None) -> tuple[int, dict[str, Any]]:
    if path == "/api/auth/login":
        tid = str(body.get("tenant_id") or (query.get("tenant_id") or [""])[0]).strip()
        uid = str(body.get("user_id") or (query.get("user_id") or [""])[0]).strip()
        key = str(body.get("api_key") or (query.get("api_key") or [""])[0]).strip()
        casdoor = str(body.get("casdoor_token") or body.get("access_token") or "").strip()
        try:
            if casdoor:
                new_ctx = exchange_casdoor_token(casdoor)
            else:
                new_ctx = _registry().authenticate(tid, uid, key)
            token = issue_token(new_ctx)
            return 200, {"ok": True, "token": token, "claims": new_ctx.to_claims()}
        except Exception as exc:  # noqa: BLE001
            return 401, {"ok": False, "error": str(exc)}

    if path == "/api/tasks":
        store = TaskStore(_tasks_root_for(ctx))
        title = str(body.get("title") or body.get("prompt") or "新任务").strip()
        mode = str(body.get("mode") or "craft").strip() or "craft"
        prompt = str(body.get("prompt") or "").strip()
        project_id = str(body.get("project_id") or "").strip()
        try:
            rec = store.create(title=title, mode=mode, prompt=prompt, project_id=project_id)
        except Exception as exc:  # noqa: BLE001
            return 400, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, "task": _task_detail(rec)}

    if path == "/api/projects":
        space = ProjectSpace(_projects_root_for(ctx))
        project_id = str(body.get("project_id") or body.get("id") or "").strip()
        name = str(body.get("name") or project_id).strip()
        description = str(body.get("description") or "").strip()
        if not project_id:
            return 400, {"ok": False, "error": "project_id required"}
        owner = ctx.user_id if ctx else "admin"
        try:
            meta = space.create(
                project_id,
                name=name,
                description=description,
                members=[{"user_id": owner, "role": "owner"}],
            )
            # persist normalized member objects
            meta.members = normalize_members(list(meta.members or []))  # type: ignore[assignment]
            save_project_meta(space, meta)
        except FileExistsError as exc:
            return 409, {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return 400, {"ok": False, "error": str(exc)}
        return 200, {
            "ok": True,
            "project": {**meta.to_dict(), "skill_count": 0, "skills": [], "members": meta.members},
        }

    if path == "/api/skills/install":
        skill_id = str(body.get("skill_id") or body.get("id") or "").strip()
        if not skill_id:
            return 400, {"ok": False, "error": "skill_id required"}
        dest_root = Path("artifacts/skillhub/installed")
        result: dict[str, Any]
        try:
            result = install_from_vendor(skill_id, dest_root=dest_root, force=True)
        except FileNotFoundError:
            cat = SkillCatalog()
            cat.scan()
            meta = next((m for m in cat.list() if m.id == skill_id), None)
            if meta is None or not meta.path:
                return 404, {"ok": False, "error": "skill not found"}
            src = Path(meta.path)
            if src.is_file():
                src = src.parent
            try:
                result = install_skill(src, dest_root, force=True)
            except Exception as exc:  # noqa: BLE001
                return 400, {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return 400, {"ok": False, "error": str(exc)}
        return 200, {"ok": bool(result.get("installed")), **result}

    if path == "/api/runtime/run-task":
        from .runtime import run_task

        tid = str((query.get("task_id") or [body.get("task_id", "")])[0]).strip()
        if not tid:
            return 400, {"ok": False, "error": "task_id required"}
        # V17: live by default unless dry explicitly set
        dry_q = query.get("dry")
        if dry_q is not None:
            dry = dry_q[0] not in {"0", "false", "no"}
        elif "dry" in body:
            dry = _as_bool(body.get("dry"), default=False)
        else:
            dry = False
        result = run_task(tid, dry_run=dry, **_run_task_kwargs(ctx))
        return 200, {"ok": result.ok, **result.to_dict()}

    if path == "/api/harbor/dry-run":
        from .bench.harbor import harbor_dry_run

        job = str(body.get("job") or (query.get("job") or ["local-openai-cbc-office-smoke"])[0]).strip()
        try:
            timeout = float(body.get("timeout") or 90)
        except (TypeError, ValueError):
            timeout = 90.0
        result = harbor_dry_run(job=job, timeout=min(timeout, 180.0))
        return 200, result

    if path == "/api/harbor/score":
        from .bench.harbor import harbor_score_entry

        job = str(body.get("job") or (query.get("job") or ["local-openai-cbc-office-smoke"])[0]).strip()
        live = body.get("live", False)
        if isinstance(live, str):
            live = live.lower() in {"1", "true", "yes"}
        dry = not bool(live)
        try:
            timeout = float(body.get("timeout") or 120)
        except (TypeError, ValueError):
            timeout = 120.0
        result = harbor_score_entry(job=job, dry_run=dry, timeout=min(timeout, 300.0))
        return 200, result

    # /api/projects/<id>/skills/deposit | memory
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "projects":
        project_id = unquote(parts[2])
        space = ProjectSpace(_projects_root_for(ctx))
        try:
            space.load(project_id)
        except FileNotFoundError:
            return 404, {"ok": False, "error": "project not found"}

        if parts[3] == "skills" and len(parts) >= 5 and parts[4] == "deposit":
            uid = ctx.user_id if ctx else "admin"
            allowed, reason = require_role(space, project_id, uid, "editor")
            if not allowed:
                return 403, {"ok": False, "error": reason}
            skill_id = str(body.get("skill_id") or body.get("id") or "").strip()
            skill_path = str(body.get("skill_path") or body.get("path") or "").strip()
            src: Path | None = None
            if skill_path:
                src = Path(skill_path)
            elif skill_id:
                installed = Path("artifacts/skillhub/installed") / skill_id
                if installed.is_dir() and (installed / "SKILL.md").is_file():
                    src = installed
                else:
                    cat = SkillCatalog()
                    cat.scan()
                    meta = next((m for m in cat.list() if m.id == skill_id), None)
                    if meta is None or not meta.path:
                        return 404, {"ok": False, "error": "skill not found"}
                    src = Path(meta.path)
                    if src.is_file():
                        src = src.parent
            else:
                return 400, {"ok": False, "error": "skill_id or skill_path required"}
            try:
                dest = space.deposit_skill(project_id, src)
            except Exception as exc:  # noqa: BLE001
                return 400, {"ok": False, "error": str(exc)}
            return 200, {
                "ok": True,
                "project_id": project_id,
                "deposited": dest.name,
                "skills": space.skill_details(project_id),
            }

        if parts[3] == "memory":
            text = str(body.get("text") or body.get("content") or "")
            mem = space._dir(project_id) / "memory" / "MEMORY.md"  # noqa: SLF001
            mem.parent.mkdir(parents=True, exist_ok=True)
            mem.write_text(text, encoding="utf-8")
            return 200, {"ok": True, "project_id": project_id, "bytes": len(text.encode("utf-8"))}

    # /api/tasks/<id>/messages|actions|patch|delete
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "tasks":
        task_id = unquote(parts[2])
        action = parts[3]
        store = TaskStore(_tasks_root_for(ctx))
        try:
            store.get(task_id)
        except FileNotFoundError:
            return 404, {"ok": False, "error": "task not found"}

        if action == "delete":
            store.delete(task_id)
            return 200, {"ok": True, "deleted": task_id}

        if action == "upload":
            filename = str(body.get("filename") or body.get("name") or "upload.bin")
            result = save_upload(
                store._dir(task_id),  # noqa: SLF001
                filename=filename,
                content_base64=body.get("content_base64"),
                text=body.get("text"),
            )
            if not result.get("ok"):
                return 400, result
            store.add_result(
                task_id,
                {"kind": "upload", "path": result["path"], "bytes": result.get("bytes", 0)},
            )
            store.append_message(task_id, "system", f"已上传附件：{result['path']}（{result.get('bytes', 0)} B）")
            rec = store.get(task_id)
            return 200, {"ok": True, "upload": result, "task": _task_detail(rec)}

        if action == "messages":
            content = str(body.get("content") or body.get("text") or "").strip()
            if not content:
                return 400, {"ok": False, "error": "content required"}
            role = str(body.get("role") or "user").strip() or "user"
            store.append_message(task_id, role, content)
            run = body.get("run", True)
            dry = _as_bool(body.get("dry"), default=False)
            stream = _as_bool(body.get("stream"), default=not dry)
            if run and role == "user":
                from .runtime import run_task

                kwargs = {**_run_task_kwargs(ctx), "dry_run": dry}
                if stream and not dry:
                    import threading

                    def _bg() -> None:
                        try:
                            run_task(task_id, **kwargs)
                        except Exception as exc:  # noqa: BLE001
                            from .console_events import append_event

                            append_event(
                                store._dir(task_id),  # noqa: SLF001
                                {"kind": "error", "terminal": True, "message": str(exc)},
                            )
                            try:
                                store.set_status(task_id, "failed")
                                store.append_message(task_id, "assistant", f"执行未成功：{exc}")
                            except Exception:
                                pass

                    store.set_status(task_id, "running")
                    threading.Thread(target=_bg, daemon=True).start()
                    rec = store.get(task_id)
                    return 200, {"ok": True, "streaming": True, "task": _task_detail(rec)}
                run_task(task_id, **kwargs)
            rec = store.get(task_id)
            return 200, {"ok": True, "streaming": False, "task": _task_detail(rec)}

        if action == "patch":
            meta_patch: dict[str, Any] = {}
            if "pinned" in body:
                meta_patch["pinned"] = bool(body["pinned"])
            if "archived" in body:
                meta_patch["archived"] = bool(body["archived"])
            try:
                rec = store.update(
                    task_id,
                    title=body.get("title"),
                    mode=body.get("mode"),
                    status=body.get("status"),
                    project_id=body.get("project_id") if "project_id" in body else None,
                    meta_patch=meta_patch or None,
                )
            except Exception as exc:  # noqa: BLE001
                return 400, {"ok": False, "error": str(exc)}
            return 200, {"ok": True, "task": _task_detail(rec)}

    # parity extras (models / knowledge / cowrite / memory / members…)
    code, payload = api_post_extra(path, body, ctx)
    if code != 404 or payload.get("error") != "not found":
        return code, payload

    return 404, {"ok": False, "error": "not found"}


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_context(self) -> tuple[TenantContext | None, dict[str, Any] | None]:
        if not auth_required():
            token = parse_bearer(self.headers.get("Authorization"))
            if token:
                try:
                    return verify_token(token), None
                except ValueError as exc:
                    return None, {"ok": False, "error": str(exc)}
            return None, None
        path = urlparse(self.path).path
        if path in _PUBLIC_GET or path == "/api/auth/login":
            return None, None
        token = parse_bearer(self.headers.get("Authorization"))
        if not token:
            # EventSource cannot set Authorization — allow ?access_token=
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            token = (qs.get("access_token") or qs.get("token") or [""])[0].strip() or None
        if not token:
            return None, {"ok": False, "error": "unauthorized", "hint": "POST /api/auth/login"}
        try:
            return verify_token(token), None
        except ValueError as exc:
            return None, {"ok": False, "error": str(exc)}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # static console assets (css/js)
        if path.startswith("/console/") or path in {"/tokens.css", "/shell.css"}:
            rel = path[len("/console/") :] if path.startswith("/console/") else path.lstrip("/")
            target = (_CONSOLE_DIR / rel).resolve()
            if not str(target).startswith(str(_CONSOLE_DIR.resolve())) or not target.is_file():
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            ctype = _STATIC_EXT.get(target.suffix.lower(), "application/octet-stream")
            self._send(200, target.read_bytes(), ctype)
            return

        if path.startswith("/api/"):
            ctx, err = self._auth_context()
            if err is not None:
                body = json.dumps(err, ensure_ascii=False).encode("utf-8")
                self._send(401, body, "application/json; charset=utf-8")
                return

            # binary download
            parts = [p for p in path.strip("/").split("/") if p]
            if (
                len(parts) >= 4
                and parts[0] == "api"
                and parts[1] == "tasks"
                and parts[3] == "download"
                and (query.get("raw") or ["0"])[0] in {"1", "true", "yes"}
            ):
                task_id = unquote(parts[2])
                rel = (query.get("path") or [""])[0]
                store = TaskStore(_tasks_root_for(ctx))
                try:
                    store.get(task_id)
                except FileNotFoundError:
                    self._send(404, b'{"ok":false,"error":"task not found"}', "application/json; charset=utf-8")
                    return
                target, derr = resolve_download(store._dir(task_id), rel)  # noqa: SLF001
                if derr or target is None:
                    self._send(
                        404,
                        json.dumps({"ok": False, "error": derr or "not found"}, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8",
                    )
                    return
                data = target.read_bytes()
                mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
                return

            # SSE: /api/tasks/<id>/events
            parts = [p for p in path.strip("/").split("/") if p]
            if (
                len(parts) >= 4
                and parts[0] == "api"
                and parts[1] == "tasks"
                and parts[3] == "events"
            ):
                task_id = unquote(parts[2])
                store = TaskStore(_tasks_root_for(ctx))
                try:
                    store.get(task_id)
                except FileNotFoundError:
                    self._send(404, b'{"ok":false,"error":"task not found"}', "application/json; charset=utf-8")
                    return
                after = 0
                try:
                    after = int((query.get("after") or ["0"])[0])
                except ValueError:
                    after = 0
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    for frame in iter_sse_frames(store._dir(task_id), after=after):  # noqa: SLF001
                        self.wfile.write(frame)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                return

            if path.startswith("/api/tasks/") and path != "/api/tasks":
                code, payload = api_get_task_path(path, ctx, query)
            elif path.startswith("/api/projects/") and path != "/api/projects":
                code, payload = api_get_project_path(path, ctx)
            elif path.startswith("/api/cowrite/"):
                code, payload = api_get_extra(path, ctx, query)
            elif path in _API_GET_EXACT:
                # prefer parity handlers for new exact routes
                if path in {
                    "/api/models",
                    "/api/knowledge",
                    "/api/cowrite",
                    "/api/library",
                    "/api/memory",
                    "/api/team",
                    "/api/channels",
                }:
                    code, payload = api_get_extra(path, ctx, query)
                else:
                    payload = api_payload(path, ctx, query)
                    code = 200
            else:
                code, payload = api_get_extra(path, ctx, query)
                if code == 404:
                    code, payload = 404, {"ok": False, "error": "not found"}
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")
            return
        # static pages
        if path in {"/", "/index.html", "/shell.html"}:
            target = _SHELL if _SHELL.is_file() else _LEGACY
        elif path in {"/ops", "/ops.html"}:
            target = _OPS if _OPS.is_file() else _LEGACY
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            self._send(404, b"console missing", "text/plain; charset=utf-8")
            return
        self._send(200, target.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        body_obj = _read_json_body(self)
        if path.startswith("/api/"):
            ctx, err = self._auth_context()
            if err is not None and path != "/api/auth/login":
                body = json.dumps(err, ensure_ascii=False).encode("utf-8")
                self._send(401, body, "application/json; charset=utf-8")
                return
            code, payload = api_post(path, query, body_obj, ctx)
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(*, host: str = "127.0.0.1", port: int = 8010) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    mode = "AUTH ON" if auth_required() else "auth optional"
    print(
        f"[wb-console] http://{host}:{port}/  ({mode})  "
        "shell=/ ops=/ops.html  APIs: /api/tasks|/api/auth/login|/api/skills/install"
    )
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="console_server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8010)
    args = p.parse_args(argv)
    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
