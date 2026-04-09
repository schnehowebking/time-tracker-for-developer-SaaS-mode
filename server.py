from __future__ import annotations

import sys

from app import cmd_server


if __name__ == "__main__":
    config = "config/default_config.yaml"
    if len(sys.argv) > 1:
        config = sys.argv[1]
    raise SystemExit(cmd_server(config))
