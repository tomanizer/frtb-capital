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


def test_records_string_is_rejected() -> None:
    with pytest.raises(CvaInputError, match="iterable"):
        adapt_cva_records("not-rows", record_kind="counterparty")  # type: ignore[arg-type]


def test_missing_counterparty_id_is_rejected() -> None:
    result = adapt_cva_records(
        ({"sector": "SOVEREIGN", "source_row_id": "row-1"},),
        record_kind="counterparty",
    )
    assert result.counterparties == ()
    assert result.rejected_rows
    assert "counterparty_id" in result.rejected_rows[0].reason


def test_adapt_netting_set_records() -> None:
    with pytest.raises(CvaInputError, match="references unknown counterparty"):
        adapt_cva_records(
            (
                {
                    "netting_set_id": "ns-1",
                    "counterparty_id": "ctp-1",
                    "ead": 100_000.0,
                    "effective_maturity": 2.5,
                    "discount_factor": 0.95,
                    "currency": "USD",
                    "sign_convention": "non_negative",
                    "uses_imm_ead": False,
                    "carved_out_to_ba_cva": True,
                    "source_row_id": "row-1",
                },
            ),
            record_kind="netting_set",
        )


def test_adapt_hedge_records() -> None:
    result = adapt_cva_records(
        (
            {
                "hedge_id": "h-1",
                "counterparty_id": "ctp-1",
                "hedge_type": "SINGLE_NAME_CDS",
                "notional": 200_000.0,
                "remaining_maturity": 1.5,
                "discount_factor": 0.98,
                "discount_factor_explicit": True,
                "reference_sector": "SOVEREIGN",
                "reference_credit_quality": "INVESTMENT_GRADE",
                "reference_region": "EMEA",
                "reference_relation": "DIRECT",
                "eligibility": "ELIGIBLE",
                "is_internal": True,
                "eligibility_evidence_id": "evidence-1",
                "source_row_id": "row-1",
            },
        ),
        record_kind="hedge",
    )
    assert len(result.hedges) == 1
    assert result.hedges[0].hedge_id == "h-1"
    assert result.hedges[0].is_internal is True


def test_adapt_sa_cva_hedge_record_preserves_nullable_ba_type_and_string_bool() -> None:
    result = adapt_cva_records(
        (
            {
                "hedge_id": "h-sa",
                "counterparty_id": "ctp-1",
                "hedge_type": None,
                "notional": 200_000.0,
                "remaining_maturity": 1.5,
                "discount_factor": 0.98,
                "reference_sector": "SOVEREIGN",
                "reference_credit_quality": "INVESTMENT_GRADE",
                "reference_region": "EMEA",
                "reference_relation": "DIRECT",
                "eligibility": "EXCLUDED",
                "rejection_reason": "market_risk_model_scope",
                "is_internal": "False",
                "sa_cva_risk_class": "GIRR",
                "sa_cva_hedge_purpose": "EXPOSURE_COMPONENT",
                "sa_cva_hedge_instrument_type": "INTEREST_RATE",
                "whole_transaction_evidence_id": "whole-transaction-1",
                "market_risk_ima_eligible": "False",
                "market_risk_ima_exclusion_reason": "not_market_risk_ima_eligible",
                "source_row_id": "row-sa",
            },
        ),
        record_kind="hedge",
    )
    hedge = result.hedges[0]
    assert hedge.hedge_type is None
    assert hedge.is_internal is False
    assert hedge.market_risk_ima_eligible is False


def test_adapt_sa_cva_hedge_record_accepts_integer_bool_values() -> None:
    result = adapt_cva_records(
        (
            {
                "hedge_id": "h-sa",
                "counterparty_id": "ctp-1",
                "hedge_type": None,
                "notional": 200_000.0,
                "remaining_maturity": 1.5,
                "discount_factor": 0.98,
                "reference_sector": "SOVEREIGN",
                "reference_credit_quality": "INVESTMENT_GRADE",
                "reference_region": "EMEA",
                "reference_relation": "DIRECT",
                "eligibility": "ELIGIBLE",
                "is_internal": 0,
                "sa_cva_risk_class": "GIRR",
                "sa_cva_hedge_purpose": "EXPOSURE_COMPONENT",
                "sa_cva_hedge_instrument_type": "INTEREST_RATE",
                "whole_transaction_evidence_id": "whole-transaction-1",
                "market_risk_ima_eligible": 1,
                "eligibility_evidence_id": "evidence-1",
                "source_row_id": "row-sa",
            },
        ),
        record_kind="hedge",
    )

    hedge = result.hedges[0]
    assert hedge.is_internal is False
    assert hedge.market_risk_ima_eligible is True


def test_non_mapping_row_rejected() -> None:
    result = adapt_cva_records(
        [None, 123],
        record_kind="counterparty",
    )
    assert len(result.rejected_rows) == 2
    assert "record must be a mapping" in result.rejected_rows[0].reason
    assert "record must be a mapping" in result.rejected_rows[1].reason


def test_optional_float_with_invalid_type() -> None:
    result = adapt_cva_records(
        (
            {
                "netting_set_id": "ns-1",
                "counterparty_id": "ctp-1",
                "ead": True,  # booleans are not allowed as numeric values
                "source_row_id": "row-1",
            },
        ),
        record_kind="netting_set",
    )
    assert result.netting_sets == ()
    assert result.rejected_rows
    assert "value must be numeric" in result.rejected_rows[0].reason


def test_sensitivity_normalisation_and_conventions() -> None:
    result = adapt_cva_records(
        (
            {
                "sensitivity_id": "sens-1",
                "risk_class": "GIRR",
                "risk_measure": "DELTA",
                "sensitivity_tag": "CVA",
                "bucket_id": "USD",
                "risk_factor_key": "5y",
                "tenor": "5y",
                "amount": -1000.0,
                "amount_currency": "USD",
                "sign_convention": "signed_absolute",
                "source_row_id": "row-1",
            },
        ),
        record_kind="sensitivity",
        amount_sign_convention="signed_absolute",
    )
    assert len(result.sensitivities) == 1
    assert result.sensitivities[0].amount == -1000.0


def test_optional_float_fallback_to_default() -> None:
    # Test remaining_maturity is omitted in hedge and defaults to 1.0
    result = adapt_cva_records(
        (
            {
                "hedge_id": "h-1",
                "counterparty_id": "ctp-1",
                "hedge_type": "SINGLE_NAME_CDS",
                "notional": 200_000.0,
                # remaining_maturity and discount_factor are omitted
                "reference_sector": "SOVEREIGN",
                "reference_credit_quality": "INVESTMENT_GRADE",
                "reference_region": "EMEA",
                "reference_relation": "DIRECT",
                "eligibility": "ELIGIBLE",
                "eligibility_evidence_id": "evidence-1",
                "is_internal": False,
                "source_row_id": "row-1",
            },
        ),
        record_kind="hedge",
    )
    assert len(result.hedges) == 1
    assert result.hedges[0].remaining_maturity == 1.0
    assert result.hedges[0].discount_factor == 1.0
