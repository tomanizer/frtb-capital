"""Runtime configuration and filesystem sandbox for the onboarding mapper.

This module centralises the security-relevant settings for the local onboarding
web service. The tool exposes endpoints that read server-side files and execute
DuckDB SQL, so it must constrain which origins may call it, how large an upload
may be, and which directories file/DuckDB connectors are allowed to touch. All
values are overridable through environment variables so an operator can widen or
narrow the boundary without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# tools/onboarding_mapper/backend/config.py -> repository root is four parents up.
_REPO_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
)


def _split_env(name: str, separator: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(separator) if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Resolved, immutable configuration for one process lifetime.

    Attributes
    ----------
    allowed_origins:
        Browser origins permitted by CORS. ``["*"]`` disables the check and is
        only honoured when explicitly requested via the environment.
    data_roots:
        Absolute directories that ``/api/source/path`` and DuckDB ``attach``
        targets must stay within. Defaults to the repository root so the tool
        operates on repo-relative datasets but cannot read arbitrary host files.
    max_upload_bytes:
        Hard cap on the in-memory upload body, rejecting oversized payloads
        before they are buffered.
    max_sessions:
        Upper bound on retained client sessions; the store evicts least-recently
        used entries beyond this count.
    session_ttl_seconds:
        Idle lifetime after which a session is discarded to release memory.
    """

    allowed_origins: tuple[str, ...]
    data_roots: tuple[Path, ...]
    max_upload_bytes: int
    max_sessions: int
    session_ttl_seconds: float

    def resolve_within_roots(self, candidate: str | os.PathLike[str]) -> Path:
        """Return the resolved path if it lies inside a configured data root.

        Parameters
        ----------
        candidate:
            User-supplied file path from a request body.

        Returns
        -------
        Path
            The resolved, absolute path.

        Raises
        ------
        PermissionError
            If the resolved path escapes every configured data root. The caller
            translates this into an HTTP 403 so a client cannot probe arbitrary
            host files via the path or DuckDB connectors.
        """

        resolved = Path(candidate).expanduser().resolve()
        for root in self.data_roots:
            if resolved == root or root in resolved.parents:
                return resolved
        allowed = ", ".join(str(root) for root in self.data_roots)
        raise PermissionError(f"Path {resolved} is outside the permitted data roots ({allowed})")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build and cache settings from the environment.

    Environment variables
    ---------------------
    FRTB_ONBOARDING_ALLOW_ORIGINS:
        Comma-separated CORS origins, or ``*`` to allow all (not recommended).
    FRTB_ONBOARDING_DATA_ROOTS:
        ``os.pathsep``-separated directories the file/DuckDB connectors may read.
    FRTB_ONBOARDING_MAX_UPLOAD_MB:
        Upload size cap in mebibytes (default 1024).
    FRTB_ONBOARDING_MAX_SESSIONS:
        Maximum retained sessions (default 24).
    FRTB_ONBOARDING_SESSION_TTL_SECONDS:
        Idle session lifetime in seconds (default 3600).
    """

    origins = _split_env("FRTB_ONBOARDING_ALLOW_ORIGINS", ",") or list(_DEFAULT_ALLOWED_ORIGINS)

    configured_roots = _split_env("FRTB_ONBOARDING_DATA_ROOTS", os.pathsep)
    roots = [Path(root).expanduser().resolve() for root in configured_roots] or [_REPO_ROOT]

    max_upload_mb = _positive_int("FRTB_ONBOARDING_MAX_UPLOAD_MB", default=1024)
    max_sessions = _positive_int("FRTB_ONBOARDING_MAX_SESSIONS", default=24)
    session_ttl = _positive_float("FRTB_ONBOARDING_SESSION_TTL_SECONDS", default=3600.0)

    return Settings(
        allowed_origins=tuple(origins),
        data_roots=tuple(roots),
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        max_sessions=max_sessions,
        session_ttl_seconds=session_ttl,
    )


def _positive_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _positive_float(name: str, *, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value
