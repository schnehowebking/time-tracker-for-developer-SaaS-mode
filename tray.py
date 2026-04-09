from __future__ import annotations

import sys

from desktop.tray_app import launch_tray


if __name__ == "__main__":
    cfg = "config/default_config.yaml"
    if len(sys.argv) > 1:
        cfg = sys.argv[1]
    launch_tray(cfg)
