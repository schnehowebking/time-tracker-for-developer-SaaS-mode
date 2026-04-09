from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tracker.config import AppConfig
from tracker.runtime import process_is_running, read_pid, read_state, request_stop
from tracker.storage import Storage


def _app_entry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "app.py"


def _command_base() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(_app_entry_path())]


def _spawn_detached(cmd: list[str]) -> int:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    return proc.pid


def tracker_status(cfg: AppConfig) -> dict[str, Any]:
    storage = Storage(cfg.db_path)
    pid = read_pid(cfg.pid_file_path)
    running = bool(pid and process_is_running(pid))
    state = read_state(cfg.runtime_state_path)
    session = storage.get_latest_open_session()
    return {
        "running": running,
        "running_pid": pid,
        "state": state,
        "open_session": asdict(session) if session else None,
    }


def start_tracker(cfg: AppConfig, config_path: str | Path) -> dict[str, Any]:
    status = tracker_status(cfg)
    if status["running"]:
        return {"ok": False, "message": f"Tracker already running (PID {status['running_pid']})"}
    cmd = _command_base() + ["--config", str(Path(config_path).resolve()), "run"]
    pid = _spawn_detached(cmd)
    return {"ok": True, "message": f"Tracker start requested (PID {pid})"}


def stop_tracker(cfg: AppConfig) -> dict[str, Any]:
    pid = read_pid(cfg.pid_file_path)
    if not pid:
        return {"ok": False, "message": "Tracker is not running (no PID file)."}
    if not process_is_running(pid):
        return {"ok": False, "message": f"Tracker PID file exists but process {pid} is not running."}
    request_stop(pid)
    return {"ok": True, "message": f"Stop signal sent to PID {pid}."}
