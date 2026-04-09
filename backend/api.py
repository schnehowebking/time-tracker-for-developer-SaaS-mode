from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.auth import create_session_token, hash_password, parse_session_token, verify_password
from tracker.config import load_config, save_config
from tracker.service import start_tracker, stop_tracker, tracker_status
from tracker.storage import Storage, UserRecord


def _config_path() -> Path:
    env_path = os.getenv("TRACKER_CONFIG_PATH", "config/default_config.yaml")
    return Path(env_path).resolve()


def create_app() -> FastAPI:
    cfg = load_config(_config_path())
    storage = Storage(cfg.db_path)
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

    app = FastAPI(title="Time Tracker API", version="0.3.0")
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
        name="static",
    )

    def current_user(request: Request) -> UserRecord | None:
        token = request.cookies.get(cfg.security.cookie_name)
        if not token:
            return None
        payload = parse_session_token(token, cfg.security.secret_key)
        if not payload:
            return None
        return storage.get_user_by_id(str(payload.get("user_id", "")))

    def require_user(request: Request) -> UserRecord:
        user = current_user(request)
        if not user or not user.is_active:
            raise PermissionError("auth")
        return user

    def require_admin(user: UserRecord) -> None:
        if user.role not in {"owner", "admin"}:
            raise PermissionError("admin")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/auth/register", response_class=HTMLResponse)
    def register_page(request: Request) -> HTMLResponse:
        if current_user(request):
            return RedirectResponse(url="/", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"title": "Create Workspace", "has_users": storage.count_users() > 0, "error": None},
        )

    @app.post("/auth/register")
    def register_submit(
        request: Request,
        organization_name: str = Form(...),
        full_name: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
    ):
        if storage.get_user_by_email(email):
            return templates.TemplateResponse(
                request=request,
                name="register.html",
                context={"title": "Create Workspace", "has_users": True, "error": "Email already exists."},
                status_code=400,
            )

        org, user = storage.bootstrap_owner(
            organization_name=organization_name,
            owner_name=full_name,
            owner_email=email,
            password_hash=hash_password(password),
        )

        # Keep local agent defaults aligned with first SaaS workspace owner.
        cfg.app.organization_id = org.id
        cfg.app.user_id = user.id
        save_config(cfg)

        token = create_session_token(user.id, org.id, user.role, cfg.security.secret_key)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(cfg.security.cookie_name, token, httponly=True, samesite="lax")
        return resp

    @app.get("/auth/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        if current_user(request):
            return RedirectResponse(url="/", status_code=303)
        return templates.TemplateResponse(request=request, name="login.html", context={"title": "Login", "error": None})

    @app.post("/auth/login")
    def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
        user = storage.get_user_by_email(email)
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"title": "Login", "error": "Invalid credentials."},
                status_code=400,
            )
        token = create_session_token(user.id, user.organization_id, user.role, cfg.security.secret_key)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(cfg.security.cookie_name, token, httponly=True, samesite="lax")
        return resp

    @app.post("/auth/logout")
    def logout() -> RedirectResponse:
        resp = RedirectResponse(url="/auth/login", status_code=303)
        resp.delete_cookie(cfg.security.cookie_name)
        return resp

    @app.get("/api/status")
    def api_status(request: Request) -> dict:
        user = require_user(request)
        data = tracker_status(cfg)
        data["tenant"] = user.organization_id
        return data

    @app.post("/api/tracker/start")
    def api_start(request: Request) -> dict[str, object]:
        require_user(request)
        return start_tracker(cfg, config_path=cfg.source_path)

    @app.post("/api/tracker/stop")
    def api_stop(request: Request) -> dict[str, object]:
        require_user(request)
        return stop_tracker(cfg)

    @app.get("/api/sessions")
    def api_sessions(request: Request, limit: int = 100) -> dict[str, object]:
        user = require_user(request)
        sessions = storage.list_sessions(limit=min(max(limit, 1), 500), organization_id=user.organization_id)
        return {"items": [asdict(item) for item in sessions]}

    @app.get("/api/summary")
    def api_summary(request: Request, days: int = 7) -> dict[str, object]:
        user = require_user(request)
        days = min(max(days, 1), 90)
        summary = storage.get_summary(days=days, organization_id=user.organization_id)
        daily = storage.get_daily_tracked(days=max(days, 7), organization_id=user.organization_id)
        projects = storage.get_project_breakdown(days=days, organization_id=user.organization_id)
        app_usage = storage.get_app_usage(days=days, organization_id=user.organization_id, limit=10)
        return {
            "days": days,
            "summary": asdict(summary),
            "daily": daily,
            "projects": projects,
            "app_usage": app_usage,
        }

    @app.post("/api/agent/sync")
    async def api_agent_sync(
        request: Request,
        x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
    ) -> JSONResponse:
        if x_agent_key != cfg.security.agent_ingest_key:
            raise HTTPException(status_code=401, detail="Invalid agent key")
        payload = await request.json()
        events = payload.get("events", [])
        return JSONResponse({"ok": True, "accepted": len(events)})

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, days: int = 7):
        user = current_user(request)
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)

        days = min(max(days, 1), 90)
        summary = storage.get_summary(days=days, organization_id=user.organization_id)
        sessions = storage.list_sessions(limit=20, organization_id=user.organization_id)
        daily = storage.get_daily_tracked(days=max(days, 7), organization_id=user.organization_id)
        projects = storage.get_project_breakdown(days=days, organization_id=user.organization_id)
        app_usage = storage.get_app_usage(days=days, organization_id=user.organization_id, limit=10)
        time_edits = storage.list_time_edits(organization_id=user.organization_id, limit=20)
        status = tracker_status(cfg)
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "title": cfg.api.dashboard_title,
                "days": days,
                "status": status,
                "summary": asdict(summary),
                "sessions": [asdict(item) for item in sessions],
                "daily": daily,
                "projects": projects,
                "app_usage": app_usage,
                "time_edits": time_edits,
                "auth_user": asdict(user),
            },
        )

    @app.post("/sessions/{session_id}/edit")
    def edit_session_time(
        request: Request,
        session_id: str,
        new_tracked_seconds: int = Form(...),
        reason: str = Form("manual edit"),
    ):
        user = current_user(request)
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)
        require_admin(user)
        ok = storage.update_session_tracked_seconds(
            session_id=session_id,
            new_seconds=max(0, new_tracked_seconds),
            editor_user_id=user.id,
            reason=reason,
        )
        if not ok:
            return RedirectResponse(url="/?error=session_not_found", status_code=303)
        return RedirectResponse(url="/", status_code=303)

    @app.get("/users", response_class=HTMLResponse)
    def users_page(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)
        require_admin(user)
        users = storage.list_users(user.organization_id)
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context={"title": "User Management", "users": [asdict(u) for u in users], "auth_user": asdict(user)},
        )

    @app.post("/users")
    def create_user_submit(
        request: Request,
        full_name: str = Form(...),
        email: str = Form(...),
        role: str = Form("member"),
        password: str = Form(...),
    ):
        user = current_user(request)
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)
        require_admin(user)
        if storage.get_user_by_email(email):
            return RedirectResponse(url="/users?error=email_exists", status_code=303)

        role = role if role in {"admin", "member"} else "member"
        storage.create_user(
            organization_id=user.organization_id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
        )
        return RedirectResponse(url="/users", status_code=303)

    @app.post("/users/{target_user_id}/toggle")
    def toggle_user(request: Request, target_user_id: str):
        user = current_user(request)
        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)
        require_admin(user)
        target = storage.get_user_by_id(target_user_id)
        if target and target.organization_id == user.organization_id and target.id != user.id:
            storage.set_user_active(user.organization_id, target.id, not target.is_active)
        return RedirectResponse(url="/users", status_code=303)

    return app
