"""Package-local DRC citation helpers."""

from __future__ import annotations


def merge_citations(*citation_groups: tuple[str, ...]) -> tuple[str, ...]:
    """Merge citation groups while preserving first-seen order.
    Parameters
    ----------
    *citation_groups : tuple[str, ...]

    Returns
    -------
    tuple[str, ...]
        Citation ids merged without duplicates while preserving first-seen order.
    """

    merged: list[str] = []
    seen: set[str] = set()
    for group in citation_groups:
        for citation_id in group:
            if citation_id in seen:
                continue
            seen.add(citation_id)
            merged.append(citation_id)
    return tuple(merged)


__all__ = ["merge_citations"]
