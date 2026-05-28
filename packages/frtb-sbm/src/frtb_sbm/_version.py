"""Package version sourced from installed package metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("frtb-sbm")
except PackageNotFoundError:  # pragma: no cover - source tree fallback outside installed envs
    __version__ = "0.0.0+unknown"
