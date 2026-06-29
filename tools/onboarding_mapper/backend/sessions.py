"""In-memory session store for uploaded client datasets."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]


@dataclass
class ClientSession:
    table: pa.Table
    source_name: str
    source_kind: str
    source_meta: dict[str, Any] = field(default_factory=dict)
    raw_bytes: bytes | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}

    def create(
        self,
        table: pa.Table,
        *,
        source_name: str,
        source_kind: str,
        source_meta: dict[str, Any] | None = None,
        raw_bytes: bytes | None = None,
    ) -> str:
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = ClientSession(
            table=table,
            source_name=source_name,
            source_kind=source_kind,
            source_meta=source_meta or {},
            raw_bytes=raw_bytes,
        )
        return session_id

    def get(self, session_id: str) -> ClientSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session {session_id}") from exc

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


SESSIONS = SessionStore()
