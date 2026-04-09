from __future__ import annotations

import random
import signal
import threading
import time
import uuid
from datetime import datetime, timezone

from tracker.activity import ActivityMonitor
from tracker.config import AppConfig
from tracker.runtime import RuntimeState, remove_pid, write_pid, write_state
from tracker.screenshot import ScreenshotCapture
from tracker.storage import Storage
from tracker.sync import SyncClient
from tracker.window_activity import WindowActivityTracker


class TrackerEngine:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.storage = Storage(cfg.db_path)
        self.activity = ActivityMonitor() if cfg.activity.enabled else None
        self.window_tracker = (
            WindowActivityTracker(cfg.monitoring.infer_browser_url_from_title)
            if cfg.monitoring.app_tracking_enabled
            else None
        )
        self.shot = ScreenshotCapture(cfg.screenshot_dir, cfg.screenshots.image_format)
        self.sync_client = SyncClient(cfg, self.storage)
        self.session_id = uuid.uuid4().hex
        self.tracked_seconds = 0
        self._running = False
        self._last_screenshot_utc: str | None = None
        self._stop_event = threading.Event()

    def _setup_signal_handlers(self) -> None:
        def _handle(_: int, __: object) -> None:
            self._stop_event.set()

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)

    def run(self) -> None:
        self.cfg.base_dir.mkdir(parents=True, exist_ok=True)
        self.cfg.screenshot_dir.mkdir(parents=True, exist_ok=True)
        write_pid(self.cfg.pid_file_path, pid=self._pid)
        self._setup_signal_handlers()

        self.storage.create_session(
            session_id=self.session_id,
            organization_id=self.cfg.app.organization_id,
            user_id=self.cfg.app.user_id,
            project_id=self.cfg.app.project_id,
        )

        if self.activity:
            self.activity.start()

        self._running = True
        next_screenshot_at = time.time() + self._next_screenshot_delay()
        next_window_activity_at = time.time()
        next_sync_at = time.time() + self.cfg.sync.interval_seconds

        while not self._stop_event.is_set():
            loop_started = time.time()
            now = time.time()

            idle_seconds = 0
            key_events = 0
            mouse_events = 0
            if self.activity:
                snap = self.activity.pop_snapshot()
                key_events = snap.key_events
                mouse_events = snap.mouse_events
                idle_seconds = int(max(0, now - snap.last_event_ts))

            idle_limit = self.cfg.activity.idle_threshold_seconds + self.cfg.activity.idle_grace_seconds
            if self.activity and idle_seconds >= idle_limit and self.cfg.activity.auto_pause_on_idle:
                delta_tracked = 0
            else:
                delta_tracked = self.cfg.tracking.heartbeat_seconds
                self.tracked_seconds += delta_tracked

            self.storage.add_activity(
                session_id=self.session_id,
                key_events=key_events,
                mouse_events=mouse_events,
                idle_seconds=idle_seconds,
            )
            self.storage.enqueue_sync_event(
                "heartbeat",
                {
                    "session_id": self.session_id,
                    "tracked_seconds": self.tracked_seconds,
                    "delta_tracked_seconds": delta_tracked,
                    "idle_seconds": idle_seconds,
                },
            )

            if self.cfg.screenshots.enabled and now >= next_screenshot_at:
                paths = self.shot.capture(
                    session_id=self.session_id,
                    capture_all_displays=self.cfg.screenshots.capture_all_displays,
                )
                for idx, p in enumerate(paths, start=1):
                    self.storage.add_screenshot(self.session_id, idx, p)
                self._last_screenshot_utc = datetime.now(timezone.utc).isoformat()
                next_screenshot_at = time.time() + self._next_screenshot_delay()

            if self.window_tracker and now >= next_window_activity_at:
                snap = self.window_tracker.get_snapshot()
                self.storage.add_app_activity(
                    session_id=self.session_id,
                    app_name=snap.app_name,
                    window_title=snap.window_title,
                    inferred_url=snap.inferred_url,
                )
                next_window_activity_at = time.time() + self.cfg.monitoring.app_tracking_interval_seconds

            if now >= next_sync_at:
                self.sync_client.sync_pending(batch_size=200)
                next_sync_at = time.time() + self.cfg.sync.interval_seconds

            self._write_runtime_state()

            elapsed = time.time() - loop_started
            sleep_for = max(0.1, self.cfg.tracking.heartbeat_seconds - elapsed)
            self._stop_event.wait(timeout=sleep_for)

        self._shutdown()

    @property
    def _pid(self) -> int:
        import os

        return os.getpid()

    def _next_screenshot_delay(self) -> int:
        return random.randint(
            self.cfg.screenshots.interval_seconds_min,
            self.cfg.screenshots.interval_seconds_max,
        )

    def _write_runtime_state(self) -> None:
        write_state(
            self.cfg.runtime_state_path,
            RuntimeState(
                pid=self._pid,
                session_id=self.session_id,
                running=self._running,
                tracked_seconds=self.tracked_seconds,
                last_heartbeat_utc=datetime.now(timezone.utc).isoformat(),
                last_screenshot_utc=self._last_screenshot_utc,
            ),
        )

    def _shutdown(self) -> None:
        self._running = False
        if self.activity:
            self.activity.stop()
        self.sync_client.sync_pending(batch_size=500)
        self.storage.close_session(self.session_id, tracked_seconds=self.tracked_seconds)
        self._write_runtime_state()
        remove_pid(self.cfg.pid_file_path)
