from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class TrackingConfig:
    heartbeat_seconds: int
    timezone: str


@dataclass(slots=True)
class ScreenshotsConfig:
    enabled: bool
    interval_seconds_min: int
    interval_seconds_max: int
    capture_all_displays: bool
    image_format: str


@dataclass(slots=True)
class ActivityConfig:
    enabled: bool
    idle_threshold_seconds: int
    auto_pause_on_idle: bool
    idle_grace_seconds: int


@dataclass(slots=True)
class StorageConfig:
    base_dir: str
    db_name: str
    screenshot_dir_name: str
    runtime_state_file: str
    pid_file: str


@dataclass(slots=True)
class ApiConfig:
    host: str
    port: int
    dashboard_title: str


@dataclass(slots=True)
class DesktopUIConfig:
    refresh_interval_seconds: int


@dataclass(slots=True)
class SecurityConfig:
    secret_key: str
    cookie_name: str
    agent_ingest_key: str


@dataclass(slots=True)
class MonitoringConfig:
    app_tracking_enabled: bool
    app_tracking_interval_seconds: int
    infer_browser_url_from_title: bool


@dataclass(slots=True)
class SyncConfig:
    enabled: bool
    endpoint_url: str
    interval_seconds: int


@dataclass(slots=True)
class AppIdentityConfig:
    organization_id: str
    user_id: str
    project_id: str


@dataclass(slots=True)
class AppConfig:
    tracking: TrackingConfig
    screenshots: ScreenshotsConfig
    activity: ActivityConfig
    storage: StorageConfig
    api: ApiConfig
    desktop_ui: DesktopUIConfig
    security: SecurityConfig
    monitoring: MonitoringConfig
    sync: SyncConfig
    app: AppIdentityConfig
    source_path: Path

    @property
    def base_dir(self) -> Path:
        return self.source_path.parent.parent / self.storage.base_dir

    @property
    def db_path(self) -> Path:
        return self.base_dir / self.storage.db_name

    @property
    def screenshot_dir(self) -> Path:
        return self.base_dir / self.storage.screenshot_dir_name

    @property
    def runtime_state_path(self) -> Path:
        return self.base_dir / self.storage.runtime_state_file

    @property
    def pid_file_path(self) -> Path:
        return self.base_dir / self.storage.pid_file


def _required(section: dict[str, Any], key: str) -> Any:
    if key not in section:
        raise ValueError(f"Missing config key: {key}")
    return section[key]


def _to_raw(cfg: AppConfig) -> dict[str, Any]:
    return {
        "tracking": {
            "heartbeat_seconds": cfg.tracking.heartbeat_seconds,
            "timezone": cfg.tracking.timezone,
        },
        "screenshots": {
            "enabled": cfg.screenshots.enabled,
            "interval_seconds_min": cfg.screenshots.interval_seconds_min,
            "interval_seconds_max": cfg.screenshots.interval_seconds_max,
            "capture_all_displays": cfg.screenshots.capture_all_displays,
            "image_format": cfg.screenshots.image_format,
        },
        "activity": {
            "enabled": cfg.activity.enabled,
            "idle_threshold_seconds": cfg.activity.idle_threshold_seconds,
            "auto_pause_on_idle": cfg.activity.auto_pause_on_idle,
            "idle_grace_seconds": cfg.activity.idle_grace_seconds,
        },
        "storage": {
            "base_dir": cfg.storage.base_dir,
            "db_name": cfg.storage.db_name,
            "screenshot_dir_name": cfg.storage.screenshot_dir_name,
            "runtime_state_file": cfg.storage.runtime_state_file,
            "pid_file": cfg.storage.pid_file,
        },
        "api": {
            "host": cfg.api.host,
            "port": cfg.api.port,
            "dashboard_title": cfg.api.dashboard_title,
        },
        "desktop_ui": {
            "refresh_interval_seconds": cfg.desktop_ui.refresh_interval_seconds,
        },
        "security": {
            "secret_key": cfg.security.secret_key,
            "cookie_name": cfg.security.cookie_name,
            "agent_ingest_key": cfg.security.agent_ingest_key,
        },
        "monitoring": {
            "app_tracking_enabled": cfg.monitoring.app_tracking_enabled,
            "app_tracking_interval_seconds": cfg.monitoring.app_tracking_interval_seconds,
            "infer_browser_url_from_title": cfg.monitoring.infer_browser_url_from_title,
        },
        "sync": {
            "enabled": cfg.sync.enabled,
            "endpoint_url": cfg.sync.endpoint_url,
            "interval_seconds": cfg.sync.interval_seconds,
        },
        "app": {
            "organization_id": cfg.app.organization_id,
            "user_id": cfg.app.user_id,
            "project_id": cfg.app.project_id,
        },
    }


def save_config(cfg: AppConfig, path: str | Path | None = None) -> Path:
    target = Path(path).resolve() if path else cfg.source_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(_to_raw(cfg), sort_keys=False), encoding="utf-8")
    return target


def load_config(path: str | Path) -> AppConfig:
    cfg_path = Path(path).resolve()
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    tracking_raw = raw.get("tracking", {})
    screenshots_raw = raw.get("screenshots", {})
    activity_raw = raw.get("activity", {})
    storage_raw = raw.get("storage", {})
    api_raw = raw.get("api", {})
    desktop_ui_raw = raw.get("desktop_ui", {})
    security_raw = raw.get("security", {})
    monitoring_raw = raw.get("monitoring", {})
    sync_raw = raw.get("sync", {})
    app_raw = raw.get("app", {})

    tracking = TrackingConfig(
        heartbeat_seconds=int(_required(tracking_raw, "heartbeat_seconds")),
        timezone=str(_required(tracking_raw, "timezone")),
    )
    screenshots = ScreenshotsConfig(
        enabled=bool(_required(screenshots_raw, "enabled")),
        interval_seconds_min=int(_required(screenshots_raw, "interval_seconds_min")),
        interval_seconds_max=int(_required(screenshots_raw, "interval_seconds_max")),
        capture_all_displays=bool(_required(screenshots_raw, "capture_all_displays")),
        image_format=str(_required(screenshots_raw, "image_format")),
    )
    activity = ActivityConfig(
        enabled=bool(_required(activity_raw, "enabled")),
        idle_threshold_seconds=int(_required(activity_raw, "idle_threshold_seconds")),
        auto_pause_on_idle=bool(activity_raw.get("auto_pause_on_idle", True)),
        idle_grace_seconds=int(activity_raw.get("idle_grace_seconds", 60)),
    )
    storage = StorageConfig(
        base_dir=str(_required(storage_raw, "base_dir")),
        db_name=str(_required(storage_raw, "db_name")),
        screenshot_dir_name=str(_required(storage_raw, "screenshot_dir_name")),
        runtime_state_file=str(_required(storage_raw, "runtime_state_file")),
        pid_file=str(_required(storage_raw, "pid_file")),
    )
    api = ApiConfig(
        host=str(api_raw.get("host", "127.0.0.1")),
        port=int(api_raw.get("port", 8000)),
        dashboard_title=str(api_raw.get("dashboard_title", "Time Tracker Admin Dashboard")),
    )
    desktop_ui = DesktopUIConfig(
        refresh_interval_seconds=int(desktop_ui_raw.get("refresh_interval_seconds", 5))
    )
    security = SecurityConfig(
        secret_key=str(security_raw.get("secret_key", "change-me-in-production")),
        cookie_name=str(security_raw.get("cookie_name", "tt_session")),
        agent_ingest_key=str(security_raw.get("agent_ingest_key", "change-agent-ingest-key")),
    )
    monitoring = MonitoringConfig(
        app_tracking_enabled=bool(monitoring_raw.get("app_tracking_enabled", True)),
        app_tracking_interval_seconds=int(monitoring_raw.get("app_tracking_interval_seconds", 10)),
        infer_browser_url_from_title=bool(monitoring_raw.get("infer_browser_url_from_title", True)),
    )
    sync = SyncConfig(
        enabled=bool(sync_raw.get("enabled", False)),
        endpoint_url=str(sync_raw.get("endpoint_url", "http://127.0.0.1:8000/api/agent/sync")),
        interval_seconds=int(sync_raw.get("interval_seconds", 20)),
    )
    app = AppIdentityConfig(
        organization_id=str(_required(app_raw, "organization_id")),
        user_id=str(_required(app_raw, "user_id")),
        project_id=str(_required(app_raw, "project_id")),
    )

    if screenshots.interval_seconds_min <= 0 or screenshots.interval_seconds_max <= 0:
        raise ValueError("Screenshot interval values must be > 0")
    if screenshots.interval_seconds_max < screenshots.interval_seconds_min:
        raise ValueError("screenshots.interval_seconds_max must be >= interval_seconds_min")
    if tracking.heartbeat_seconds <= 0:
        raise ValueError("tracking.heartbeat_seconds must be > 0")
    if api.port <= 0:
        raise ValueError("api.port must be > 0")
    if desktop_ui.refresh_interval_seconds <= 0:
        raise ValueError("desktop_ui.refresh_interval_seconds must be > 0")
    if activity.idle_grace_seconds < 0:
        raise ValueError("activity.idle_grace_seconds must be >= 0")
    if monitoring.app_tracking_interval_seconds <= 0:
        raise ValueError("monitoring.app_tracking_interval_seconds must be > 0")
    if sync.interval_seconds <= 0:
        raise ValueError("sync.interval_seconds must be > 0")

    return AppConfig(
        tracking=tracking,
        screenshots=screenshots,
        activity=activity,
        storage=storage,
        api=api,
        desktop_ui=desktop_ui,
        security=security,
        monitoring=monitoring,
        sync=sync,
        app=app,
        source_path=cfg_path,
    )
