from __future__ import annotations

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from frtb_rrao import (
    RraoCalculationContext,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    input_hash_for_positions,
)
from frtb_rrao.numeric import is_reconciled

NOTIONALS = st.floats(
    min_value=0.0,
    max_value=100_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
INCLUDED_EVIDENCE = st.sampled_from(
    (
        (RraoEvidenceType.EXOTIC_UNDERLYING, RraoClassification.EXOTIC),
        (RraoEvidenceType.GAP_RISK, RraoClassification.OTHER_RESIDUAL_RISK),
        (RraoEvidenceType.CORRELATION_RISK, RraoClassification.OTHER_RESIDUAL_RISK),
        (RraoEvidenceType.BEHAVIOURAL_RISK, RraoClassification.OTHER_RESIDUAL_RISK),
    )
)


def sample_lineage(index: int) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="hypothesis",
        source_file="generated",
        source_row_id=f"row-{index:03d}",
        source_column_map=(("notional", "gross_effective_notional"),),
    )


def context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-properties",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )


def included_position(
    index: int,
    notional: float,
    evidence_pair: tuple[RraoEvidenceType, RraoClassification],
) -> RraoPosition:
    evidence_type, classification = evidence_pair
    return RraoPosition(
        position_id=f"pos-{index:03d}",
        source_row_id=f"row-{index:03d}",
        desk_id=f"desk-{index % 3}",
        legal_entity=f"LE-{index % 2}",
        gross_effective_notional=notional,
        currency="USD",
        evidence_type=evidence_type,
        evidence_label=evidence_type.value.lower(),
        classification_hint=classification,
        lineage=sample_lineage(index),
    )


def listed_exclusion(index: int, notional: float) -> RraoPosition:
    return RraoPosition(
        position_id=f"excluded-{index:03d}",
        source_row_id=f"excluded-row-{index:03d}",
        desk_id="desk-excluded",
        legal_entity="LE-X",
        gross_effective_notional=notional,
        currency="USD",
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="listed option",
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.LISTED,
        exclusion_evidence_id=f"exchange-listing-{index:03d}",
        lineage=sample_lineage(10_000 + index),
    )


@st.composite
def included_positions(draw: st.DrawFn) -> tuple[RraoPosition, ...]:
    notionals = draw(st.lists(NOTIONALS, min_size=1, max_size=20))
    evidence = draw(st.lists(INCLUDED_EVIDENCE, min_size=len(notionals), max_size=len(notionals)))
    return tuple(
        included_position(index, notional, evidence_pair)
        for index, (notional, evidence_pair) in enumerate(zip(notionals, evidence, strict=True))
    )


def canonical_line_snapshot(result: RraoCapitalResult) -> tuple[object, ...]:
    lines = sorted(
        (
            line.position_id,
            line.classification.value,
            line.gross_effective_notional,
            line.add_on,
            line.is_excluded,
        )
        for line in result.lines + result.excluded_lines
    )
    return tuple(lines)


def canonical_subtotal_snapshot(result: RraoCapitalResult) -> tuple[object, ...]:
    return tuple(
        sorted(
            (
                subtotal.subtotal_type,
                subtotal.subtotal_key,
                tuple(sorted(subtotal.position_ids)),
            )
            for subtotal in result.subtotals
        )
    )


@given(positions=included_positions())
def test_rrao_total_equals_sum_of_included_line_addons(positions: tuple[RraoPosition, ...]) -> None:
    result = calculate_rrao_capital(positions, context=context())

    assert result.total_rrao == sum(line.add_on for line in result.lines)


@given(positions=included_positions(), excluded_notional=NOTIONALS)
def test_explicit_exclusion_does_not_change_total_rrao(
    positions: tuple[RraoPosition, ...],
    excluded_notional: float,
) -> None:
    base = calculate_rrao_capital(positions, context=context())
    with_exclusion = calculate_rrao_capital(
        (*positions, listed_exclusion(len(positions), excluded_notional)),
        context=context(),
    )

    assert with_exclusion.total_rrao == base.total_rrao


@given(positions=included_positions())
def test_input_permutation_is_stable_after_canonical_sorting(
    positions: tuple[RraoPosition, ...],
) -> None:
    reversed_positions = tuple(reversed(positions))

    result = calculate_rrao_capital(positions, context=context())
    reordered = calculate_rrao_capital(reversed_positions, context=context())

    assert is_reconciled(result.total_rrao, reordered.total_rrao)
    assert canonical_line_snapshot(result) == canonical_line_snapshot(reordered)
    assert canonical_subtotal_snapshot(result) == canonical_subtotal_snapshot(reordered)


@given(
    notional=st.integers(min_value=0, max_value=100_000_000),
    increment=st.integers(min_value=1, max_value=1_000),
)
def test_distinct_canonical_inputs_have_distinct_hashes(notional: int, increment: int) -> None:
    first = (
        included_position(
            1,
            float(notional),
            (RraoEvidenceType.EXOTIC_UNDERLYING, RraoClassification.EXOTIC),
        ),
    )
    second = (
        included_position(
            1,
            float(notional + increment),
            (RraoEvidenceType.EXOTIC_UNDERLYING, RraoClassification.EXOTIC),
        ),
    )

    assert input_hash_for_positions(first) != input_hash_for_positions(second)


@given(positions=included_positions(), excluded_notional=NOTIONALS)
def test_exclusion_partitions_are_disjoint(
    positions: tuple[RraoPosition, ...],
    excluded_notional: float,
) -> None:
    result = calculate_rrao_capital(
        (*positions, listed_exclusion(len(positions), excluded_notional)),
        context=context(),
    )

    included_ids = {line.position_id for line in result.lines}
    excluded_ids = {line.position_id for line in result.excluded_lines}
    assert included_ids.isdisjoint(excluded_ids)
