# Time Tracker Suite

Hubstaff-style configurable time tracking software for Windows and Linux.

## Features

- Time tracking with heartbeat updates
- Keyboard/mouse activity logging
- Automatic screenshots at random intervals
- Active app/window tracking (Windows/Linux)
- Idle auto-pause behavior with grace period
- Offline sync queue + agent sync endpoint
- Manual time edits with audit trail
- Desktop tray app with settings panel
- SaaS-style web app with login/register, organizations, and user management
- FastAPI backend with tenant-aware admin dashboard
- Local SQLite storage
- Build scripts for Windows and Linux packaging

## Project Structure

- `app.py` - main CLI entry
- `tracker/` - core tracking engine and storage
- `desktop/tray_app.py` - system tray desktop UI
- `backend/api.py` - backend API and dashboard server
- `config/default_config.yaml` - app configuration
- `build/windows/` - Windows build + installer spec
- `build/linux/` - Linux build + packaging scripts

## Requirements

- Python 3.11+
- Desktop session for screenshot/input capture

## Installation

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run tracker foreground:

```bash
python app.py run
```

Start tracker background:

```bash
python app.py start
```

Check status:

```bash
python app.py status
```

Stop tracker:

```bash
python app.py stop
```

Run backend server and dashboard:

```bash
python app.py server
```

Run desktop tray UI:

```bash
python app.py tray
```

Dashboard default URL:

- `http://127.0.0.1:8000/`

## SaaS Flow

1. Open `http://127.0.0.1:8000/auth/register`
2. Create your organization + owner account
3. Login at `/auth/login`
4. Manage team users at `/users` (owner/admin only)
5. View tenant dashboard at `/`
6. Edit session tracked time from dashboard (owner/admin)

## API Endpoints

- `GET /health`
- `GET /auth/register`
- `POST /auth/register`
- `GET /auth/login`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /api/status`
- `POST /api/tracker/start`
- `POST /api/tracker/stop`
- `POST /api/agent/sync` (agent ingest, secured by `X-Agent-Key`)
- `GET /api/sessions?limit=100`
- `GET /api/summary?days=7`

## Configuration

Edit `config/default_config.yaml`:

- `tracking.heartbeat_seconds`
- `screenshots.enabled`
- `screenshots.interval_seconds_min`
- `screenshots.interval_seconds_max`
- `activity.idle_threshold_seconds`
- `activity.auto_pause_on_idle`
- `activity.idle_grace_seconds`
- `api.host`
- `api.port`
- `desktop_ui.refresh_interval_seconds`
- `security.secret_key`
- `security.cookie_name`
- `security.agent_ingest_key`
- `monitoring.app_tracking_enabled`
- `monitoring.app_tracking_interval_seconds`
- `monitoring.infer_browser_url_from_title`
- `sync.enabled`
- `sync.endpoint_url`
- `sync.interval_seconds`
- `app.organization_id`
- `app.user_id`
- `app.project_id`

## Build and Packaging

Windows build:

```powershell
powershell -ExecutionPolicy Bypass -File build\windows\build.ps1
```

Optional installer:

- Open `build/windows/installer.iss` with Inno Setup Compiler and build installer.

Linux build:

```bash
bash build/linux/build.sh
bash build/linux/package.sh
```

Artifacts are generated under `dist/`.

## Local Data Paths

- SQLite database: `data/tracker.db`
- Screenshots: `data/screenshots/`
- Runtime state: `data/runtime_state.json`
- PID file: `data/tracker.pid`
