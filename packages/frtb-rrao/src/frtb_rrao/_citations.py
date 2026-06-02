"""Package-local citation merge helpers for RRAO."""

from __future__ import annotations


def merged_citation_ids(*citation_groups: tuple[str, ...]) -> tuple[str, ...]:
    """Merge citation groups while preserving first-seen order."""

    merged: list[str] = []
    seen: set[str] = set()
    for group in citation_groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


__all__ = ["merged_citation_ids"]
