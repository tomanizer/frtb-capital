from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pyarrow as pa
import pytest
from frtb_common import (
    ColumnSpec,
    ComponentCapitalSummary,
    ComponentHandoffError,
    ComponentResultHandoff,
    ComponentSummaryError,
    NormalizedArrowTable,
    NormalizedTableError,
    NormalizedTabularHandoff,
    StandardisedComponent,
    TabularHandoffError,
    TabularLogicalType,
    column_specs_to_arrow_schema,
    column_specs_to_json_schema,
    handoff_specs_to_arrow_schema,
    handoff_specs_to_json_schema,
    normalized_arrow_table_hash,
    normalized_handoff_hash,
    read_handoff_columns,
)
from frtb_common.arrow_conversion import ArrowColumnArray, HandoffColumnArray
from frtb_cva import build_cva_counterparty_batch_from_handoff
from frtb_cva.validation import CvaInputError
from frtb_drc import build_drc_nonsec_batch_from_handoff
from frtb_drc import to_orchestration_handoff as drc_to_orchestration_handoff
from frtb_drc.validation import DrcInputError
from frtb_orchestration import compose_standardised_approach_capital
from frtb_rrao import build_rrao_batch_from_handoff, to_orchestration_handoff
from frtb_rrao.validation import RraoInputError


def test_common_old_handoff_callables_warn() -> None:
    table = pa.table({"amount": [1.0]})
    amount_spec = ColumnSpec("amount", logical_type=TabularLogicalType.FLOAT)
    normalized = NormalizedArrowTable(accepted=table, column_specs=(amount_spec,))

    with pytest.warns(DeprecationWarning, match="normalized_handoff_hash"):
        legacy_hash = normalized_handoff_hash(normalized)

    assert legacy_hash == normalized_arrow_table_hash(normalized)

    with pytest.warns(DeprecationWarning, match="read_handoff_columns"):
        columns = read_handoff_columns(
            table,
            (amount_spec,),
            error=lambda message, _field: ValueError(message),
        )

    assert columns["amount"].tolist() == [1.0]

    with pytest.warns(DeprecationWarning, match="handoff_specs_to_json_schema"):
        legacy_json_schema = handoff_specs_to_json_schema((amount_spec,), title="Amount")

    assert legacy_json_schema == column_specs_to_json_schema((amount_spec,), title="Amount")

    with pytest.warns(DeprecationWarning, match="handoff_specs_to_arrow_schema"):
        legacy_arrow_schema = handoff_specs_to_arrow_schema((amount_spec,))

    assert legacy_arrow_schema == column_specs_to_arrow_schema((amount_spec,))


def test_common_old_type_aliases_preserve_identity() -> None:
    assert NormalizedTabularHandoff is NormalizedArrowTable
    assert TabularHandoffError is NormalizedTableError
    assert ComponentResultHandoff is ComponentCapitalSummary
    assert ComponentHandoffError is ComponentSummaryError
    assert HandoffColumnArray is ArrowColumnArray


def test_package_old_handoff_wrappers_warn_before_delegating() -> None:
    with pytest.warns(DeprecationWarning, match="build_rrao_batch_from_handoff"):
        with pytest.raises(RraoInputError):
            build_rrao_batch_from_handoff(object())  # type: ignore[arg-type]

    with pytest.warns(DeprecationWarning, match="build_drc_nonsec_batch_from_handoff"):
        with pytest.raises(DrcInputError):
            build_drc_nonsec_batch_from_handoff(object())  # type: ignore[arg-type]

    with pytest.warns(DeprecationWarning, match="build_cva_counterparty_batch_from_handoff"):
        with pytest.raises(CvaInputError):
            build_cva_counterparty_batch_from_handoff(object())  # type: ignore[arg-type]


def test_old_component_summary_adapter_warns() -> None:
    rrao_result = SimpleNamespace(
        run_id="rrao-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        total_rrao=10.0,
        profile_hash="profile",
        input_hash="input",
        lines=(object(),),
        excluded_lines=(),
        subtotals=(object(),),
        citations=("__.1",),
        warnings=(),
    )

    with pytest.warns(DeprecationWarning, match="to_orchestration_handoff"):
        summary = to_orchestration_handoff(rrao_result)  # type: ignore[arg-type]

    assert summary.component is StandardisedComponent.RRAO
    assert summary.total_capital == 10.0

    drc_result = SimpleNamespace(
        package_name="frtb-drc",
        run_id="drc-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        total_drc=20.0,
        profile_hash="profile",
        input_hash="input",
        input_count=1,
        rejected_input_count=0,
        categories=(object(),),
        citations=("__.1",),
        warnings=(),
    )

    with pytest.warns(DeprecationWarning, match="to_orchestration_handoff"):
        drc_summary = drc_to_orchestration_handoff(drc_result)  # type: ignore[arg-type]

    assert drc_summary.component is StandardisedComponent.DRC
    assert drc_summary.total_capital == 20.0


def test_orchestration_old_summary_keywords_warn() -> None:
    sbm = _summary(StandardisedComponent.SBM, total=10.0)
    drc = _summary(StandardisedComponent.DRC, total=20.0)
    rrao = _summary(StandardisedComponent.RRAO, total=30.0)

    with pytest.warns(DeprecationWarning, match="sbm_handoff"):
        result = compose_standardised_approach_capital(
            sbm_handoff=sbm,
            drc_summary=drc,
            rrao_summary=rrao,
        )

    assert result.total_capital == 60.0


def _summary(component: StandardisedComponent, *, total: float) -> ComponentCapitalSummary:
    return ComponentCapitalSummary(
        component=component,
        package_name=f"frtb-{component.value.lower()}",
        run_id=f"{component.value.lower()}-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        total_capital=total,
        profile_hash=f"{component.value.lower()}-profile",
        input_hash=f"{component.value.lower()}-input",
        line_count=1,
        excluded_line_count=0,
        subtotal_count=1,
        citations=("__.1",),
    )
