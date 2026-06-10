from __future__ import annotations

from dataclasses import dataclass

from frtb_cva._citations import collect_ba_citations, merge_citations


@dataclass(frozen=True)
class _Line:
    citations: tuple[str, ...]


def test_merge_citations_preserves_first_seen_order() -> None:
    assert merge_citations(("A", "B"), ("B", "C"), ("A", "D")) == ("A", "B", "C", "D")


def test_collect_ba_citations_merges_reduced_and_line_citations() -> None:
    assert collect_ba_citations(
        ("REDUCED", "COMMON"),
        (_Line(("LINE-1", "COMMON")), _Line(("LINE-2", "REDUCED"))),
    ) == ("REDUCED", "COMMON", "LINE-1", "LINE-2")
