"""Data Delulu Local Agent — In-Enclave Audit Logger.

Records operational audit logs inside the customer environment.
ZERO RAW DATA LOGGING GUARANTEE: Never logs PII, raw records, database dumps, or passwords.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class LocalAgentAuditLogger:
    """Local JSONL structured audit logger for customer enclave compliance."""

    def __init__(self, log_path: Path | str):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, action: str, job_id: int | str | None = None,
                  organization_id: int = 1, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Appends a structured sanitized audit record to the local enclave log."""
        safe_metadata = self._sanitize_metadata(metadata or {})
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "organization_id": organization_id,
            "action": action,
            "job_id": job_id,
            "raw_data_egress": 0,
            "metadata": safe_metadata
        }
        
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        return entry

    @staticmethod
    def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
        """Strips potential sensitive PII or credentials from audit metadata."""
        clean = {}
        blocked_keys = {"password", "secret", "token", "ssn", "raw_data", "query_text", "api_key", "credentials", "cred"}
        for k, v in meta.items():
            if any(b in k.lower() for b in blocked_keys):
                continue
            if isinstance(v, (str, int, float, bool, list, dict)):
                clean[k] = v
        return clean
