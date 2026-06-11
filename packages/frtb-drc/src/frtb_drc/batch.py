"""Package-owned DRC batches for high-volume DRC kernels."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np

from frtb_drc._batch_columns import BoolArray, FloatArray, ObjectArray
from frtb_drc._identifiers import slug_path as _slug
from frtb_drc._netting_helpers import (
    risk_weights_for_net_jtd as _risk_weights_for_net_jtd,
)
from frtb_drc._validation_utils import require_text as _required_text
from frtb_drc._version import __version__
from frtb_drc.assembly.hashes import (
    context_input_hash_for_drc_batch as _context_input_hash_for_batch,
)
from frtb_drc.assembly.hashes import input_hash_for_drc_batch
from frtb_drc.attribution import calculate_drc_attribution
from frtb_drc.audit import validate_reconciliation
from frtb_drc.capital import CapitalInput, calculate_category_drc
from frtb_drc.ctp import CtpCapitalInput, calculate_ctp_category_drc
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    CategoryDrc,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcFxConversion,
    DrcFxRate,
    DrcRiskClass,
    DrcSeniority,
    NetJtd,
)
from frtb_drc.fair_value_cap import (
    used_fair_value_cap_evidence_for_position_ids,
    validate_fair_value_cap_evidence,
)
from frtb_drc.fx import (
    fx_branch_metadata,
    fx_citation_ids,
    fx_conversion_records,
    input_hash_with_fx,
    require_fx_rate,
    validate_fx_rates,
)
from frtb_drc.kernel import net_jtd as _net_jtd_kernel
from frtb_drc.reference_data import (
    get_lgd_rule,
    get_maturity_policy,
    get_risk_weight_rule,
    iter_lgd_rules,
)
from frtb_drc.regimes import DrcRuleProfile, ensure_risk_class_supported, get_rule_profile
from frtb_drc.risk_weight_evidence import (
    effective_risk_weights,
    used_risk_weight_evidence_for_position_ids,
)
from frtb_drc.securitisation import (
    SecuritisationNonCtpCapitalInput,
    calculate_securitisation_non_ctp_category_drc,
)
from frtb_drc.validation import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    DrcInputError,
    chargeable_non_securitisation_bucket_keys,
    chargeable_securitisation_non_ctp_bucket_keys,
    ensure_chargeable_credit_quality,
    ensure_chargeable_non_securitisation_bucket,
    ensure_chargeable_securitisation_non_ctp_bucket,
)

_US_NPR_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_BASEL_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_EU_CRR3_FORMULA_CITATIONS = ("EU_CRR3_ARTICLE_325W",)
_US_NPR_NETTING_CITATION = "US_NPR_210_B_2"
_BASEL_NETTING_CITATION = "BASEL_MAR22_19"
_EU_CRR3_NETTING_CITATION = "EU_CRR3_ARTICLE_325X"
_US_NPR_ZERO_CATEGORY_CITATION = "US_NPR_210_B_3_III"
_BASEL_ZERO_CATEGORY_CITATION = "BASEL_MAR22_26"
_EU_CRR3_ZERO_CATEGORY_CITATION = "EU_CRR3_ARTICLE_325Y_3_5"
_SEC_NON_CTP_GROSS_CITATIONS = ("US_NPR_210_C_1", "BASEL_MAR22_27")
_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("US_NPR_210_C_3_III", "BASEL_MAR22_34")
_SEC_NON_CTP_NETTING_CITATIONS = (
    "US_NPR_210_C_2",
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_SEC_NON_CTP_BATCH_CITATIONS = (
    *_SEC_NON_CTP_GROSS_CITATIONS,
    *_SEC_NON_CTP_NETTING_CITATIONS,
    "US_NPR_210_C_3_I_II",
    "US_NPR_210_C_3_III",
    "US_NPR_210_C_3_IV",
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
    "BASEL_MAR22_35",
)
_BASEL_SEC_NON_CTP_GROSS_CITATIONS = ("BASEL_MAR22_27",)
_BASEL_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("BASEL_MAR22_34",)
_BASEL_SEC_NON_CTP_NETTING_CITATIONS = (
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_BASEL_SEC_NON_CTP_BATCH_CITATIONS = (
    *_BASEL_SEC_NON_CTP_GROSS_CITATIONS,
    *_BASEL_SEC_NON_CTP_NETTING_CITATIONS,
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
    "BASEL_MAR22_35",
)
_CTP_GROSS_CITATIONS = ("US_NPR_210_D_1",)
_BASEL_CTP_GROSS_CITATIONS = ("BASEL_MAR22_36", "BASEL_MAR22_37")
_CTP_NETTING_CITATIONS = ("US_NPR_210_D_2",)
_BASEL_CTP_NETTING_CITATIONS = ("BASEL_MAR22_39",)
_CTP_BATCH_CITATIONS = (
    *_CTP_GROSS_CITATIONS,
    *_CTP_NETTING_CITATIONS,
    "US_NPR_210_D_3_I_III",
    "US_NPR_210_D_3_IV",
    "US_NPR_210_D_3_IV_D",
    "US_NPR_210_D_3_V",
)
_BASEL_CTP_BATCH_CITATIONS = (
    *_BASEL_CTP_GROSS_CITATIONS,
    *_BASEL_CTP_NETTING_CITATIONS,
    "BASEL_MAR22_40",
    "BASEL_MAR22_41",
    "BASEL_MAR22_42",
    "BASEL_MAR22_44",
    "BASEL_MAR22_45",
)


@dataclass(frozen=True)
class DrcPositionBatch:
    """Kernel-facing non-securitisation DRC input batch."""

    position_ids: ObjectArray
    source_row_ids: ObjectArray
    desk_ids: ObjectArray
    legal_entities: ObjectArray
    risk_classes: ObjectArray
    instrument_types: ObjectArray
    default_directions: ObjectArray
    issuer_ids: ObjectArray
    tranche_ids: ObjectArray
    index_series_ids: ObjectArray
    bucket_keys: ObjectArray
    seniorities: ObjectArray
    credit_qualities: ObjectArray
    notionals: FloatArray
    market_values: FloatArray
    cumulative_pnls: FloatArray
    maturity_years: FloatArray
    currencies: ObjectArray
    lgd_overrides: FloatArray
    is_defaulted: BoolArray
    is_gse: BoolArray
    is_pse: BoolArray
    is_covered_bond: BoolArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_present: BoolArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    citation_ids: tuple[tuple[str, ...], ...]
    input_hash: str
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

    @property
    def row_count(self) -> int:
        """Number of positions carried by the batch.

        Returns
        -------
        int
            Length of the ``position_ids`` column.
        """
        return int(self.position_ids.shape[0])


@dataclass(frozen=True)
class DrcBatchCapitalCalculation:
    """DRC batch calculation with array intermediates and row API-compatible capital."""

    result: DrcCapitalResult
    gross_jtd: FloatArray
    maturity_weights: FloatArray
    scaled_jtd: FloatArray
    accepted_row_dataclasses_materialized: int = 0


def calculate_drc_capital_from_batch(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> DrcBatchCapitalCalculation:
    """Calculate supported DRC capital from a columnar batch.

    Parameters
    ----------
    batch : DrcPositionBatch
        Validated position batch for the active risk class.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    DrcBatchCapitalCalculation
        Capital result plus array intermediates for audit replay.
    """

    if not isinstance(batch, DrcPositionBatch):
        raise DrcInputError("batch must be DrcPositionBatch")
    _validate_context(context)
    profile = get_rule_profile(context.profile_id)
    risk_class = _batch_risk_class(batch)
    _validate_supported_batch_run(batch, context=context, profile=profile)
    calculation_batch, fx_conversions = _convert_batch_to_base_currency(
        batch,
        context=context,
    )

    if risk_class is DrcRiskClass.NON_SECURITISATION:
        gross_jtd, lgd_citations = _gross_jtd_array(
            calculation_batch,
            profile_id=profile.profile_id,
        )
        maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
            calculation_batch,
            gross_jtd,
            profile_id=profile.profile_id,
        )
        netting_citation = _nonsec_netting_citation(profile.profile_id)
        net_jtds = _net_jtd_kernel.calculate_nonsec_net_jtds_from_arrays(
            calculation_batch,
            gross_jtd,
            scaled_jtd,
            netting_citation=netting_citation,
        )
        capital_inputs = _capital_inputs(calculation_batch, net_jtds)
        category = (
            calculate_category_drc(capital_inputs, profile_id=profile.profile_id)
            if capital_inputs
            else _zero_nonsec_category(profile.profile_id)
        )
        formula_citations = (
            *_nonsec_formula_citations(profile.profile_id),
            maturity_citation,
            *lgd_citations,
            *((netting_citation,) if net_jtds else ()),
        )
    elif risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        gross_jtd = _securitisation_non_ctp_gross_jtd_array(calculation_batch, context=context)
        maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
            calculation_batch,
            gross_jtd,
            profile_id=profile.profile_id,
        )
        net_jtds = _net_jtd_kernel.calculate_securitisation_non_ctp_net_jtds_from_arrays(
            calculation_batch,
            gross_jtd,
            scaled_jtd,
            context=context,
            netting_citations=_sec_non_ctp_netting_citations(context.profile_id),
        )
        sec_capital_inputs = _securitisation_non_ctp_capital_inputs_from_batch(
            net_jtds,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            ),
        )
        category = calculate_securitisation_non_ctp_category_drc(
            sec_capital_inputs,
            profile_id=profile.profile_id,
        )
        formula_citations = (
            *_sec_non_ctp_batch_citations(profile.profile_id),
            *_batch_fair_value_cap_citations(calculation_batch, context=context),
            maturity_citation,
        )
    elif risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        gross_jtd = _market_value_gross_jtd_array(calculation_batch)
        maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
            calculation_batch,
            gross_jtd,
            profile_id=profile.profile_id,
        )
        net_jtds = _net_jtd_kernel.calculate_ctp_net_jtds_from_arrays(
            calculation_batch,
            gross_jtd,
            scaled_jtd,
            context=context,
            netting_citations=_ctp_netting_citations(context.profile_id),
        )
        ctp_capital_inputs = _ctp_capital_inputs_from_batch(
            net_jtds,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ),
        )
        category = calculate_ctp_category_drc(ctp_capital_inputs, profile_id=profile.profile_id)
        formula_citations = (*_ctp_batch_citations(profile.profile_id), maturity_citation)
    else:  # pragma: no cover - _batch_risk_class only returns known enum values.
        raise DrcInputError(f"unsupported DRC batch risk_class: {risk_class.value}")

    input_hash = _context_input_hash_for_batch(
        calculation_batch.input_hash,
        calculation_batch,
        context=context,
        risk_class=risk_class,
    )
    result = DrcCapitalResult(
        result_id=f"drc-{_slug(context.run_id)}-{input_hash[:12]}",
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=profile.profile_id,
        profile_hash=profile.content_hash,
        input_hash=input_hash,
        categories=(category,),
        total_drc=category.capital,
        citations=_collect_batch_citations(
            calculation_batch,
            category=category,
            net_jtds=net_jtds,
            formula_citations=formula_citations,
            fx_citations=fx_citation_ids(fx_conversions),
            profile_id=profile.profile_id,
        ),
        warnings=(),
        branch_metadata=(
            BranchMetadata(
                branch_id=f"drc-{_slug(risk_class.value)}-batch-api",
                branch_type=BranchType.NORMAL,
                source_id=profile.profile_id,
                selected=True,
                reason=(
                    f"batch API executed supported {risk_class.value} path; "
                    "attribution records are calculated on API-compatible net JTDs"
                ),
                citations=_batch_api_citations(profile.profile_id, risk_class),
            ),
            *_fair_value_cap_branch_metadata_for_batch(
                calculation_batch,
                context=context,
                risk_class=risk_class,
            ),
            *fx_branch_metadata(fx_conversions),
        ),
        package_name="frtb-drc",
        package_version=__version__,
        input_count=calculation_batch.row_count,
        rejected_input_count=len(calculation_batch.diagnostics),
        input_positions=(),
        gross_jtds=(),
        maturity_scaled_jtds=(),
        net_jtds=net_jtds,
        fx_conversions=fx_conversions,
        risk_weight_evidence=used_risk_weight_evidence_for_position_ids(
            (cast(str, position_id) for position_id in calculation_batch.position_ids),
            context,
            risk_class=risk_class,
        )
        if risk_class
        in {
            DrcRiskClass.SECURITISATION_NON_CTP,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        }
        else (),
        fair_value_cap_evidence=used_fair_value_cap_evidence_for_position_ids(
            (cast(str, position_id) for position_id in calculation_batch.position_ids),
            context,
        )
        if risk_class is DrcRiskClass.SECURITISATION_NON_CTP
        else (),
    )
    result = replace(
        result,
        attribution_records=calculate_drc_attribution(
            result,
            risk_weights_by_position=_batch_risk_weights_by_position(
                calculation_batch,
                context=context,
                risk_class=risk_class,
            ),
            input_hash=result.input_hash,
            profile_hash=result.profile_hash,
        ),
    )
    validate_reconciliation(result)
    return DrcBatchCapitalCalculation(
        result=result,
        gross_jtd=_batch_arrays.readonly_array(
            np.asarray(gross_jtd, dtype=np.float64).copy(),
            copy=False,
        ),
        maturity_weights=_batch_arrays.readonly_array(
            np.asarray(maturity_weights, dtype=np.float64).copy(),
            copy=False,
        ),
        scaled_jtd=_batch_arrays.readonly_array(
            np.asarray(scaled_jtd, dtype=np.float64).copy(),
            copy=False,
        ),
        accepted_row_dataclasses_materialized=0,
    )


def _validate_context(context: DrcCalculationContext) -> None:
    if context.run_id.strip() == "":
        raise DrcInputError("run_id must be non-empty")
    if context.base_currency.strip() == "":
        raise DrcInputError("base_currency must be non-empty")
    if context.profile_id.strip() == "":
        raise DrcInputError("profile_id must be non-empty")
    if context.citation_policy.strip() == "":
        raise DrcInputError("citation_policy must be non-empty")
    if context.citation_policy.strip().lower() != "strict":
        raise DrcInputError(f"unsupported citation_policy: {context.citation_policy}")
    validate_fx_rates(context)
    effective_risk_weights(context, risk_class=DrcRiskClass.SECURITISATION_NON_CTP)
    validate_fair_value_cap_evidence(
        context.securitisation_non_ctp_fair_value_cap_evidence,
        context=context,
    )
    _validate_context_text_map(
        context.securitisation_non_ctp_offset_groups,
        field_name="context.securitisation_non_ctp_offset_groups",
    )
    effective_risk_weights(context, risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    _validate_context_text_map(context.ctp_offset_groups, field_name="context.ctp_offset_groups")


def _validate_context_risk_weight_map(values: Mapping[str, float], *, field_name: str) -> None:
    for position_id, risk_weight in values.items():
        _required_text(position_id, f"{field_name} position_id")
        _coerce_finite_non_negative_float(
            risk_weight,
            field_name=f"{field_name}[{position_id!r}]",
        )


def _validate_context_text_map(values: Mapping[str, str], *, field_name: str) -> None:
    for position_id, value in values.items():
        _required_text(position_id, f"{field_name} position_id")
        _required_text(value, f"{field_name}[{position_id!r}]")


def _validate_supported_batch_run(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    profile: DrcRuleProfile,
) -> None:
    risk_class = _batch_risk_class(batch)
    ensure_risk_class_supported(profile, risk_class)
    scoped_desk_id = context.desk_id.strip()
    scoped_legal_entity = context.legal_entity.strip()
    if scoped_desk_id:
        _raise_first_mismatch(
            batch.desk_ids,
            scoped_desk_id,
            message=lambda index: (
                f"position {batch.position_ids[index]} desk_id {batch.desk_ids[index]} "
                f"does not match context desk_id {scoped_desk_id}"
            ),
        )
    if scoped_legal_entity:
        _raise_first_mismatch(
            batch.legal_entities,
            scoped_legal_entity,
            message=lambda index: (
                f"position {batch.position_ids[index]} legal_entity "
                f"{batch.legal_entities[index]} does not match context legal_entity "
                f"{scoped_legal_entity}"
            ),
        )
    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        risk_weights = effective_risk_weights(
            context,
            risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        )
        _validate_context_position_map(
            batch,
            risk_weights,
            field_name="context.securitisation_non_ctp_risk_weights",
        )
        _validate_context_position_map(
            batch,
            context.securitisation_non_ctp_offset_groups,
            field_name="context.securitisation_non_ctp_offset_groups",
            require_all=False,
        )
        _validate_context_position_map(
            batch,
            context.securitisation_non_ctp_fair_value_cap_evidence,
            field_name="context.securitisation_non_ctp_fair_value_cap_evidence",
            require_all=False,
        )
    elif risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        risk_weights = effective_risk_weights(
            context,
            risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        )
        _validate_context_position_map(
            batch,
            risk_weights,
            field_name="context.ctp_risk_weights",
        )
        _validate_context_position_map(
            batch,
            context.ctp_offset_groups,
            field_name="context.ctp_offset_groups",
            require_all=False,
        )


def _batch_risk_class(batch: DrcPositionBatch) -> DrcRiskClass:
    unique = tuple(sorted(np.unique(batch.risk_classes)))
    if len(unique) != 1:
        raise DrcInputError(
            "DRC batch calculation requires one risk_class; mixed risk classes must "
            "be split into class-specific batches"
        )
    return DrcRiskClass(cast(str, unique[0]))


def _validate_context_position_map(
    batch: DrcPositionBatch,
    values: Mapping[str, object],
    *,
    field_name: str,
    require_all: bool = True,
) -> None:
    position_ids = {cast(str, position_id) for position_id in batch.position_ids.tolist()}
    keys = {str(position_id) for position_id in values}
    if require_all:
        missing = sorted(position_ids - keys)
        if missing:
            raise DrcInputError(f"{field_name} is required for positions: " + ", ".join(missing))
    unused = sorted(keys - position_ids)
    if unused:
        raise DrcInputError(f"{field_name} contains unused position ids: " + ", ".join(unused))


def _convert_batch_to_base_currency(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> tuple[DrcPositionBatch, tuple[DrcFxConversion, ...]]:
    conversion_mask = batch.currencies != context.base_currency
    if not bool(np.any(conversion_mask)):
        return batch, ()

    rates = np.ones(batch.row_count, dtype=np.float64)
    used_rates: dict[str, DrcFxRate] = {}
    counts: dict[str, int] = {}
    for raw_currency in sorted(np.unique(batch.currencies[conversion_mask])):
        currency = cast(str, raw_currency)
        first_index = int(np.nonzero(batch.currencies == currency)[0][0])
        rate = require_fx_rate(
            context,
            source_currency=currency,
            position_id=cast(str, batch.position_ids[first_index]),
        )
        mask = batch.currencies == currency
        rates[mask] = rate.rate
        used_rates[currency] = rate
        counts[currency] = int(np.count_nonzero(mask))

    conversions = fx_conversion_records(used_rates, counts)
    converted_currencies = _batch_arrays.object_array(
        [context.base_currency] * batch.row_count,
        copy=True,
    )
    converted = replace(
        batch,
        notionals=_batch_arrays.readonly_array(
            np.asarray(batch.notionals * rates, dtype=np.float64).copy(),
            copy=False,
        ),
        market_values=_batch_arrays.readonly_array(
            np.asarray(batch.market_values * rates, dtype=np.float64).copy(),
            copy=False,
        ),
        cumulative_pnls=_batch_arrays.readonly_array(
            np.asarray(batch.cumulative_pnls * rates, dtype=np.float64).copy(),
            copy=False,
        ),
        currencies=converted_currencies,
        input_hash=input_hash_with_fx(batch.input_hash, conversions),
    )
    return converted, conversions


def _validate_batch(
    batch: DrcPositionBatch,
    *,
    expected_risk_class: DrcRiskClass,
    profile_id: str,
) -> None:
    if not np.all(batch.risk_classes == expected_risk_class.value):
        unique = ", ".join(str(value) for value in sorted(np.unique(batch.risk_classes)))
        raise DrcInputError(
            "DRC batch builder requires a single supported risk_class "
            f"{expected_risk_class.value}; received {unique}"
        )
    _validate_common_batch_fields(batch)
    if expected_risk_class is DrcRiskClass.NON_SECURITISATION:
        _validate_nonsec_batch(batch, profile_id=profile_id)
    elif expected_risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        _validate_securitisation_non_ctp_batch(batch)
    elif expected_risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        _validate_ctp_batch(batch)
    else:  # pragma: no cover - all enum values are handled above.
        raise DrcInputError(f"unsupported DRC batch risk_class: {expected_risk_class.value}")


def _validate_common_batch_fields(batch: DrcPositionBatch) -> None:
    if not np.all(np.isfinite(batch.notionals)):
        raise DrcInputError("notional values must be finite")
    if not np.all(np.isfinite(batch.maturity_years)):
        raise DrcInputError("maturity_years values must be finite")
    if np.any(batch.maturity_years < 0.0):
        raise DrcInputError("maturity_years values must be non-negative")
    for field_name, values in (
        ("market_value", batch.market_values),
        ("cumulative_pnl", batch.cumulative_pnls),
        ("lgd_override", batch.lgd_overrides),
    ):
        mask = ~np.isnan(values)
        if bool(np.any(mask & ~np.isfinite(values))):
            raise DrcInputError(f"{field_name} values must be finite when present")
    if bool(np.any(~batch.lineage_present)):
        raise DrcInputError("lineage is required")
    _raise_first_mismatch(
        batch.lineage_source_systems,
        "",
        mismatch_when_equal=True,
        message=lambda _index: "lineage.source_system must be non-empty",
    )
    _raise_first_mismatch(
        batch.lineage_source_files,
        "",
        mismatch_when_equal=True,
        message=lambda _index: "lineage.source_file must be non-empty",
    )


def _validate_nonsec_batch(batch: DrcPositionBatch, *, profile_id: str) -> None:
    if np.any(batch.issuer_ids == None):  # noqa: E711
        raise DrcInputError("issuer_id is required for non-securitisation DRC batch")
    if np.any(batch.seniorities == None):  # noqa: E711
        raise DrcInputError("seniority is required for non-securitisation DRC batch")
    if np.any(batch.credit_qualities == None):  # noqa: E711
        raise DrcInputError("credit_quality is required for non-securitisation DRC batch")
    bucket_mask = np.isin(
        batch.bucket_keys,
        chargeable_non_securitisation_bucket_keys(profile_id=profile_id),
    )
    if not bool(np.all(bucket_mask)):
        first = int(np.argmax(~bucket_mask))
        ensure_chargeable_non_securitisation_bucket(
            cast(str, batch.bucket_keys[first]),
            position_id=cast(str, batch.position_ids[first]),
            profile_id=profile_id,
        )
    for quality in sorted(set(cast(str, item) for item in batch.credit_qualities.tolist())):
        first = int(np.argmax(batch.credit_qualities == quality))
        ensure_chargeable_credit_quality(
            quality,
            position_id=cast(str, batch.position_ids[first]),
            profile_id=profile_id,
        )


def _validate_securitisation_non_ctp_batch(batch: DrcPositionBatch) -> None:
    if np.any(batch.tranche_ids == None):  # noqa: E711
        raise DrcInputError("tranche_id is required for securitisation non-CTP DRC batch")
    bucket_mask = np.isin(
        batch.bucket_keys,
        chargeable_securitisation_non_ctp_bucket_keys(),
    )
    if not bool(np.all(bucket_mask)):
        first = int(np.argmax(~bucket_mask))
        ensure_chargeable_securitisation_non_ctp_bucket(
            cast(str, batch.bucket_keys[first]),
            position_id=cast(str, batch.position_ids[first]),
        )
    _validate_market_value_default_exposure_batch(
        batch,
        risk_class_label="securitisation non-CTP",
    )


def _validate_ctp_batch(batch: DrcPositionBatch) -> None:
    missing_identity = (
        (batch.tranche_ids == None)  # noqa: E711
        & (batch.index_series_ids == None)  # noqa: E711
        & (batch.issuer_ids == None)  # noqa: E711
    )
    if bool(np.any(missing_identity)):
        first = int(np.nonzero(missing_identity)[0][0])
        raise DrcInputError(
            "CTP positions require tranche_id, index_series_id, or issuer_id: "
            f"{batch.position_ids[first]}"
        )
    _validate_market_value_default_exposure_batch(batch, risk_class_label="CTP")


def _validate_market_value_default_exposure_batch(
    batch: DrcPositionBatch,
    *,
    risk_class_label: str,
) -> None:
    missing_market_value = np.isnan(batch.market_values)
    if bool(np.any(missing_market_value)):
        first = int(np.nonzero(missing_market_value)[0][0])
        raise DrcInputError(
            f"{risk_class_label} position {batch.position_ids[first]} requires market_value"
        )
    if bool(np.any(~np.isnan(batch.lgd_overrides))):
        raise DrcInputError(
            f"{risk_class_label} gross JTD uses market value; lgd_override is not supported"
        )


def _gross_jtd_array(
    batch: DrcPositionBatch,
    *,
    profile_id: str,
) -> tuple[FloatArray, tuple[str, ...]]:
    if bool(np.any(~np.isnan(batch.lgd_overrides))):
        raise DrcInputError("explicit LGD overrides are not supported by the selected profile")

    lgd_rates, citations = _lgd_rate_array(batch, profile_id=profile_id)
    pnl_component = np.empty(batch.row_count, dtype=np.float64)
    has_cumulative = ~np.isnan(batch.cumulative_pnls)
    pnl_component[has_cumulative] = batch.cumulative_pnls[has_cumulative]
    missing_pnl = ~has_cumulative & np.isnan(batch.market_values)
    if bool(np.any(missing_pnl)):
        first = int(np.nonzero(missing_pnl)[0][0])
        raise DrcInputError(
            f"cumulative_pnl or market_value is required for gross JTD: {batch.position_ids[first]}"
        )
    market_indices = ~has_cumulative
    notionals_abs = np.abs(batch.notionals)
    long_mask = batch.default_directions == DefaultDirection.LONG.value
    pnl_component[market_indices & long_mask] = (
        batch.market_values[market_indices & long_mask] - notionals_abs[market_indices & long_mask]
    )
    pnl_component[market_indices & ~long_mask] = (
        notionals_abs[market_indices & ~long_mask]
        - batch.market_values[market_indices & ~long_mask]
    )

    signed_notional = np.where(long_mask, notionals_abs, -notionals_abs)
    raw_jtd = lgd_rates * signed_notional + pnl_component
    gross = np.where(long_mask, np.maximum(raw_jtd, 0.0), np.abs(np.minimum(raw_jtd, 0.0)))
    return gross.astype(np.float64), citations


def _lgd_rate_array(
    batch: DrcPositionBatch,
    *,
    profile_id: str,
) -> tuple[FloatArray, tuple[str, ...]]:
    rule_by_seniority = {
        rule.seniority.value: rule for rule in iter_lgd_rules(profile_id=profile_id)
    }

    lgd_rates = np.empty(batch.row_count, dtype=np.float64)
    citations: set[str] = set()

    defaulted_mask = batch.is_defaulted
    if bool(np.any(defaulted_mask)):
        defaulted_rule = get_lgd_rule(
            DrcSeniority.EQUITY,
            profile_id=profile_id,
            is_defaulted=True,
        )
        lgd_rates[defaulted_mask] = defaulted_rule.lgd_rate
        citations.add(defaulted_rule.citation_id)

    non_defaulted_mask = ~defaulted_mask
    for seniority_value in np.unique(batch.seniorities[non_defaulted_mask]):
        seniority_text = cast(str, seniority_value)
        try:
            rule = rule_by_seniority[seniority_text]
        except KeyError as exc:
            raise DrcInputError(f"missing DRC LGD rule: {profile_id}/{seniority_text}") from exc
        seniority_mask = non_defaulted_mask & (batch.seniorities == seniority_text)
        lgd_rates[seniority_mask] = rule.lgd_rate
        citations.add(rule.citation_id)

    return lgd_rates, tuple(sorted(citations))


def _scaled_jtd_array(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    *,
    profile_id: str,
) -> tuple[FloatArray, FloatArray, str]:
    policy = get_maturity_policy(profile_id)
    effective_maturity = np.maximum(batch.maturity_years, policy.floor_years)
    weights = np.where(
        batch.maturity_years >= policy.full_weight_years,
        1.0,
        effective_maturity / policy.full_weight_years,
    )
    return weights.astype(np.float64), (gross_jtd * weights).astype(np.float64), policy.citation_id


def _market_value_gross_jtd_array(batch: DrcPositionBatch) -> FloatArray:
    return np.abs(batch.market_values).astype(np.float64)


def _securitisation_non_ctp_gross_jtd_array(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> FloatArray:
    gross_jtd = _market_value_gross_jtd_array(batch)
    evidence = context.securitisation_non_ctp_fair_value_cap_evidence
    if not evidence:
        return gross_jtd
    capped = gross_jtd.copy()
    for index in range(batch.row_count):
        position_id = cast(str, batch.position_ids[index])
        record = evidence.get(position_id)
        if record is None or not record.eligible:
            continue
        if record.fair_value_cap_amount is None:  # pragma: no cover - context validation enforces.
            raise DrcInputError(
                f"fair_value_cap_evidence[{position_id}].fair_value_cap_amount is required"
            )
        capped[index] = min(float(capped[index]), record.fair_value_cap_amount)
    return capped.astype(np.float64)


def _capital_inputs(
    batch: DrcPositionBatch,
    net_jtds: tuple[NetJtd, ...],
) -> tuple[CapitalInput, ...]:
    credit_quality_by_position = {
        cast(str, batch.position_ids[index]): CreditQuality(
            cast(str, batch.credit_qualities[index])
        )
        for index in range(batch.row_count)
    }
    return tuple(
        CapitalInput(
            net_jtd=net_jtd,
            credit_quality=_credit_quality_for_net_jtd(net_jtd, credit_quality_by_position),
        )
        for net_jtd in net_jtds
    )


def _securitisation_non_ctp_capital_inputs_from_batch(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[SecuritisationNonCtpCapitalInput, ...]:
    inputs: list[SecuritisationNonCtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(
            sorted(
                _risk_weights_for_net_jtd(
                    net_jtd,
                    risk_weights=risk_weights,
                    field_name="context.securitisation_non_ctp_risk_weights",
                )
            )
        )
        if len(weights) != 1:
            raise DrcInputError(
                "securitisation non-CTP net JTD must map to exactly one risk weight: "
                f"{net_jtd.net_jtd_id}"
            )
        inputs.append(SecuritisationNonCtpCapitalInput(net_jtd=net_jtd, risk_weight=weights[0]))
    return tuple(inputs)


def _ctp_capital_inputs_from_batch(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[CtpCapitalInput, ...]:
    inputs: list[CtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(
            sorted(
                _risk_weights_for_net_jtd(
                    net_jtd,
                    risk_weights=risk_weights,
                    field_name="context.ctp_risk_weights",
                )
            )
        )
        if len(weights) != 1:
            raise DrcInputError(
                f"CTP net JTD must map to exactly one risk weight: {net_jtd.net_jtd_id}"
            )
        inputs.append(CtpCapitalInput(net_jtd=net_jtd, risk_weight=weights[0]))
    return tuple(inputs)


def _coerce_finite_non_negative_float(value: object, *, field_name: str) -> float:
    try:
        result = float(cast(Any, value))
    except (ValueError, TypeError) as exc:
        raise DrcInputError(f"{field_name} must be a valid finite number") from exc
    if not math.isfinite(result) or result < 0.0:
        raise DrcInputError(f"{field_name} must be finite and non-negative")
    return result


def _credit_quality_for_net_jtd(
    net_jtd: NetJtd,
    credit_quality_by_position: Mapping[str, CreditQuality],
) -> CreditQuality:
    credit_qualities = {
        credit_quality_by_position[position_id] for position_id in net_jtd.position_ids
    }
    if len(credit_qualities) != 1:
        raise DrcInputError(f"net JTD must map to exactly one credit quality: {net_jtd.net_jtd_id}")
    return next(iter(credit_qualities))


def _zero_nonsec_category(profile_id: str) -> CategoryDrc:
    return CategoryDrc(
        category_id="category-drc-non-securitisation",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(),
        capital=0.0,
        branch_metadata=(
            BranchMetadata(
                branch_id="category-non-securitisation-zero",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.NON_SECURITISATION.value,
                selected=True,
                reason="all supported net JTD records are zero",
                citations=(_zero_nonsec_category_citation(profile_id),),
            ),
        ),
    )


def _collect_batch_citations(
    batch: DrcPositionBatch,
    *,
    category: CategoryDrc,
    net_jtds: tuple[NetJtd, ...],
    formula_citations: tuple[str, ...],
    profile_id: str,
    fx_citations: tuple[str, ...] = (),
) -> tuple[str, ...]:
    citation_ids = {*formula_citations, *fx_citations}
    if profile_id == US_NPR_2_0_PROFILE_ID:
        citation_ids.add("US_NPR_210_SCOPE")
    for group in batch.citation_ids:
        citation_ids.update(group)
    citation_ids.update(_branch_citations(category.branch_metadata))
    for bucket in category.bucket_results:
        citation_ids.update(bucket.citations)
        citation_ids.update(bucket.hbr.citations)
        citation_ids.update(_branch_citations(bucket.branch_metadata))
        citation_ids.update(_branch_citations(bucket.hbr.branch_metadata))
    for net_jtd in net_jtds:
        citation_ids.update(_branch_citations(net_jtd.branch_metadata))
        for rejected_offset in net_jtd.rejected_offsets:
            citation_ids.update(rejected_offset.citations)
    return tuple(sorted(citation_ids))


def _batch_api_citations(profile_id: str, risk_class: DrcRiskClass) -> tuple[str, ...]:
    if profile_id == EU_CRR3_PROFILE_ID and risk_class is DrcRiskClass.NON_SECURITISATION:
        return (
            "EU_CRR3_ARTICLE_325W",
            "EU_CRR3_ARTICLE_325X",
            "EU_CRR3_ARTICLE_325Y_1_2",
            "EU_CRR3_ARTICLE_325Y_3_5",
            "EU_CRR3_ARTICLE_325Y_6",
            "EU_CRR3_ECAI_CQS_MAPPING",
        )
    if profile_id == BASEL_MAR22_PROFILE_ID and risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return _BASEL_SEC_NON_CTP_BATCH_CITATIONS
    if (
        profile_id == BASEL_MAR22_PROFILE_ID
        and risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
    ):
        return _BASEL_CTP_BATCH_CITATIONS
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return ()
    if profile_id == EU_CRR3_PROFILE_ID:
        return ()
    return ("US_NPR_210_SCOPE",)


def _nonsec_formula_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_FORMULA_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_FORMULA_CITATIONS
    return _US_NPR_FORMULA_CITATIONS


def _nonsec_netting_citation(profile_id: str) -> str:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_NETTING_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_NETTING_CITATION
    return _US_NPR_NETTING_CITATION


def _zero_nonsec_category_citation(profile_id: str) -> str:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_ZERO_CATEGORY_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_ZERO_CATEGORY_CITATION
    return _US_NPR_ZERO_CATEGORY_CITATION


def _batch_risk_weights_by_position(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> dict[str, float]:
    if risk_class == DrcRiskClass.NON_SECURITISATION:
        weights: dict[str, float] = {}
        for index in _sorted_indices(batch):
            position_id = cast(str, batch.position_ids[index])
            weights[position_id] = get_risk_weight_rule(
                cast(str, batch.bucket_keys[index]),
                CreditQuality(cast(str, batch.credit_qualities[index])),
                profile_id=context.profile_id,
            ).risk_weight
        return weights
    if risk_class == DrcRiskClass.SECURITISATION_NON_CTP:
        return dict(
            effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            )
        )
    if risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return dict(
            effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            )
        )
    return {}


def _batch_fair_value_cap_citations(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> tuple[str, ...]:
    citation_ids: set[str] = set()
    for position_id in batch.position_ids:
        evidence = context.securitisation_non_ctp_fair_value_cap_evidence.get(
            cast(str, position_id)
        )
        if evidence is not None:
            citation_ids.update(_sec_non_ctp_fair_value_cap_citations(context.profile_id))
            citation_ids.update(evidence.citation_ids)
    return tuple(sorted(citation_ids))


def _fair_value_cap_branch_metadata_for_batch(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> tuple[BranchMetadata, ...]:
    if risk_class is not DrcRiskClass.SECURITISATION_NON_CTP:
        return ()
    gross_jtd = _market_value_gross_jtd_array(batch)
    branches: list[BranchMetadata] = []
    evidence = context.securitisation_non_ctp_fair_value_cap_evidence
    if not evidence:
        return (
            BranchMetadata(
                branch_id="drc-securitisation-non-ctp-batch-no-fair-value-cap",
                branch_type=BranchType.NORMAL,
                source_id=context.profile_id,
                selected=True,
                reason=(
                    "batch securitisation non-CTP gross default exposure used market value; "
                    "no fair-value cap evidence was supplied"
                ),
                citations=_sec_non_ctp_gross_citations(context.profile_id),
            ),
        )
    for index in _sorted_indices(batch):
        position_id = cast(str, batch.position_ids[index])
        record = evidence.get(position_id)
        if record is None:
            branches.append(
                BranchMetadata(
                    branch_id=f"batch-sec-non-ctp-no-fair-value-cap-{_slug(position_id)}",
                    branch_type=BranchType.NORMAL,
                    source_id=position_id,
                    selected=True,
                    reason=(
                        "batch securitisation non-CTP position used market value; "
                        "no fair-value cap evidence was supplied"
                    ),
                    citations=_sec_non_ctp_gross_citations(context.profile_id),
                )
            )
            continue
        citations = tuple(
            sorted(
                {
                    *_sec_non_ctp_fair_value_cap_citations(context.profile_id),
                    *record.citation_ids,
                }
            )
        )
        if not record.eligible:
            branch_type = BranchType.NORMAL
            reason = (
                "batch fair-value cap evidence marked the position ineligible; "
                f"reason: {record.eligibility_reason}"
            )
        elif record.fair_value_cap_amount is not None and record.fair_value_cap_amount < float(
            gross_jtd[index]
        ):
            branch_type = BranchType.CAP
            reason = (
                "batch fair-value cap applied to securitisation non-CTP gross default "
                f"exposure: market_value={float(gross_jtd[index])}, "
                f"cap_amount={record.fair_value_cap_amount}"
            )
        else:
            branch_type = BranchType.NORMAL
            reason = (
                "batch fair-value cap evidence was eligible but not binding: "
                f"market_value={float(gross_jtd[index])}, "
                f"cap_amount={record.fair_value_cap_amount}"
            )
        branches.append(
            BranchMetadata(
                branch_id=f"batch-sec-non-ctp-fair-value-cap-{_slug(position_id)}",
                branch_type=branch_type,
                source_id=record.source_id,
                selected=True,
                reason=reason,
                citations=citations,
            )
        )
    return tuple(branches)


def _sec_non_ctp_gross_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_GROSS_CITATIONS
    return _SEC_NON_CTP_GROSS_CITATIONS


def _sec_non_ctp_fair_value_cap_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS
    return _SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS


def _sec_non_ctp_netting_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_NETTING_CITATIONS
    return _SEC_NON_CTP_NETTING_CITATIONS


def _sec_non_ctp_batch_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_BATCH_CITATIONS
    return _SEC_NON_CTP_BATCH_CITATIONS


def _ctp_netting_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_CTP_NETTING_CITATIONS
    return _CTP_NETTING_CITATIONS


def _ctp_batch_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_CTP_BATCH_CITATIONS
    return _CTP_BATCH_CITATIONS


def _branch_citations(branches: tuple[BranchMetadata, ...]) -> set[str]:
    citation_ids: set[str] = set()
    for branch in branches:
        citation_ids.update(branch.citations)
    return citation_ids


def _raise_first_mismatch(
    values: ObjectArray,
    expected: str,
    *,
    mismatch_when_equal: bool = False,
    message: Callable[[int], str],
) -> None:
    mismatch = values == expected if mismatch_when_equal else values != expected
    if bool(np.any(mismatch)):
        index = int(np.nonzero(mismatch)[0][0])
        raise DrcInputError(message(index))


def _sorted_indices(batch: DrcPositionBatch) -> tuple[int, ...]:
    return tuple(
        sorted(
            range(batch.row_count),
            key=lambda index: (
                cast(str, batch.position_ids[index]),
                cast(str, batch.source_row_ids[index]),
            ),
        )
    )


from frtb_drc.adapters.positions import (  # noqa: E402, I001
    build_drc_ctp_batch_from_columns,
    build_drc_nonsec_batch_from_columns,
    build_drc_nonsec_batch_from_positions,
    build_drc_securitisation_non_ctp_batch_from_columns,
)


__all__ = [
    "DrcBatchCapitalCalculation",
    "DrcPositionBatch",
    "build_drc_ctp_batch_from_columns",
    "build_drc_nonsec_batch_from_columns",
    "build_drc_nonsec_batch_from_positions",
    "build_drc_securitisation_non_ctp_batch_from_columns",
    "calculate_drc_capital_from_batch",
    "input_hash_for_drc_batch",
]
