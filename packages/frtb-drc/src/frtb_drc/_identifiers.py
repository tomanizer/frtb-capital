"""Package-local DRC identifier helpers."""

from __future__ import annotations


def slug(value: str) -> str:
    """Return the standard DRC identifier slug."""

    return value.lower().replace(" ", "-").replace("_", "-")


def slug_path(value: str) -> str:
    """Return a slug for identifiers that may include path-like separators."""

    return slug(value).replace(":", "-").replace("/", "-")


__all__ = ["slug", "slug_path"]
