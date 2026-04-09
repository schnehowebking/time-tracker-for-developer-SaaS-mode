from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from pynput import keyboard, mouse


@dataclass(slots=True)
class ActivitySnapshot:
    key_events: int
    mouse_events: int
    last_event_ts: float


class ActivityMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._key_events = 0
        self._mouse_events = 0
        self._last_event_ts = time.time()
        self._k_listener: keyboard.Listener | None = None
        self._m_listener: mouse.Listener | None = None

    def start(self) -> None:
        def on_key_press(_: keyboard.Key | keyboard.KeyCode) -> None:
            with self._lock:
                self._key_events += 1
                self._last_event_ts = time.time()

        def on_mouse_move(_: int, __: int) -> None:
            with self._lock:
                self._mouse_events += 1
                self._last_event_ts = time.time()

        def on_mouse_click(_: int, __: int, ___: mouse.Button, ____: bool) -> None:
            with self._lock:
                self._mouse_events += 1
                self._last_event_ts = time.time()

        def on_mouse_scroll(_: int, __: int, ___: int, ____: int) -> None:
            with self._lock:
                self._mouse_events += 1
                self._last_event_ts = time.time()

        self._k_listener = keyboard.Listener(on_press=on_key_press)
        self._m_listener = mouse.Listener(
            on_move=on_mouse_move,
            on_click=on_mouse_click,
            on_scroll=on_mouse_scroll,
        )
        self._k_listener.start()
        self._m_listener.start()

    def stop(self) -> None:
        if self._k_listener:
            self._k_listener.stop()
        if self._m_listener:
            self._m_listener.stop()

    def pop_snapshot(self) -> ActivitySnapshot:
        with self._lock:
            snap = ActivitySnapshot(
                key_events=self._key_events,
                mouse_events=self._mouse_events,
                last_event_ts=self._last_event_ts,
            )
            self._key_events = 0
            self._mouse_events = 0
            return snap
