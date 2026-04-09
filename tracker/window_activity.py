from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class WindowActivitySnapshot:
    ts: str
    app_name: str
    window_title: str
    inferred_url: str | None


def _infer_url_from_title(title: str) -> str | None:
    lowered = title.lower()
    if "http://" in lowered or "https://" in lowered:
        marker = lowered.find("http://")
        if marker == -1:
            marker = lowered.find("https://")
        return title[marker:].split()[0]
    if " - google chrome" in lowered or " - microsoft edge" in lowered or " - mozilla firefox" in lowered:
        return f"title://{title.strip()}"
    return None


class WindowActivityTracker:
    def __init__(self, infer_browser_url_from_title: bool = True) -> None:
        self._infer = infer_browser_url_from_title

    def _read_windows(self) -> tuple[str, str]:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown", "unknown"

        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value or "unknown"

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        app = f"pid:{int(pid.value)}"
        return app, title

    def _read_linux(self) -> tuple[str, str]:
        try:
            win_id = (
                subprocess.check_output(["xprop", "-root", "_NET_ACTIVE_WINDOW"], text=True).strip().split()[-1]
            )
            win_props = subprocess.check_output(["xprop", "-id", win_id], text=True)
            title = "unknown"
            app = "unknown"
            for line in win_props.splitlines():
                if "WM_NAME(" in line or "_NET_WM_NAME(" in line:
                    title = line.split("=", 1)[-1].strip().strip('"')
                if "WM_CLASS(" in line:
                    cls = line.split("=", 1)[-1].strip()
                    app = cls.split(",")[-1].strip().strip('"')
            return app or "unknown", title or "unknown"
        except Exception:
            return "unknown", "unknown"

    def get_snapshot(self) -> WindowActivitySnapshot:
        system = platform.system().lower()
        if "windows" in system:
            app_name, title = self._read_windows()
        elif "linux" in system:
            app_name, title = self._read_linux()
        else:
            app_name, title = "unsupported-os", "unknown"
        inferred_url = _infer_url_from_title(title) if self._infer else None
        return WindowActivitySnapshot(
            ts=datetime.utcnow().isoformat(),
            app_name=app_name,
            window_title=title[:500],
            inferred_url=inferred_url,
        )
