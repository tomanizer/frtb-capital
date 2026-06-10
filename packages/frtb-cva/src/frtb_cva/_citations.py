"""Package-local citation helpers for CVA result assembly."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class _CitedLine(Protocol):
    @property
    def citations(self) -> tuple[str, ...]:
        """Citation ids carried by a BA-CVA standalone line."""
        ...


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


def collect_ba_citations(
    reduced_citations: tuple[str, ...],
    netting_set_lines: Iterable[_CitedLine],
) -> tuple[str, ...]:
    """Return BA-CVA reduced and standalone-line citations in audit order.

    Parameters
    ----------
    reduced_citations : tuple[str, ...]
        Citations attached to the reduced BA-CVA portfolio result.
    netting_set_lines : Iterable[_CitedLine]
        Standalone netting-set records that expose their own citations.

    Returns
    -------
    tuple[str, ...]
        De-duplicated BA-CVA citation ids preserving first-seen order.
    """

    return merge_citations(
        reduced_citations,
        tuple(citation for line in netting_set_lines for citation in line.citations),
    )
