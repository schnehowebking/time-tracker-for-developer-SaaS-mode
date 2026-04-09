from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from tracker.config import AppConfig, load_config, save_config
from tracker.service import start_tracker, stop_tracker, tracker_status


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Time Tracker Settings")
        self.setMinimumWidth(380)

        form = QFormLayout()
        self.heartbeat = QSpinBox()
        self.heartbeat.setRange(1, 3600)
        self.heartbeat.setValue(cfg.tracking.heartbeat_seconds)
        form.addRow("Heartbeat (sec)", self.heartbeat)

        self.idle_threshold = QSpinBox()
        self.idle_threshold.setRange(5, 7200)
        self.idle_threshold.setValue(cfg.activity.idle_threshold_seconds)
        form.addRow("Idle Threshold (sec)", self.idle_threshold)

        self.auto_pause_idle = QCheckBox("Auto Pause On Idle")
        self.auto_pause_idle.setChecked(cfg.activity.auto_pause_on_idle)
        form.addRow(self.auto_pause_idle)

        self.shots_enabled = QCheckBox("Enable Screenshots")
        self.shots_enabled.setChecked(cfg.screenshots.enabled)
        form.addRow(self.shots_enabled)

        self.interval_min = QSpinBox()
        self.interval_min.setRange(5, 3600)
        self.interval_min.setValue(cfg.screenshots.interval_seconds_min)
        form.addRow("Screenshot Min (sec)", self.interval_min)

        self.interval_max = QSpinBox()
        self.interval_max.setRange(5, 7200)
        self.interval_max.setValue(cfg.screenshots.interval_seconds_max)
        form.addRow("Screenshot Max (sec)", self.interval_max)

        self.user_id = QLineEdit(cfg.app.user_id)
        form.addRow("User ID", self.user_id)
        self.project_id = QLineEdit(cfg.app.project_id)
        form.addRow("Project ID", self.project_id)

        self.api_host = QLineEdit(cfg.api.host)
        form.addRow("API Host", self.api_host)
        self.api_port = QSpinBox()
        self.api_port.setRange(1, 65535)
        self.api_port.setValue(cfg.api.port)
        form.addRow("API Port", self.api_port)

        self.sync_enabled = QCheckBox("Enable Sync")
        self.sync_enabled.setChecked(cfg.sync.enabled)
        form.addRow(self.sync_enabled)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(buttons)
        self.setLayout(root)

    def apply(self) -> None:
        self.cfg.tracking.heartbeat_seconds = int(self.heartbeat.value())
        self.cfg.activity.idle_threshold_seconds = int(self.idle_threshold.value())
        self.cfg.activity.auto_pause_on_idle = bool(self.auto_pause_idle.isChecked())
        self.cfg.screenshots.enabled = bool(self.shots_enabled.isChecked())
        self.cfg.screenshots.interval_seconds_min = int(self.interval_min.value())
        self.cfg.screenshots.interval_seconds_max = int(self.interval_max.value())
        self.cfg.app.user_id = self.user_id.text().strip() or self.cfg.app.user_id
        self.cfg.app.project_id = self.project_id.text().strip() or self.cfg.app.project_id
        self.cfg.api.host = self.api_host.text().strip() or "127.0.0.1"
        self.cfg.api.port = int(self.api_port.value())
        self.cfg.sync.enabled = bool(self.sync_enabled.isChecked())
        save_config(self.cfg)


class TrayController(QMainWindow):
    def __init__(self, config_path: str | Path) -> None:
        super().__init__()
        self.config_path = Path(config_path).resolve()
        self.cfg = load_config(self.config_path)
        self.setWindowTitle("Time Tracker")
        self.setMinimumSize(360, 180)

        central = QWidget()
        layout = QVBoxLayout()
        self.status_label = QLabel("Loading status...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip("Time Tracker")

        menu = self.tray.contextMenu() or self._build_menu()
        self.tray.setContextMenu(menu)
        self.tray.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(self.cfg.desktop_ui.refresh_interval_seconds * 1000)
        self.refresh_status()

    def _build_menu(self):
        from PySide6.QtWidgets import QMenu

        menu = QMenu()
        act_start = QAction("Start Tracking", self)
        act_stop = QAction("Stop Tracking", self)
        act_dashboard = QAction("Open Dashboard", self)
        act_settings = QAction("Settings", self)
        act_show = QAction("Show Window", self)
        act_quit = QAction("Quit", self)

        act_start.triggered.connect(self.start_tracking)
        act_stop.triggered.connect(self.stop_tracking)
        act_dashboard.triggered.connect(self.open_dashboard)
        act_settings.triggered.connect(self.open_settings)
        act_show.triggered.connect(self.showNormal)
        act_quit.triggered.connect(self.quit_app)

        menu.addAction(act_start)
        menu.addAction(act_stop)
        menu.addAction(act_dashboard)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_show)
        menu.addAction(act_quit)
        return menu

    def refresh_status(self) -> None:
        status = tracker_status(self.cfg)
        running = status["running"]
        session = status["open_session"]
        txt = "Running" if running else "Stopped"
        sid = session["id"][:8] if session else "-"
        tracked = status["state"]["tracked_seconds"] if status.get("state") else 0
        self.status_label.setText(f"Status: {txt}\nSession: {sid}\nTracked seconds: {tracked}")
        self.tray.setToolTip(f"Time Tracker: {txt}")

    def start_tracking(self) -> None:
        result = start_tracker(self.cfg, self.config_path)
        self.tray.showMessage("Time Tracker", result["message"])
        self.refresh_status()

    def stop_tracking(self) -> None:
        result = stop_tracker(self.cfg)
        self.tray.showMessage("Time Tracker", result["message"])
        self.refresh_status()

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            try:
                dlg.apply()
                self.cfg = load_config(self.config_path)
                self.timer.start(self.cfg.desktop_ui.refresh_interval_seconds * 1000)
                self.tray.showMessage("Time Tracker", "Settings saved.")
            except Exception as exc:
                QMessageBox.critical(self, "Settings Error", str(exc))
        self.refresh_status()

    def open_dashboard(self) -> None:
        url = f"http://{self.cfg.api.host}:{self.cfg.api.port}/"
        webbrowser.open(url)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()
        self.hide()
        self.tray.showMessage("Time Tracker", "Running in system tray.")

    def quit_app(self) -> None:
        self.tray.hide()
        QApplication.quit()


def launch_tray(config_path: str | Path) -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = TrayController(config_path=config_path)
    controller.show()
    sys.exit(app.exec())
