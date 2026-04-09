from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(slots=True)
class SessionRecord:
    id: str
    organization_id: str
    user_id: str
    project_id: str
    started_at: str
    ended_at: str | None
    tracked_seconds: int


@dataclass(slots=True)
class SummaryRecord:
    total_tracked_seconds: int
    total_sessions: int
    total_activity_events: int
    total_screenshots: int
    active_users: int


@dataclass(slots=True)
class OrganizationRecord:
    id: str
    name: str
    created_at: str


@dataclass(slots=True)
class UserRecord:
    id: str
    organization_id: str
    email: str
    full_name: str
    password_hash: str
    role: str
    is_active: bool
    created_at: str


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    tracked_seconds INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    key_events INTEGER NOT NULL,
                    mouse_events INTEGER NOT NULL,
                    idle_seconds INTEGER NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS screenshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    display_index INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS app_activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    inferred_url TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS time_edits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    editor_user_id TEXT NOT NULL,
                    old_tracked_seconds INTEGER NOT NULL,
                    new_tracked_seconds INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    edited_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                );
                """
            )

    def count_users(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return int(row["c"])

    def create_organization(self, name: str) -> OrganizationRecord:
        org = OrganizationRecord(
            id=uuid.uuid4().hex,
            name=name.strip(),
            created_at=datetime.utcnow().isoformat(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO organizations (id, name, created_at) VALUES (?, ?, ?)",
                (org.id, org.name, org.created_at),
            )
        return org

    def create_user(
        self,
        organization_id: str,
        email: str,
        full_name: str,
        password_hash: str,
        role: str = "member",
    ) -> UserRecord:
        user = UserRecord(
            id=uuid.uuid4().hex,
            organization_id=organization_id,
            email=email.strip().lower(),
            full_name=full_name.strip(),
            password_hash=password_hash,
            role=role,
            is_active=True,
            created_at=datetime.utcnow().isoformat(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (id, organization_id, email, full_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.organization_id,
                    user.email,
                    user.full_name,
                    user.password_hash,
                    user.role,
                    1,
                    user.created_at,
                ),
            )
        return user

    def bootstrap_owner(
        self, organization_name: str, owner_name: str, owner_email: str, password_hash: str
    ) -> tuple[OrganizationRecord, UserRecord]:
        org = self.create_organization(organization_name)
        user = self.create_user(
            organization_id=org.id,
            email=owner_email,
            full_name=owner_name,
            password_hash=password_hash,
            role="owner",
        )
        return org, user

    def get_user_by_email(self, email: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, organization_id, email, full_name, password_hash, role, is_active, created_at
                FROM users WHERE email = ?
                """,
                (email.strip().lower(),),
            ).fetchone()
        if not row:
            return None
        return UserRecord(
            id=row["id"],
            organization_id=row["organization_id"],
            email=row["email"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, organization_id, email, full_name, password_hash, role, is_active, created_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return UserRecord(
            id=row["id"],
            organization_id=row["organization_id"],
            email=row["email"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    def list_users(self, organization_id: str) -> list[UserRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, organization_id, email, full_name, password_hash, role, is_active, created_at
                FROM users
                WHERE organization_id = ?
                ORDER BY created_at DESC
                """,
                (organization_id,),
            ).fetchall()
        return [
            UserRecord(
                id=row["id"],
                organization_id=row["organization_id"],
                email=row["email"],
                full_name=row["full_name"],
                password_hash=row["password_hash"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_user_active(self, organization_id: str, user_id: str, is_active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ? AND organization_id = ?",
                (1 if is_active else 0, user_id, organization_id),
            )

    def create_session(self, session_id: str, organization_id: str, user_id: str, project_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, organization_id, user_id, project_id, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, organization_id, user_id, project_id, datetime.utcnow().isoformat()),
            )

    def close_session(self, session_id: str, tracked_seconds: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET ended_at = ?, tracked_seconds = ?
                WHERE id = ?
                """,
                (datetime.utcnow().isoformat(), tracked_seconds, session_id),
            )

    def update_session_tracked_seconds(self, session_id: str, new_seconds: int, editor_user_id: str, reason: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT tracked_seconds FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return False
            old_value = int(row["tracked_seconds"])
            conn.execute(
                "UPDATE sessions SET tracked_seconds = ? WHERE id = ?",
                (max(0, int(new_seconds)), session_id),
            )
            conn.execute(
                """
                INSERT INTO time_edits (
                    session_id, editor_user_id, old_tracked_seconds, new_tracked_seconds, reason, edited_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    editor_user_id,
                    old_value,
                    max(0, int(new_seconds)),
                    reason.strip() or "manual edit",
                    datetime.utcnow().isoformat(),
                ),
            )
        return True

    def list_time_edits(self, organization_id: str, limit: int = 100) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT te.id, te.session_id, te.editor_user_id, te.old_tracked_seconds, te.new_tracked_seconds,
                       te.reason, te.edited_at
                FROM time_edits te
                JOIN sessions s ON s.id = te.session_id
                WHERE s.organization_id = ?
                ORDER BY te.edited_at DESC
                LIMIT ?
                """,
                (organization_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_activity(
        self,
        session_id: str,
        key_events: int,
        mouse_events: int,
        idle_seconds: int,
    ) -> None:
        payload = {
            "session_id": session_id,
            "key_events": int(key_events),
            "mouse_events": int(mouse_events),
            "idle_seconds": int(idle_seconds),
        }
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO activity_logs (session_id, ts, key_events, mouse_events, idle_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, now, key_events, mouse_events, idle_seconds),
            )
            conn.execute(
                "INSERT INTO sync_queue (event_type, event_data, created_at) VALUES (?, ?, ?)",
                ("activity", json.dumps(payload), now),
            )

    def add_app_activity(self, session_id: str, app_name: str, window_title: str, inferred_url: str | None) -> None:
        payload = {
            "session_id": session_id,
            "app_name": app_name,
            "window_title": window_title,
            "inferred_url": inferred_url,
        }
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_activity_logs (session_id, ts, app_name, window_title, inferred_url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, now, app_name, window_title, inferred_url),
            )
            conn.execute(
                "INSERT INTO sync_queue (event_type, event_data, created_at) VALUES (?, ?, ?)",
                ("app_activity", json.dumps(payload), now),
            )

    def add_screenshot(self, session_id: str, display_index: int, file_path: Path) -> None:
        payload = {
            "session_id": session_id,
            "display_index": int(display_index),
            "file_path": str(file_path),
        }
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO screenshots (session_id, ts, display_index, file_path)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, now, display_index, str(file_path)),
            )
            conn.execute(
                "INSERT INTO sync_queue (event_type, event_data, created_at) VALUES (?, ?, ?)",
                ("screenshot", json.dumps(payload), now),
            )

    def enqueue_sync_event(self, event_type: str, event_data: dict[str, object]) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sync_queue (event_type, event_data, created_at) VALUES (?, ?, ?)",
                (event_type, json.dumps(event_data), now),
            )

    def fetch_pending_sync_events(self, limit: int = 100) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, event_data, created_at
                FROM sync_queue
                WHERE sent_at IS NULL
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return rows

    def mark_sync_events_sent(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        params: tuple[object, ...] = (datetime.utcnow().isoformat(), *ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE sync_queue SET sent_at = ? WHERE id IN ({placeholders})",
                params,
            )

    def get_app_usage(self, days: int = 7, organization_id: str | None = None, limit: int = 20) -> list[dict[str, object]]:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        if organization_id:
            query = """
                SELECT aal.app_name, COUNT(*) AS entries
                FROM app_activity_logs aal
                JOIN sessions s ON s.id = aal.session_id
                WHERE aal.ts >= ? AND s.organization_id = ?
                GROUP BY aal.app_name
                ORDER BY entries DESC
                LIMIT ?
            """
            params: tuple[object, ...] = (since, organization_id, limit)
        else:
            query = """
                SELECT app_name, COUNT(*) AS entries
                FROM app_activity_logs
                WHERE ts >= ?
                GROUP BY app_name
                ORDER BY entries DESC
                LIMIT ?
            """
            params = (since, limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"app_name": row["app_name"], "entries": int(row["entries"])} for row in rows]

    def get_latest_open_session(self) -> SessionRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, organization_id, user_id, project_id, started_at, ended_at, tracked_seconds
                FROM sessions
                WHERE ended_at IS NULL
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return SessionRecord(
            id=row["id"],
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            tracked_seconds=row["tracked_seconds"],
        )

    def list_sessions(self, limit: int = 100, organization_id: str | None = None) -> list[SessionRecord]:
        if organization_id:
            query = """
                SELECT id, organization_id, user_id, project_id, started_at, ended_at, tracked_seconds
                FROM sessions
                WHERE organization_id = ?
                ORDER BY started_at DESC
                LIMIT ?
            """
            params: tuple[object, ...] = (organization_id, limit)
        else:
            query = """
                SELECT id, organization_id, user_id, project_id, started_at, ended_at, tracked_seconds
                FROM sessions
                ORDER BY started_at DESC
                LIMIT ?
            """
            params = (limit,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            SessionRecord(
                id=row["id"],
                organization_id=row["organization_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                tracked_seconds=row["tracked_seconds"],
            )
            for row in rows
        ]

    def get_summary(self, days: int = 7, organization_id: str | None = None) -> SummaryRecord:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        org_clause = " AND s.organization_id = ?" if organization_id else ""
        params = [since]
        if organization_id:
            params.append(organization_id)

        with self._connect() as conn:
            session_row = conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(s.tracked_seconds), 0) AS tracked,
                    COUNT(*) AS sessions,
                    COUNT(DISTINCT s.user_id) AS active_users
                FROM sessions s
                WHERE s.started_at >= ?{org_clause}
                """,
                tuple(params),
            ).fetchone()

            activity_query = """
                SELECT COALESCE(SUM(a.key_events + a.mouse_events), 0) AS events
                FROM activity_logs a
                JOIN sessions s ON s.id = a.session_id
                WHERE a.ts >= ?
            """
            screenshot_query = """
                SELECT COUNT(*) AS screenshots
                FROM screenshots sc
                JOIN sessions s ON s.id = sc.session_id
                WHERE sc.ts >= ?
            """
            act_params = [since]
            sc_params = [since]
            if organization_id:
                activity_query += " AND s.organization_id = ?"
                screenshot_query += " AND s.organization_id = ?"
                act_params.append(organization_id)
                sc_params.append(organization_id)

            activity_row = conn.execute(activity_query, tuple(act_params)).fetchone()
            screenshot_row = conn.execute(screenshot_query, tuple(sc_params)).fetchone()

        return SummaryRecord(
            total_tracked_seconds=int(session_row["tracked"]),
            total_sessions=int(session_row["sessions"]),
            total_activity_events=int(activity_row["events"]),
            total_screenshots=int(screenshot_row["screenshots"]),
            active_users=int(session_row["active_users"]),
        )

    def get_daily_tracked(self, days: int = 14, organization_id: str | None = None) -> list[dict[str, int | str]]:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        if organization_id:
            query = """
                SELECT substr(started_at, 1, 10) AS day, COALESCE(SUM(tracked_seconds), 0) AS tracked
                FROM sessions
                WHERE started_at >= ? AND organization_id = ?
                GROUP BY day
                ORDER BY day ASC
            """
            params: tuple[object, ...] = (since, organization_id)
        else:
            query = """
                SELECT substr(started_at, 1, 10) AS day, COALESCE(SUM(tracked_seconds), 0) AS tracked
                FROM sessions
                WHERE started_at >= ?
                GROUP BY day
                ORDER BY day ASC
            """
            params = (since,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"day": row["day"], "tracked_seconds": int(row["tracked"])} for row in rows]

    def get_project_breakdown(
        self,
        days: int = 7,
        limit: int = 10,
        organization_id: str | None = None,
    ) -> list[dict[str, int | str]]:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        if organization_id:
            query = """
                SELECT project_id, COALESCE(SUM(tracked_seconds), 0) AS tracked
                FROM sessions
                WHERE started_at >= ? AND organization_id = ?
                GROUP BY project_id
                ORDER BY tracked DESC
                LIMIT ?
            """
            params: tuple[object, ...] = (since, organization_id, limit)
        else:
            query = """
                SELECT project_id, COALESCE(SUM(tracked_seconds), 0) AS tracked
                FROM sessions
                WHERE started_at >= ?
                GROUP BY project_id
                ORDER BY tracked DESC
                LIMIT ?
            """
            params = (since, limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"project_id": row["project_id"], "tracked_seconds": int(row["tracked"])} for row in rows]
