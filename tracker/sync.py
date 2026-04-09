from __future__ import annotations

import json
from typing import Any

import requests

from tracker.config import AppConfig
from tracker.storage import Storage


class SyncClient:
    def __init__(self, cfg: AppConfig, storage: Storage) -> None:
        self.cfg = cfg
        self.storage = storage

    def sync_pending(self, batch_size: int = 100) -> dict[str, Any]:
        if not self.cfg.sync.enabled:
            return {"ok": False, "sent": 0, "message": "sync disabled"}

        pending = self.storage.fetch_pending_sync_events(limit=batch_size)
        if not pending:
            return {"ok": True, "sent": 0, "message": "nothing to sync"}

        payload = {
            "events": [
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "event_data": json.loads(row["event_data"]),
                    "created_at": row["created_at"],
                }
                for row in pending
            ]
        }
        headers = {
            "X-Agent-Key": self.cfg.security.agent_ingest_key,
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                self.cfg.sync.endpoint_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=8,
            )
            resp.raise_for_status()
        except Exception as exc:
            return {"ok": False, "sent": 0, "message": f"sync failed: {exc}"}

        ids = [int(item["id"]) for item in pending]
        self.storage.mark_sync_events_sent(ids)
        return {"ok": True, "sent": len(ids), "message": "ok"}
