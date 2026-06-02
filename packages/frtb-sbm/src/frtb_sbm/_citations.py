"""Package-local citation helpers for SBM."""

from __future__ import annotations

from collections.abc import Iterable


def merge_citation_groups(groups: Iterable[Iterable[str]]) -> tuple[str, ...]:
    """Return citation ids from an iterable of citation groups."""

    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


def merge_citation_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Return citation ids in first-seen order with duplicates removed."""

    return merge_citation_groups(groups)
