"""
Deterministic CVA audit serialization and reconciliation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from frtb_cva.aggregation import aggregate_inter_bucket
from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
    CvaRunControls,
    CvaSourceLineage,
    SaCvaBucketCapital,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
)
from frtb_cva.sa_cva import sa_cva_aggregation_config
from frtb_cva.numeric import is_reconciled
from frtb_cva.validation import (
    CvaInputError,
    validate_calculation_context,
    validate_cva_counterparties,
    validate_cva_hedges,
    validate_cva_netting_sets,
    validate_sa_cva_sensitivities,
)

_HASH_HEX_LENGTH = 64


def input_hash(
    context: CvaCalculationContext,
    counterparties: Iterable[CvaCounterparty],
    netting_sets: Iterable[CvaNettingSet],
    *,
    hedges: Iterable[CvaHedge] = (),
    sensitivities: Iterable[SaCvaSensitivity] = (),
) -> str:
    """Return a deterministic hash of canonical CVA inputs."""

    validated_context = validate_calculation_context(context)
    validated_counterparties = validate_cva_counterparties(counterparties)
    validated_netting_sets = validate_cva_netting_sets(
        netting_sets,
        counterparties=validated_counterparties,
    )
    validated_hedges = validate_cva_hedges(hedges)
    validated_sensitivities = validate_sa_cva_sensitivities(sensitivities)
    return _input_hash_from_validated(
        validated_context,
        validated_counterparties,
        validated_netting_sets,
        hedges=validated_hedges,
        sensitivities=validated_sensitivities,
    )


def _input_hash_from_validated(
    context: CvaCalculationContext,
    counterparties: tuple[CvaCounterparty, ...],
    netting_sets: tuple[CvaNettingSet, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    sensitivities: tuple[SaCvaSensitivity, ...] = (),
) -> str:
    """Return hash from pre-validated inputs, avoiding double validation."""

    return _hash_payload(
        {
            "context": _context_payload(context),
            "counterparties": [
                _counterparty_payload(counterparty) for counterparty in counterparties
            ],
            "netting_sets": [_netting_set_payload(netting_set) for netting_set in netting_sets],
            "hedges": [_hedge_payload(hedge) for hedge in hedges],
            "sensitivities": [_sensitivity_payload(sensitivity) for sensitivity in sensitivities],
        }
    )


def serialize_cva_result(result: CvaCapitalResult) -> dict[str, object]:
    """Return a JSON-serialisable audit payload for a CVA result."""

    return {
        "run_id": result.run_id,
        "calculation_date": result.calculation_date.isoformat(),
        "base_currency": result.base_currency,
        "profile_id": result.profile_id,
        "profile_hash": result.profile_hash,
        "input_hash": result.input_hash,
        "method": result.method.value,
        "total_cva_capital": result.total_cva_capital,
        "citations": list(result.citations),
        "warnings": list(result.warnings),
        "unsupported_flags": list(result.unsupported_flags),
        "audit_metadata": [list(pair) for pair in result.audit_metadata],
        "ba_cva_reduced": _reduced_portfolio_payload(result.ba_cva_reduced),
        "ba_cva_counterparty_capitals": [
            _counterparty_capital_payload(counterparty)
            for counterparty in result.ba_cva_counterparty_capitals
        ],
        "ba_cva_netting_set_lines": [
            _netting_set_line_payload(line) for line in result.ba_cva_netting_set_lines
        ],
        "sa_cva_risk_class_capitals": [
            _risk_class_capital_payload(risk_class_capital)
            for risk_class_capital in result.sa_cva_risk_class_capitals
        ],
    }


def validate_cva_result_reconciliation(result: CvaCapitalResult) -> None:
    """Raise when a public CVA result does not reconcile to its line records."""

    _validate_hash("profile_hash", result.profile_hash)
    _validate_hash("input_hash", result.input_hash)

    if result.ba_cva_reduced is None and result.method is CvaMethod.BA_CVA_REDUCED:
        raise CvaInputError(
            "BA-CVA reduced result is required for reconciliation",
            field="ba_cva_reduced",
        )

    if result.ba_cva_reduced is not None:
        reduced = result.ba_cva_reduced
        if not is_reconciled(result.total_cva_capital, reduced.k_reduced):
            raise CvaInputError(
                "total CVA capital does not reconcile to reduced BA-CVA capital",
                field="total_cva_capital",
            )

        if result.ba_cva_netting_set_lines != reduced.netting_set_lines:
            raise CvaInputError(
                "netting-set lines do not reconcile to reduced portfolio records",
                field="ba_cva_netting_set_lines",
            )

        if result.ba_cva_counterparty_capitals != reduced.counterparty_capitals:
            raise CvaInputError(
                "counterparty capitals do not reconcile to reduced portfolio records",
                field="ba_cva_counterparty_capitals",
            )

        for counterparty in reduced.counterparty_capitals:
            expected_total = sum(
                line.standalone_capital
                for line in reduced.netting_set_lines
                if line.counterparty_id == counterparty.counterparty_id
            )
            if not is_reconciled(counterparty.standalone_capital, expected_total):
                raise CvaInputError(
                    "counterparty stand-alone capital does not reconcile to netting-set lines",
                    field="standalone_capital",
                    record_id=counterparty.counterparty_id,
                )

        standalones = [capital.standalone_capital for capital in reduced.counterparty_capitals]
        if not is_reconciled(reduced.sum_scva, sum(standalones)):
            raise CvaInputError(
                "reduced portfolio sum_scva does not reconcile",
                field="sum_scva",
            )

        expected_portfolio = (
            reduced.rho * (reduced.sum_scva**2) + (1.0 - reduced.rho) * reduced.sum_scva_squared
        ) ** 0.5
        if not is_reconciled(reduced.k_portfolio, expected_portfolio):
            raise CvaInputError(
                "portfolio capital does not reconcile to MAR50.14 components",
                field="k_portfolio",
            )

        if not is_reconciled(reduced.k_reduced, reduced.d_ba_cva * reduced.k_portfolio):
            raise CvaInputError(
                "reduced capital does not reconcile to discount scalar",
                field="k_reduced",
            )

    if result.method is CvaMethod.SA_CVA:
        if not result.sa_cva_risk_class_capitals:
            raise CvaInputError(
                "SA-CVA result requires at least one risk-class capital record",
                field="sa_cva_risk_class_capitals",
            )
        expected_total = sum(
            risk_class_capital.post_multiplier_capital
            for risk_class_capital in result.sa_cva_risk_class_capitals
        )
        if not is_reconciled(result.total_cva_capital, expected_total):
            raise CvaInputError(
                "total CVA capital does not reconcile to SA-CVA risk-class totals",
                field="total_cva_capital",
            )
        for risk_class_capital in result.sa_cva_risk_class_capitals:
            expected_post = risk_class_capital.m_cva * risk_class_capital.pre_multiplier_capital
            if not is_reconciled(risk_class_capital.post_multiplier_capital, expected_post):
                raise CvaInputError(
                    "SA-CVA risk-class post-multiplier capital does not reconcile",
                    field="post_multiplier_capital",
                    record_id=risk_class_capital.risk_class.value,
                )
            if not risk_class_capital.bucket_capitals:
                raise CvaInputError(
                    "SA-CVA risk-class result requires at least one bucket capital",
                    field="bucket_capitals",
                    record_id=risk_class_capital.risk_class.value,
                )
            recomputed = aggregate_inter_bucket(
                risk_class_capital.bucket_capitals,
                config=sa_cva_aggregation_config(
                    risk_class_capital.risk_class,
                    risk_class_capital.risk_measure,
                    profile=result.profile_id,
                ),
                m_cva=risk_class_capital.m_cva,
                profile=result.profile_id,
            )
            if not is_reconciled(
                risk_class_capital.pre_multiplier_capital,
                recomputed.pre_multiplier_capital,
            ):
                raise CvaInputError(
                    "SA-CVA pre-multiplier capital does not reconcile to bucket capitals",
                    field="pre_multiplier_capital",
                    record_id=risk_class_capital.risk_class.value,
                )


def _validate_hash(field: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != _HASH_HEX_LENGTH:
        raise CvaInputError("hash must be a sha256 hex digest", field=field)
    try:
        int(value, 16)
    except ValueError as exc:
        raise CvaInputError("hash must be a sha256 hex digest", field=field) from exc


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _context_payload(context: CvaCalculationContext) -> dict[str, object]:
    run_controls = context.run_controls or CvaRunControls()
    return {
        "run_id": context.run_id,
        "calculation_date": context.calculation_date.isoformat(),
        "base_currency": context.base_currency,
        "profile": context.profile.value,
        "method": context.method.value,
        "sa_cva_approved": context.sa_cva_approved,
        "materiality_threshold_elected": context.materiality_threshold_elected,
        "carve_out_netting_set_ids": list(context.carve_out_netting_set_ids),
        "desk_id": context.desk_id,
        "legal_entity": context.legal_entity,
        "citation_policy": context.citation_policy,
        "run_controls": {
            "audit_verbosity": run_controls.audit_verbosity,
            "retain_intermediate_details": run_controls.retain_intermediate_details,
            "unsupported_feature_behaviour": run_controls.unsupported_feature_behaviour,
        },
    }


def _counterparty_payload(counterparty: CvaCounterparty) -> dict[str, object]:
    return {
        "counterparty_id": counterparty.counterparty_id,
        "desk_id": counterparty.desk_id,
        "legal_entity": counterparty.legal_entity,
        "sector": counterparty.sector.value,
        "credit_quality": counterparty.credit_quality.value,
        "region": counterparty.region,
        "source_row_id": counterparty.source_row_id,
        "lineage": _lineage_payload(counterparty.lineage),
    }


def _netting_set_payload(netting_set: CvaNettingSet) -> dict[str, object]:
    return {
        "netting_set_id": netting_set.netting_set_id,
        "counterparty_id": netting_set.counterparty_id,
        "ead": netting_set.ead,
        "effective_maturity": netting_set.effective_maturity,
        "discount_factor": netting_set.discount_factor,
        "discount_factor_explicit": netting_set.discount_factor_explicit,
        "currency": netting_set.currency,
        "sign_convention": netting_set.sign_convention,
        "uses_imm_ead": netting_set.uses_imm_ead,
        "carved_out_to_ba_cva": netting_set.carved_out_to_ba_cva,
        "source_row_id": netting_set.source_row_id,
        "lineage": _lineage_payload(netting_set.lineage),
    }


def _hedge_payload(hedge: CvaHedge) -> dict[str, object]:
    return {
        "hedge_id": hedge.hedge_id,
        "source_row_id": hedge.source_row_id,
        "hedge_type": hedge.hedge_type.value,
        "eligibility": hedge.eligibility.value,
        "counterparty_id": hedge.counterparty_id,
        "reference_sector": hedge.reference_sector.value,
        "reference_region": hedge.reference_region,
        "reference_relation": hedge.reference_relation.value,
        "notional": hedge.notional,
        "remaining_maturity": hedge.remaining_maturity,
        "discount_factor": hedge.discount_factor,
        "is_internal": hedge.is_internal,
        "internal_desk_counterparty_id": hedge.internal_desk_counterparty_id,
        "eligibility_evidence_id": hedge.eligibility_evidence_id,
        "rejection_reason": hedge.rejection_reason,
        "sa_cva_risk_class": hedge.sa_cva_risk_class.value
        if hedge.sa_cva_risk_class is not None
        else None,
        "lineage": _lineage_payload(hedge.lineage),
    }


def _sensitivity_payload(sensitivity: SaCvaSensitivity) -> dict[str, object]:
    return {
        "sensitivity_id": sensitivity.sensitivity_id,
        "risk_class": sensitivity.risk_class.value,
        "risk_measure": sensitivity.risk_measure.value,
        "sensitivity_tag": sensitivity.sensitivity_tag.value,
        "bucket_id": sensitivity.bucket_id,
        "risk_factor_key": sensitivity.risk_factor_key,
        "tenor": sensitivity.tenor,
        "amount": sensitivity.amount,
        "amount_currency": sensitivity.amount_currency,
        "sign_convention": sensitivity.sign_convention,
        "volatility_input": sensitivity.volatility_input,
        "hedge_id": sensitivity.hedge_id,
        "source_row_id": sensitivity.source_row_id,
        "lineage": _lineage_payload(sensitivity.lineage),
    }


def _lineage_payload(lineage: CvaSourceLineage | None) -> dict[str, object] | None:
    if lineage is None:
        return None
    return {
        "source_system": lineage.source_system,
        "source_file": lineage.source_file,
        "source_row_id": lineage.source_row_id,
        "source_column_map": [list(pair) for pair in lineage.source_column_map],
    }


def _reduced_portfolio_payload(
    reduced: BaCvaReducedPortfolioResult | None,
) -> dict[str, object] | None:
    if reduced is None:
        return None
    return {
        "k_portfolio": reduced.k_portfolio,
        "k_reduced": reduced.k_reduced,
        "sum_scva": reduced.sum_scva,
        "sum_scva_squared": reduced.sum_scva_squared,
        "rho": reduced.rho,
        "d_ba_cva": reduced.d_ba_cva,
        "alpha": reduced.alpha,
        "citations": list(reduced.citations),
        "counterparty_capitals": [
            _counterparty_capital_payload(counterparty)
            for counterparty in reduced.counterparty_capitals
        ],
        "netting_set_lines": [
            _netting_set_line_payload(line) for line in reduced.netting_set_lines
        ],
    }


def _counterparty_capital_payload(counterparty: BaCvaCounterpartyCapital) -> dict[str, object]:
    return {
        "counterparty_id": counterparty.counterparty_id,
        "sector": counterparty.sector.value,
        "credit_quality": counterparty.credit_quality.value,
        "standalone_capital": counterparty.standalone_capital,
        "netting_set_ids": list(counterparty.netting_set_ids),
        "region": counterparty.region,
        "citations": list(counterparty.citations),
    }


def _netting_set_line_payload(line: BaCvaStandAloneLine) -> dict[str, object]:
    return {
        "netting_set_id": line.netting_set_id,
        "counterparty_id": line.counterparty_id,
        "sector": line.sector.value,
        "credit_quality": line.credit_quality.value,
        "risk_weight": line.risk_weight,
        "alpha": line.alpha,
        "effective_maturity": line.effective_maturity,
        "ead": line.ead,
        "discount_factor": line.discount_factor,
        "standalone_capital": line.standalone_capital,
        "currency": line.currency,
        "source_row_id": line.source_row_id,
        "citations": list(line.citations),
        "uses_imm_ead": line.uses_imm_ead,
        "discount_factor_supplied": line.discount_factor_supplied,
    }


def _risk_class_capital_payload(
    risk_class_capital: SaCvaRiskClassCapital,
) -> dict[str, object]:
    return {
        "risk_class": risk_class_capital.risk_class.value,
        "risk_measure": risk_class_capital.risk_measure.value,
        "pre_multiplier_capital": risk_class_capital.pre_multiplier_capital,
        "post_multiplier_capital": risk_class_capital.post_multiplier_capital,
        "m_cva": risk_class_capital.m_cva,
        "citations": list(risk_class_capital.citations),
        "bucket_capitals": [
            _bucket_capital_payload(bucket) for bucket in risk_class_capital.bucket_capitals
        ],
    }


def _bucket_capital_payload(bucket: SaCvaBucketCapital) -> dict[str, object]:
    return {
        "bucket_id": bucket.bucket_id,
        "risk_class": bucket.risk_class.value,
        "risk_measure": bucket.risk_measure.value,
        "k_b": bucket.k_b,
        "s_b": bucket.s_b,
        "sensitivity_ids": list(bucket.sensitivity_ids),
        "citations": list(bucket.citations),
        "branch_metadata": [list(pair) for pair in bucket.branch_metadata],
    }


__all__ = [
    "_input_hash_from_validated",
    "input_hash",
    "serialize_cva_result",
    "validate_cva_result_reconciliation",
]
