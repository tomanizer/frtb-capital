"""Package-local citation helpers for CVA result assembly."""

from __future__ import annotations


def merge_citations(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Return citation ids in first-seen order with duplicates removed.

    Parameters
    ----------
    *groups : tuple[str, ...]
        Citation id tuples merged in argument order.

    Returns
    -------
    tuple[str, ...]
        De-duplicated citation ids preserving first-seen order for audit output.
    """

    citation_ids: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                citation_ids.append(citation_id)
                seen.add(citation_id)
    return tuple(citation_ids)
