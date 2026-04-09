from __future__ import annotations

import argparse
import json
import os
import sys

from tracker.config import load_config
from tracker.service import start_tracker, stop_tracker, tracker_status


def cmd_run(config_path: str) -> int:
    from tracker.engine import TrackerEngine

    cfg = load_config(config_path)
    status = tracker_status(cfg)
    if status["running"]:
        print(f"Tracker already running with PID {status['running_pid']}.")
        return 1
    engine = TrackerEngine(cfg)
    print("Tracker started. Press Ctrl+C to stop.")
    engine.run()
    print("Tracker stopped.")
    return 0


def cmd_status(config_path: str) -> int:
    cfg = load_config(config_path)
    print(json.dumps(tracker_status(cfg), indent=2))
    return 0


def cmd_stop(config_path: str) -> int:
    cfg = load_config(config_path)
    result = stop_tracker(cfg)
    print(result["message"])
    return 0 if result["ok"] else 1


def cmd_start(config_path: str) -> int:
    cfg = load_config(config_path)
    result = start_tracker(cfg, config_path=config_path)
    print(result["message"])
    return 0 if result["ok"] else 1


def cmd_server(config_path: str) -> int:
    cfg = load_config(config_path)
    os.environ["TRACKER_CONFIG_PATH"] = str(cfg.source_path)
    import uvicorn

    uvicorn.run("backend.api:create_app", factory=True, host=cfg.api.host, port=cfg.api.port)
    return 0


def cmd_tray(config_path: str) -> int:
    from desktop.tray_app import launch_tray

    launch_tray(config_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configurable desktop time tracker")
    parser.add_argument(
        "--config",
        default="config/default_config.yaml",
        help="Path to config YAML",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="Run tracker in foreground")
    sub.add_parser("start", help="Start tracker in background")
    sub.add_parser("status", help="Show current runtime status")
    sub.add_parser("stop", help="Request graceful stop")
    sub.add_parser("server", help="Run backend API + dashboard")
    sub.add_parser("tray", help="Run desktop tray UI")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "run":
        return cmd_run(args.config)
    if args.cmd == "start":
        return cmd_start(args.config)
    if args.cmd == "status":
        return cmd_status(args.config)
    if args.cmd == "stop":
        return cmd_stop(args.config)
    if args.cmd == "server":
        return cmd_server(args.config)
    if args.cmd == "tray":
        return cmd_tray(args.config)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
