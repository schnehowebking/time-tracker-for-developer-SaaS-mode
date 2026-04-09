from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import mss
import mss.tools


class ScreenshotCapture:
    def __init__(self, output_root: Path, image_format: str = "png") -> None:
        self.output_root = output_root
        self.image_format = image_format.lower()

    def capture(
        self,
        session_id: str,
        capture_all_displays: bool = True,
    ) -> list[Path]:
        now = datetime.now()
        date_dir = self.output_root / now.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        with mss.mss() as sct:
            monitors: Iterable[dict[str, int]]
            if len(sct.monitors) <= 1:
                return created
            if capture_all_displays:
                monitors = sct.monitors[1:]
            else:
                monitors = [sct.monitors[1]]

            for index, mon in enumerate(monitors, start=1):
                raw = sct.grab(mon)
                filename = (
                    f"{session_id}_{now.strftime('%H%M%S')}_display{index}.{self.image_format}"
                )
                target = date_dir / filename
                mss.tools.to_png(raw.rgb, raw.size, output=str(target))
                created.append(target)

        return created
