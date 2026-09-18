# SPDX-License-Identifier: MIT
"""Extra console APIs — knowledge / cowrite / models / memory / members / team."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .connectors import probe_status as connectors_probe
from .cowrite import CowriteStore
from .knowledge import LocalKnowledgeBase
from .library import LibraryIndex
from .models_profile import ModelProfile, ModelProfileStore
from .project import ProjectSpace
from .runtime.profile_env import apply_profile_env
from .tenant import TenantContext, TenantRoots


def _roots(ctx: TenantContext | None) -> TenantRoots | None:
    if ctx is None:
        return None
    roots = TenantRoots(ctx.tenant_id, ctx.user_id)
    roots.ensure()
    return roots


def _projects_root(ctx: TenantContext | None) -> Path:
    roots = _roots(ctx)
    return roots.projects if roots else Path("artifacts/projects")


def _knowledge_root(ctx: TenantContext | None) -> Path:
    roots = _roots(ctx)
    return roots.knowledge if roots else Path("artifacts/knowledge")


def _cowrite_root(ctx: TenantContext | None) -> Path:
    roots = _roots(ctx)
    return roots.cowrite if roots else Path("artifacts/cowrite")


def _library_root(ctx: TenantContext | None) -> Path:
    roots = _roots(ctx)
    return roots.library if roots else Path("artifacts/library")


def _models_path(ctx: TenantContext | None) -> Path:
    roots = _roots(ctx)
    if roots is not None:
        return roots.models / "profiles.json"
    return Path("artifacts/models/profiles.json")


def normalize_members(raw: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw or []:
        if isinstance(item, str) and item.strip():
            out.append({"user_id": item.strip(), "role": "editor"})
        elif isinstance(item, dict) and item.get("user_id"):
            role = str(item.get("role") or "editor").strip().lower()
            if role not in {"owner", "editor", "viewer"}:
                role = "editor"
            out.append({"user_id": str(item["user_id"]).strip(), "role": role})
    # dedupe keep highest role
    rank = {"viewer": 0, "editor": 1, "owner": 2}
    best: dict[str, str] = {}
    for m in out:
        uid = m["user_id"]
        if uid not in best or rank[m["role"]] > rank[best[uid]]:
            best[uid] = m["role"]
    return [{"user_id": u, "role": r} for u, r in sorted(best.items())]


def member_role(space: ProjectSpace, project_id: str, user_id: str) -> str | None:
    meta = space.load(project_id)
    members = normalize_members(list(meta.members or []))
    if not members:
        return "owner"  # legacy open project
    for m in members:
        if m["user_id"] == user_id:
            return m["role"]
    return None


def require_role(space: ProjectSpace, project_id: str, user_id: str, need: str) -> tuple[bool, str]:
    rank = {"viewer": 0, "editor": 1, "owner": 2}
    role = member_role(space, project_id, user_id)
    if role is None:
        return False, "forbidden: not a project member"
    if rank.get(role, -1) < rank.get(need, 99):
        return False, f"forbidden: need {need}, have {role}"
    return True, role


def save_project_meta(space: ProjectSpace, meta: Any) -> None:
    path = space._dir(meta.project_id) / "project.json"  # noqa: SLF001
    path.write_text(
        __import__("json").dumps(meta.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def api_get_extra(path: str, ctx: TenantContext | None, query: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
    if path == "/api/models":
        store = ModelProfileStore(_models_path(ctx))
        active = store.active()
        return 200, {
            "ok": True,
            "active": active.profile_id if active else "",
            "profiles": [p.to_dict() for p in store.list()],
            "env_model": (__import__("os").environ.get("WB_LLM_MODEL") or "").strip() or None,
        }
    if path == "/api/knowledge":
        kb = LocalKnowledgeBase(_knowledge_root(ctx))
        q = (query.get("q") or [""])[0].strip()
        if q:
            hits = kb.search(q, limit=20)
            return 200, {"ok": True, "query": q, "hits": hits}
        # list sources from chunks
        sources: list[str] = []
        if kb.store_path.is_file():
            seen: set[str] = set()
            for line in kb.store_path.read_text(encoding="utf-8").splitlines()[-200:]:
                try:
                    row = __import__("json").loads(line)
                except Exception:
                    continue
                src = str(row.get("source") or "")
                if src and src not in seen:
                    seen.add(src)
                    sources.append(src)
        return 200, {"ok": True, "sources": sources[-50:], "store": str(kb.store_path)}
    if path == "/api/cowrite":
        store = CowriteStore(_cowrite_root(ctx))
        rows = []
        for p in sorted(store.root.glob("cw-*.json"), reverse=True)[:40]:
            try:
                sess = store.get(p.stem)
                rows.append(
                    {
                        "session_id": sess.session_id,
                        "title": sess.title,
                        "updated_at": sess.updated_at,
                        "turns": len(sess.turns),
                        "doc_chars": len(sess.document or ""),
                    }
                )
            except Exception:
                continue
        return 200, {"ok": True, "sessions": rows}
    if path.startswith("/api/cowrite/") and path != "/api/cowrite":
        sid = path.rstrip("/").split("/")[-1]
        store = CowriteStore(_cowrite_root(ctx))
        try:
            sess = store.get(sid)
        except FileNotFoundError:
            return 404, {"ok": False, "error": "session not found"}
        return 200, {"ok": True, "session": sess.to_dict()}
    if path == "/api/library":
        lib = LibraryIndex(_library_root(ctx))
        entries = [e.to_dict() for e in lib.list_entries()[:80]]
        tree = _library_tree(lib)
        kb = LocalKnowledgeBase(_knowledge_root(ctx))
        kb_files: list[dict[str, Any]] = []
        uploads = kb.root / "uploads"
        if uploads.is_dir():
            for p in sorted(uploads.rglob("*"))[:60]:
                if p.is_file():
                    kb_files.append(
                        {
                            "path": p.relative_to(kb.root).as_posix(),
                            "bytes": p.stat().st_size,
                        }
                    )
        return 200, {
            "ok": True,
            "entries": entries,
            "tree": tree,
            "knowledge_files": kb_files,
            "content_root": str(lib.content_dir),
        }
    if path == "/api/worktree":
        roots = _roots(ctx)
        wt_root = (roots.root / "worktrees") if roots else Path("artifacts/worktrees")
        reg = wt_root / "registry.json"
        rows: list[dict[str, Any]] = []
        if reg.is_file():
            try:
                data = __import__("json").loads(reg.read_text(encoding="utf-8"))
                rows = list(data) if isinstance(data, list) else []
            except Exception:
                rows = []
        return 200, {"ok": True, "worktrees": rows, "root": str(wt_root)}
    if path == "/api/channels":
        probe = connectors_probe()
        return 200, {
            "ok": True,
            **probe,
            "wizard": _channel_wizard(probe),
        }
    if path == "/api/team":
        experts = _list_team_experts()
        return 200, {
            "ok": True,
            "available": True,
            "experts": experts,
            "modes": ["supervisor", "parallel"],
            "hint": "壳内可 dry-run / 限员实跑；完整编排亦可用 team.live_cli",
            "shell_note": "选择专家团后输入问题，默认演练（dry-run）；取消演练将调用本地 LLM",
        }
    if path == "/api/memory":
        project_id = (query.get("project_id") or [""])[0].strip()
        if project_id:
            space = ProjectSpace(_projects_root(ctx))
            try:
                text = space.memory_text(project_id, limit=20000)
            except FileNotFoundError:
                return 404, {"ok": False, "error": "project not found"}
            return 200, {"ok": True, "scope": "project", "project_id": project_id, "text": text}
        # tenant user workspace memory stub
        roots = _roots(ctx)
        mem = (roots.root / "MEMORY.md") if roots else Path("MEMORY.md")
        text = mem.read_text(encoding="utf-8", errors="replace") if mem.is_file() else ""
        return 200, {"ok": True, "scope": "workspace", "path": str(mem), "text": text}
    return 404, {"ok": False, "error": "not found"}


def _library_tree(lib: LibraryIndex) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if not lib.content_dir.is_dir():
        return nodes
    for p in sorted(lib.content_dir.rglob("*"))[:120]:
        if p.is_file():
            nodes.append(
                {
                    "path": p.relative_to(lib.root).as_posix(),
                    "name": p.name,
                    "bytes": p.stat().st_size,
                    "kind": "file",
                }
            )
        elif p.is_dir():
            nodes.append(
                {
                    "path": p.relative_to(lib.root).as_posix(),
                    "name": p.name,
                    "kind": "dir",
                }
            )
    return nodes


def _channel_wizard(probe: dict[str, Any]) -> list[dict[str, Any]]:
    china = probe.get("china_im") if isinstance(probe.get("china_im"), dict) else {}
    msg = probe.get("messaging") if isinstance(probe.get("messaging"), dict) else {}
    feishu = probe.get("feishu") if isinstance(probe.get("feishu"), dict) else {}
    steps = [
        {
            "id": "feishu",
            "title": "飞书 / Lark",
            "env": ["FEISHU_WEBHOOK", "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID"],
            "ready": bool(feishu.get("configured") or feishu.get("webhook_set")),
            "hint": "配置 Webhook 或应用凭据后重启 console",
        },
        {
            "id": "dingtalk",
            "title": "钉钉",
            "env": ["DINGTALK_WEBHOOK", "DINGTALK_SECRET"],
            "ready": bool((china or {}).get("dingtalk", {}).get("configured"))
            if isinstance(china.get("dingtalk"), dict)
            else bool(china.get("dingtalk_configured")),
            "hint": "设置 DINGTALK_WEBHOOK（可选 SECRET）",
        },
        {
            "id": "wecom",
            "title": "企业微信",
            "env": ["WECOM_WEBHOOK", "WECOM_CORP_ID", "WECOM_AGENT_ID", "WECOM_SECRET"],
            "ready": bool((china or {}).get("wecom", {}).get("configured"))
            if isinstance(china.get("wecom"), dict)
            else bool(china.get("wecom_configured")),
            "hint": "群机器人 Webhook 或应用凭据",
        },
        {
            "id": "outbound",
            "title": "出站开关",
            "env": ["WB_ALLOW_OUTBOUND"],
            "ready": bool(probe.get("outbound_allowed")),
            "hint": "生产出站需 WB_ALLOW_OUTBOUND=1",
        },
    ]
    if msg:
        steps.append(
            {
                "id": "messaging",
                "title": "通用消息桥",
                "env": ["WB_MESSAGE_BRIDGE"],
                "ready": bool(msg.get("ok") or msg.get("configured")),
                "hint": str(msg.get("hint") or "见 connectors.messaging"),
            }
        )
    return steps


def _default_expert_library() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "octop"
        / "infra"
        / "agents"
        / "experts"
        / "library"
    )


def _list_team_experts(limit: int = 40) -> list[dict[str, Any]]:
    root = _default_expert_library()
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        soul = d / "SOUL.md"
        if not soul.is_file():
            continue
        name = d.name
        # prefer *Team* for shell roster; still include a few singles if needed
        is_team = "Team" in name or "team" in name
        if not is_team and len(rows) > 8:
            continue
        try:
            head = soul.read_text(encoding="utf-8", errors="replace")[:240].replace("\n", " ")
        except Exception:
            head = ""
        rows.append({"id": name, "name": name, "preview": head, "is_team": is_team})
        if len(rows) >= limit:
            break
    rows.sort(key=lambda r: (0 if r.get("is_team") else 1, r["id"]))
    return rows[:limit]


def api_post_extra(
    path: str,
    body: dict[str, Any],
    ctx: TenantContext | None,
) -> tuple[int, dict[str, Any]]:
    if path == "/api/models/activate":
        pid = str(body.get("profile_id") or body.get("id") or "").strip()
        if not pid:
            return 400, {"ok": False, "error": "profile_id required"}
        store = ModelProfileStore(_models_path(ctx))
        try:
            prof = store.set_active(pid)
        except FileNotFoundError as exc:
            return 404, {"ok": False, "error": str(exc)}
        applied = apply_profile_env(prof, path=_models_path(ctx))
        return 200, {"ok": True, "active": prof.to_dict(), "applied": applied}
    if path == "/api/models":
        pid = str(body.get("profile_id") or body.get("id") or "").strip()
        if not pid:
            return 400, {"ok": False, "error": "profile_id required"}
        prof = ModelProfile(
            profile_id=pid,
            base_url=str(body.get("base_url") or "http://127.0.0.1:11434/v1"),
            model=str(body.get("model") or "qwen2.5:3b"),
            api_key_env=str(body.get("api_key_env") or "OPENAI_API_KEY"),
            temperature=float(body.get("temperature", 0.2)),
            max_tokens=int(body.get("max_tokens", 4096)),
        )
        store = ModelProfileStore(_models_path(ctx))
        store.upsert(prof)
        if body.get("activate", True):
            store.set_active(pid)
            apply_profile_env(prof, path=_models_path(ctx))
        return 200, {"ok": True, "profile": prof.to_dict()}
    if path == "/api/knowledge/ingest":
        text = str(body.get("text") or "")
        title = str(body.get("title") or body.get("source") or "note.md").strip() or "note.md"
        kb = LocalKnowledgeBase(_knowledge_root(ctx))
        if text:
            dest = kb.root / "uploads" / title
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            chunks = kb.ingest_file(dest)
            return 200, {"ok": True, "chunks": len(chunks), "source": str(dest)}
        path_s = str(body.get("path") or "").strip()
        if not path_s:
            return 400, {"ok": False, "error": "text or path required"}
        chunks = kb.ingest_file(path_s)
        return 200, {"ok": True, "chunks": len(chunks), "source": path_s}
    if path == "/api/library/ingest":
        text = str(body.get("text") or "")
        title = str(body.get("title") or "note.md").strip() or "note.md"
        if not text:
            return 400, {"ok": False, "error": "text required"}
        lib = LibraryIndex(_library_root(ctx))
        tmp = lib.content_dir / title
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        entry = lib.add_file(tmp, title=title, tags=list(body.get("tags") or []))
        return 200, {"ok": True, "entry": entry.to_dict()}
    if path == "/api/cowrite":
        store = CowriteStore(_cowrite_root(ctx))
        title = str(body.get("title") or "共写会话").strip()
        seed = str(body.get("seed") or body.get("document") or "")
        sess = store.start(title, seed=seed)
        return 200, {"ok": True, "session": sess.to_dict()}
    if path.startswith("/api/cowrite/") and path.endswith("/append"):
        sid = path.split("/")[3]
        store = CowriteStore(_cowrite_root(ctx))
        author = str(body.get("author") or "human")
        text = str(body.get("text") or body.get("content") or "").strip()
        if not text:
            return 400, {"ok": False, "error": "text required"}
        try:
            sess = store.append(sid, author, text)
        except FileNotFoundError:
            return 404, {"ok": False, "error": "session not found"}
        return 200, {"ok": True, "session": sess.to_dict()}
    if path == "/api/memory":
        project_id = str(body.get("project_id") or "").strip()
        text = str(body.get("text") or body.get("content") or "")
        if project_id:
            space = ProjectSpace(_projects_root(ctx))
            try:
                space.load(project_id)
            except FileNotFoundError:
                return 404, {"ok": False, "error": "project not found"}
            uid = ctx.user_id if ctx else "admin"
            ok, reason = require_role(space, project_id, uid, "editor")
            if not ok:
                return 403, {"ok": False, "error": reason}
            mem = space._dir(project_id) / "memory" / "MEMORY.md"  # noqa: SLF001
            mem.parent.mkdir(parents=True, exist_ok=True)
            mem.write_text(text, encoding="utf-8")
            return 200, {"ok": True, "scope": "project", "project_id": project_id, "bytes": len(text.encode())}
        roots = _roots(ctx)
        mem = (roots.root / "MEMORY.md") if roots else Path("MEMORY.md")
        mem.parent.mkdir(parents=True, exist_ok=True)
        mem.write_text(text, encoding="utf-8")
        return 200, {"ok": True, "scope": "workspace", "path": str(mem), "bytes": len(text.encode())}
    if path == "/api/worktree":
        from .runtime.worktree_bind import create_task_with_worktree

        title = str(body.get("title") or "worktree-task").strip() or "worktree-task"
        repo = str(body.get("repo") or body.get("path") or "").strip()
        dry = bool(body.get("dry_run", True))
        live = bool(body.get("live", False))
        roots = _roots(ctx)
        tasks_root = roots.tasks if roots else Path("artifacts/tasks")
        wt_root = (roots.root / "worktrees") if roots else Path("artifacts/worktrees")
        if not repo:
            return 400, {"ok": False, "error": "repo path required"}
        try:
            out = create_task_with_worktree(
                title,
                tasks_root=tasks_root,
                repo=repo,
                worktrees_dir=wt_root,
                mode=str(body.get("mode") or "craft"),
                prompt=str(body.get("prompt") or ""),
                with_worktree=True,
                dry_run=dry and not live,
            )
        except Exception as exc:  # noqa: BLE001
            return 400, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, **out, "dry_run": dry and not live}
    if path == "/api/team/run":
        expert = str(body.get("expert") or body.get("expert_id") or "").strip()
        query = str(body.get("query") or body.get("content") or "").strip()
        if not expert or not query:
            return 400, {"ok": False, "error": "expert and query required"}
        dry = bool(body.get("dry_run", True))
        max_members = int(body.get("max_members") or 2)
        library = _default_expert_library()
        expert_dir = library / expert
        if not (expert_dir / "SOUL.md").is_file():
            return 404, {"ok": False, "error": f"expert not found: {expert}"}
        try:
            from .team.parser import write_team_artifacts
            from .team.runtime import MockMemberCaller, TeamAgentRuntime

            write_team_artifacts(expert_dir)
            if dry:
                rt = TeamAgentRuntime.from_expert_dir(expert_dir, caller=MockMemberCaller())
            else:
                from .team.llm import OpenAICompatCaller
                from .team.probe import probe_local_llm

                probe = probe_local_llm()
                if not probe.ok:
                    return 503, {"ok": False, "error": "local LLM unreachable", "probe": probe.to_dict()}
                import os

                model = (
                    str(body.get("model") or "").strip()
                    or os.environ.get("WB_LLM_MODEL")
                    or probe.preferred_model
                )
                base = (
                    str(body.get("base_url") or "").strip()
                    or os.environ.get("WB_LLM_BASE_URL")
                    or probe.base_url
                )
                caller = OpenAICompatCaller(base_url=base, model=model, max_tokens=512)
                rt = TeamAgentRuntime.from_expert_dir(expert_dir, caller=caller)
            if max_members > 0 and len(rt.definition.members) > max_members:
                kept = rt.definition.members[:max_members]
                rt.definition.members = kept
                for phase in rt.definition.phases:
                    ids = [m.agent_id for m in kept if m.agent_id in phase.member_ids]
                    object.__setattr__(phase, "member_ids", tuple(ids))
            result = rt.run_sync(query, dry_run=dry)
            return 200, {
                "ok": True,
                "dry_run": dry,
                "team_id": result.team_id,
                "final_report": (result.final_report or "")[:8000],
                "members": [
                    {
                        "agent_id": o.agent_id,
                        "display_name": o.display_name,
                        "content": (o.content or "")[:2000],
                    }
                    for o in (result.member_outputs or [])
                ],
                "plan": result.plan,
            }
        except Exception as exc:  # noqa: BLE001
            return 500, {"ok": False, "error": str(exc)}
    # /api/projects/<id>/members
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "projects" and parts[3] == "members":
        project_id = parts[2]
        space = ProjectSpace(_projects_root(ctx))
        try:
            meta = space.load(project_id)
        except FileNotFoundError:
            return 404, {"ok": False, "error": "project not found"}
        uid = ctx.user_id if ctx else "admin"
        ok, reason = require_role(space, project_id, uid, "owner")
        if not ok and normalize_members(list(meta.members or [])):
            return 403, {"ok": False, "error": reason}
        action = str(body.get("action") or "upsert").strip()
        target = str(body.get("user_id") or "").strip()
        role = str(body.get("role") or "editor").strip().lower()
        if not target:
            return 400, {"ok": False, "error": "user_id required"}
        members = normalize_members(list(meta.members or []))
        if action == "remove":
            members = [m for m in members if m["user_id"] != target]
        else:
            if role not in {"owner", "editor", "viewer"}:
                role = "editor"
            members = [m for m in members if m["user_id"] != target]
            members.append({"user_id": target, "role": role})
            members = normalize_members(members)
        meta.members = members  # type: ignore[assignment]
        save_project_meta(space, meta)
        return 200, {"ok": True, "project_id": project_id, "members": members}
    return 404, {"ok": False, "error": "not found"}
