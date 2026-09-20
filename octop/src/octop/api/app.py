"""FastAPI app factory."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from scalar_fastapi import get_scalar_api_reference

from octop.api.middleware.jwt_auth import install as install_jwt_auth
from octop.api.middleware.setup_lockdown import install as install_setup_lockdown
from octop.api.openapi_meta import API_DESCRIPTION, OPENAPI_TAGS, configure_openapi
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.server import OctopServer
from octop.infra.utils.locale import resolve_request_locale

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _RouterMount:
    router: Any
    prefix: str
    tags: Sequence[str]


_NO_CACHE_DASHBOARD_NAMES = frozenset({"sw.js", "manifest.json", "index.html"})


def _resolve_xiongbao_console_dir(cfg: Any) -> Path | None:
    """Resolve the 熊宝 Agent UI directory; ``None`` if it cannot be located.

    The default ``console_path`` (``contrib/workbuddy/console``) is relative to the
    octop workspace root, which is the parent of the installed ``src/octop`` package.
    """
    if cfg is None:
        return None
    raw = Path(str(cfg.xiongbao.console_path))
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        # src/octop/api/app.py → src/octop/api → src/octop → src → octop (workspace root)
        workspace_root = Path(__file__).resolve().parents[3]
        candidates.append(workspace_root / raw)
        candidates.append(Path.cwd() / raw)
    for c in candidates:
        if c.is_dir() and (c / "shell.html").is_file():
            return c
    return None


def dashboard_cache_control(full_path: str) -> str | None:
    """Cache-Control for a dashboard SPA path, or ``None`` to leave unset."""
    name = Path(full_path).name.lower() if full_path else "index.html"
    if not full_path or name in _NO_CACHE_DASHBOARD_NAMES:
        return "no-cache"
    # Vite emits content-hashed files under assets/ — safe to pin forever.
    if full_path.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    return None


def _dashboard_response(path: Path, full_path: str) -> FileResponse:
    response = FileResponse(path)
    cache_control = dashboard_cache_control(full_path)
    if cache_control is not None:
        response.headers["Cache-Control"] = cache_control
    return response


def is_dashboard_asset_path(full_path: str) -> bool:
    """True for hashed build artifacts that must 404 instead of falling back."""
    return full_path.startswith("assets/")


def _dashboard_fallback(index_file: Path, full_path: str) -> FileResponse:
    """Serve the SPA shell for routes; 404 for a missing hashed asset.

    Answering ``/assets/index.<old-hash>.js`` with ``index.html`` makes the
    browser reject HTML as a module script ("not a valid JavaScript MIME
    type"), which hides the real cause — a stale shell after an upgrade.
    """
    if is_dashboard_asset_path(full_path):
        raise HTTPException(status_code=404, detail="Not Found")
    return _dashboard_response(index_file, "")


def _mount_routers(app: FastAPI, mounts: Sequence[_RouterMount]) -> None:
    for spec in mounts:
        app.include_router(spec.router, prefix=spec.prefix, tags=list(spec.tags))


def _install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(OctopError)
    async def _octop(request: Request, exc: OctopError) -> JSONResponse:
        # Client responses are locale-localized; log the original English message
        # so INTERNAL_ERROR (and other 5xx) remain diagnosable in ~/.octop/logs.
        if exc.status >= 500:
            logger.error(
                "OctopError %s in %s: %s",
                exc.code.value,
                request.url.path,
                exc.message,
                exc_info=exc,
            )
        locale = resolve_request_locale(request)
        return JSONResponse(status_code=exc.status, content=exc.to_envelope(locale=locale))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception in %s", request.url.path)
        locale = resolve_request_locale(request)
        err = OctopError.localized(ErrorCode.INTERNAL_ERROR, locale)
        return JSONResponse(status_code=err.status, content=err.to_envelope())


def build_app(server: OctopServer) -> FastAPI:
    cfg = server.services.config if server.services else getattr(server, "config", None)
    enable_dashboard = cfg.enable_dashboard if cfg else True
    enable_api_docs = cfg.enable_api_docs if cfg else False
    enable_mobile = (
        cfg.capabilities.mobile.enabled if cfg and cfg.capabilities.mobile.enabled else False
    )

    app = FastAPI(
        title="Octop API",
        version="0.1.0",
        description=API_DESCRIPTION,
        openapi_url="/api/openapi.json" if enable_api_docs else None,
        openapi_tags=OPENAPI_TAGS,
    )
    configure_openapi(app)
    app.state.octop_server = server
    _install_exception_handlers(app)

    if cfg and cfg.cors_origins:
        from octop.api.deps import ACCESS_TOKEN_RESPONSE_HEADER

        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[ACCESS_TOKEN_RESPONSE_HEADER],
        )

    install_jwt_auth(app, server)
    install_setup_lockdown(app, server)

    from octop.infra.setup.tls.challenge import challenge_store

    @app.get("/.well-known/acme-challenge/{token}", include_in_schema=False)
    async def acme_http01_challenge(token: str) -> PlainTextResponse:
        body = challenge_store.get(token)
        if body is None:
            raise HTTPException(status_code=404, detail="challenge not found")
        return PlainTextResponse(body)

    from octop.api.routers import (
        acp,
        admin,
        agent_files,
        agent_tools,
        agents,
        auth,
        auth_oidc,
        backup,
        browser,
        channels,
        chat,
        connectors,
        credits,
        cron,
        desktop,
        envs,
        experts,
        health,
        i18n,
        internal_mcp,
        invites,
        knowledge_bases,
        mbti,
        media_generation,
        memory,
        memory_portable,
        mobile,
        ollama_models,
        onnx_models,
        plugins,
        preferences,
        proactive_care,
        providers,
        search,
        settings,
        setup,
        skill_packages,
        skills,
        slash,
        subagents,
        terminal,
        update,
        uploads,
        usage,
        users,
    voice,
    workspace,
    xb,
)
    from octop.api.routers.filesystem import router as filesystem_router
    from octop.api.routers.observability import router as observability_router
    from octop.api.routers.providers import admin_router as admin_providers_router
    from octop.api.routers.security import router as security_router
    from octop.api.routers.storage_backends import admin_router as admin_storage_router
    from octop.api.routers.storage_backends import user_router as storage_backends_user_router
    from octop.api.routers.tls import router as tls_router
    from octop.api.routers.voice import admin_router as admin_voice_router

    _mount_routers(
        app,
        [
            _RouterMount(setup.router, "/api", ["setup"]),
            _RouterMount(auth.router, "/api/auth", ["auth"]),
            _RouterMount(auth_oidc.router, "/api/auth", ["auth"]),
            _RouterMount(invites.public_router, "/api/auth/invite", ["auth"]),
            _RouterMount(preferences.router, "/api", ["auth"]),
            _RouterMount(i18n.router, "/api", ["i18n"]),
            _RouterMount(health.router, "/api/health", ["health"]),
            _RouterMount(invites.admin_router, "/api/users/invites", ["users"]),
            _RouterMount(users.router, "/api/users", ["users"]),
            _RouterMount(agents.router, "/api/agents", ["agents"]),
            _RouterMount(agent_tools.router, "/api", ["agents"]),
            _RouterMount(acp.router, "/api", ["agents"]),
            _RouterMount(chat.router, "/api", ["chat"]),
            _RouterMount(slash.router, "/api", ["slash"]),
            _RouterMount(connectors.router, "/api", ["connectors"]),
            _RouterMount(knowledge_bases.router, "/api", ["knowledge"]),
            _RouterMount(internal_mcp.router, "/api", ["internal-mcp"]),
            _RouterMount(channels.router, "/api", ["channels"]),
            _RouterMount(cron.router, "/api", ["cron"]),
            _RouterMount(settings.router, "/api", ["settings"]),
            _RouterMount(envs.router, "/api", ["envs"]),
            _RouterMount(search.router, "/api", ["search"]),
            _RouterMount(providers.router, "/api/providers", ["providers"]),
            _RouterMount(voice.router, "/api/voice", ["voice"]),
            _RouterMount(admin.router, "/api/admin", ["admin"]),
            _RouterMount(backup.router, "/api/admin", ["admin"]),
            _RouterMount(admin_providers_router, "/api/admin/providers", ["admin"]),
            _RouterMount(admin_voice_router, "/api/admin/voice/providers", ["admin"]),
            _RouterMount(observability_router, "/api/admin/observability", ["observability"]),
            _RouterMount(
                media_generation.router,
                "/api/admin/media-generation",
                ["providers"],
            ),
            _RouterMount(tls_router, "/api/admin/tls", ["tls"]),
            _RouterMount(security_router, "/api/admin/security", ["security"]),
            _RouterMount(admin_storage_router, "/api/admin/storage-backends", ["admin"]),
            _RouterMount(
                storage_backends_user_router, "/api/storage-backends", ["storage-backends"]
            ),
            _RouterMount(filesystem_router, "/api/filesystem", ["filesystem"]),
            _RouterMount(mbti.router, "/api", ["mbti"]),
            _RouterMount(experts.router, "/api", ["experts"]),
            _RouterMount(workspace.router, "/api", ["workspace"]),
            _RouterMount(agent_files.router, "/api", ["agent_files"]),
            _RouterMount(memory.router, "/api", ["memory"]),
            _RouterMount(memory_portable.router, "/api", ["memory"]),
            _RouterMount(proactive_care.router, "/api", ["proactive-care"]),
            _RouterMount(usage.router, "/api", ["usage"]),
            _RouterMount(usage.admin_router, "/api/admin", ["admin"]),
            _RouterMount(credits.router, "/api", ["credits"]),
            _RouterMount(credits.admin_router, "/api/admin", ["admin", "credits"]),
            _RouterMount(skill_packages.router, "/api", ["skill-packages"]),
            _RouterMount(skills.router, "/api", ["skills"]),
            _RouterMount(subagents.router, "/api", ["subagents"]),
            _RouterMount(terminal.router, "/api", ["terminal"]),
            _RouterMount(uploads.router, "/api", ["chat"]),
            _RouterMount(update.router, "/api", ["update"]),
            _RouterMount(browser.router, "/api", ["browser"]),
            _RouterMount(desktop.router, "/api", ["desktop"]),
            _RouterMount(ollama_models.router, "/api", ["ollama"]),
            _RouterMount(onnx_models.router, "/api", ["onnx"]),
            _RouterMount(plugins.router, "/api", ["plugins"]),
            _RouterMount(xb.router, "/api", ["xiongbao"]),
        ],
    )

    if enable_mobile:
        _mount_routers(
            app,
            [
                _RouterMount(mobile.router, "/api", ["mobile"]),
            ],
        )

    if enable_api_docs:

        @app.get("/api/docs", include_in_schema=False)
        async def api_docs() -> HTMLResponse:
            return get_scalar_api_reference(
                openapi_url=app.openapi_url,
                title="Octop API",
            )

    if enable_dashboard:
        cfg_local = cfg
        mode = (getattr(cfg_local, "dashboard_mode", "legacy") if cfg_local else "legacy")
        legacy_dashboard_dir = Path(__file__).parent.parent / "dashboard"
        xb_console_dir = _resolve_xiongbao_console_dir(cfg_local) if mode == "xiongbao" else None

        if mode == "xiongbao" and xb_console_dir is not None:
            # 熊宝 Agent UI：挂静态资源 + 默认首页跳到 shell.html
            app.mount(
                "/console",
                StaticFiles(directory=xb_console_dir, html=True),
                name="xb-console",
            )
            shell_file = xb_console_dir / "shell.html"
            ops_file = xb_console_dir / "ops.html"

            @app.get("/", include_in_schema=False)
            async def root_index() -> FileResponse:
                return FileResponse(shell_file)

            @app.get("/ops", include_in_schema=False)
            async def root_ops() -> FileResponse:
                if ops_file.is_file():
                    return FileResponse(ops_file)
                raise HTTPException(status_code=404, detail="ops.html not found")

            @app.get("/{full_path:path}", include_in_schema=False)
            async def spa_fallback(full_path: str) -> FileResponse:
                # API 路径不能被 SPA fallback 截胡
                if full_path.startswith(("api/", "ws/", "console/")):
                    raise HTTPException(status_code=404, detail="Not Found")
                if full_path in {"shell.html", "ops.html"}:
                    target = xb_console_dir / full_path
                    if target.is_file():
                        return FileResponse(target)
                if full_path:
                    raw_path = Path(full_path)
                    if raw_path.is_absolute() or ".." in raw_path.parts:
                        return FileResponse(shell_file)
                    candidate = (xb_console_dir / Path(*raw_path.parts)).resolve()
                    try:
                        candidate.relative_to(xb_console_dir.resolve())
                    except ValueError:
                        return FileResponse(shell_file)
                    if candidate.is_file():
                        return FileResponse(candidate)
                return FileResponse(shell_file)
        elif mode == "legacy":
            index_file = legacy_dashboard_dir / "index.html"
            if index_file.exists():

                @app.get("/{full_path:path}", include_in_schema=False)
                async def spa_fallback(full_path: str) -> FileResponse:
                    if full_path.startswith(("api/", "ws/")):
                        raise HTTPException(status_code=404, detail="Not Found")

                    if full_path:
                        raw_path = Path(full_path)
                        # Reject absolute paths and parent-dir references before
                        # joining, so user input never drives a path expression.
                        if raw_path.is_absolute() or ".." in raw_path.parts:
                            return _dashboard_fallback(index_file, full_path)
                        candidate = (legacy_dashboard_dir / Path(*raw_path.parts)).resolve()
                        try:
                            candidate.relative_to(legacy_dashboard_dir.resolve())
                        except ValueError:
                            return _dashboard_fallback(index_file, full_path)
                        if candidate.is_file():
                            return _dashboard_response(candidate, full_path)
                    return _dashboard_fallback(index_file, full_path)
        # mode == "none" 或 dashboard 资源缺失 → 不挂任何静态 fallback，API-only

    return app
