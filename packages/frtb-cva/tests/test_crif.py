from __future__ import annotations

import pytest
from frtb_cva.crif import adapt_cva_records
from frtb_cva.validation import CvaInputError


def test_crif_module_has_no_pandas_import() -> None:
    import inspect

    import frtb_cva.crif as module

    source = inspect.getsource(module)
    assert "import pandas" not in source


def test_adapt_counterparty_records() -> None:
    result = adapt_cva_records(
        (
            {
                "counterparty_id": "ctp-1",
                "sector": "SOVEREIGN",
                "credit_quality": "INVESTMENT_GRADE",
                "region": "EMEA",
                "source_row_id": "row-1",
            },
        ),
        record_kind="counterparty",
    )
    assert len(result.counterparties) == 1
    assert result.counterparties[0].counterparty_id == "ctp-1"


def test_ambiguous_sensitivity_tag_is_rejected() -> None:
    result = adapt_cva_records(
        (
            {
                "sensitivity_id": "sens-1",
                "risk_class": "GIRR",
                "risk_measure": "DELTA",
                "sensitivity_tag": "UNKNOWN",
                "bucket_id": "USD",
                "risk_factor_key": "5y",
                "tenor": "5y",
                "amount": 1.0,
                "amount_currency": "USD",
                "source_row_id": "row-1",
            },
        ),
        record_kind="sensitivity",
    )
    assert result.sensitivities == ()
    assert result.rejected_rows


def test_invalid_record_kind_fails() -> None:
    with pytest.raises(CvaInputError, match="record_kind"):
        adapt_cva_records((), record_kind="invalid")
