"""Append-only JSON audit trail for agent-loop activity."""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"
_LOCK = Lock()


def append_record(
    *,
    event: str,
    agent: str | None = None,
    tool_name: str | None = None,
    ticket_id: int | None = None,
    arguments: dict[str, Any] | None = None,
    stop_reason: str | None = None,
) -> None:
    """Append one record to a JSON array without deleting earlier records."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "agent": agent,
        "tool_name": tool_name,
        "ticket_id": ticket_id,
        "arguments": arguments or {},
        "stop_reason": stop_reason,
    }
    encoded = json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        if not AUDIT_PATH.exists():
            AUDIT_PATH.write_bytes(b"[]")
        with AUDIT_PATH.open("r+b") as handle:
            content = handle.read().rstrip()
            if content in (b"", b"[]"):
                handle.seek(0)
                handle.write(b"[" + encoded + b"]")
            elif content.endswith(b"]"):
                handle.seek(len(content) - 1)
                handle.write(b"," + encoded + b"]")
            else:
                raise ValueError("audit_trail.json is not a JSON array")
            handle.truncate()
