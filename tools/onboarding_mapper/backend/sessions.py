"""In-memory session store for uploaded client datasets.

Sessions hold the loaded Arrow table (and, for uploads, the raw bytes used for
source-content hashing) between API calls. Because the table and bytes can be
large, the store bounds memory by evicting least-recently-used sessions beyond a
configured cap and discarding sessions that have been idle past a TTL.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]

from tools.onboarding_mapper.backend.config import Settings, get_settings


@dataclass
class ClientSession:
    table: pa.Table
    source_name: str
    source_kind: str
    source_meta: dict[str, Any] = field(default_factory=dict)
    raw_bytes: bytes | None = None
    last_access: float = field(default_factory=time.monotonic)


class SessionStore:
    """Bounded, TTL-evicting store keyed by opaque session id.

    Access is guarded by a lock: FastAPI dispatches the synchronous source and
    mapping endpoints to a worker threadpool, so concurrent requests can mutate
    the ordering structure from different threads. The lock keeps the eviction
    bookkeeping (``move_to_end`` / ``popitem``) consistent.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._sessions: OrderedDict[str, ClientSession] = OrderedDict()
        self._lock = threading.Lock()

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
        with self._lock:
            self._evict_expired()
            self._sessions[session_id] = ClientSession(
                table=table,
                source_name=source_name,
                source_kind=source_kind,
                source_meta=source_meta or {},
                raw_bytes=raw_bytes,
            )
            self._sessions.move_to_end(session_id)
            self._evict_overflow()
        return session_id

    def get(self, session_id: str) -> ClientSession:
        with self._lock:
            self._evict_expired()
            try:
                session = self._sessions[session_id]
            except KeyError as exc:
                raise KeyError(f"Unknown or expired session {session_id}") from exc
            session.last_access = time.monotonic()
            self._sessions.move_to_end(session_id)
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _evict_expired(self) -> None:
        ttl = self._settings.session_ttl_seconds
        cutoff = time.monotonic() - ttl
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.last_access < cutoff
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def _evict_overflow(self) -> None:
        while len(self._sessions) > self._settings.max_sessions:
            self._sessions.popitem(last=False)


SESSIONS = SessionStore()
