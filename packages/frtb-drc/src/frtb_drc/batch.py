"""Package-owned DRC batches for high-volume DRC kernels."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np

from frtb_drc._batch_columns import BoolArray, FloatArray, ObjectArray
from frtb_drc._identifiers import slug_path as _slug
from frtb_drc._netting_helpers import (
    risk_weights_for_net_jtd as _risk_weights_for_net_jtd,
)
from frtb_drc._version import __version__
from frtb_drc.assembly.citations import (
    batch_api_citations as _batch_api_citations,
)
from frtb_drc.assembly.citations import (
    collect_batch_citations as _collect_batch_citations,
)
from frtb_drc.assembly.citations import (
    ctp_batch_citations as _ctp_batch_citations,
)
from frtb_drc.assembly.citations import (
    ctp_netting_citations as _ctp_netting_citations,
)
from frtb_drc.assembly.citations import (
    nonsec_formula_citations as _nonsec_formula_citations,
)
from frtb_drc.assembly.citations import (
    nonsec_netting_citation as _nonsec_netting_citation,
)
from frtb_drc.assembly.citations import (
    sec_non_ctp_batch_citations as _sec_non_ctp_batch_citations,
)
from frtb_drc.assembly.citations import (
    sec_non_ctp_netting_citations as _sec_non_ctp_netting_citations,
)
from frtb_drc.assembly.citations import (
    zero_nonsec_category_citation as _zero_nonsec_category_citation,
)
from frtb_drc.assembly.fair_value_cap import (
    batch_fair_value_cap_citations as _batch_fair_value_cap_citations,
)
from frtb_drc.assembly.fair_value_cap import (
    fair_value_cap_branch_metadata_for_batch as _fair_value_cap_branch_metadata_for_batch,
)
from frtb_drc.assembly.hashes import (
    context_input_hash_for_drc_batch as _context_input_hash_for_batch,
)
from frtb_drc.assembly.hashes import input_hash_for_drc_batch
from frtb_drc.attribution import calculate_drc_attribution
from frtb_drc.audit import validate_reconciliation
from frtb_drc.batch_validation import (
    batch_risk_class as _batch_risk_class,
)
from frtb_drc.batch_validation import (
    validate_batch_context as _validate_context,
)
from frtb_drc.batch_validation import (
    validate_supported_batch_run as _validate_supported_batch_run,
)
from frtb_drc.capital import CapitalInput, calculate_category_drc
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
)
from frtb_drc.fx import (
    fx_branch_metadata,
    fx_citation_ids,
    fx_conversion_records,
    input_hash_with_fx,
    require_fx_rate,
)
from frtb_drc.kernel import net_jtd as _net_jtd_kernel
from frtb_drc.kernel.ctp import CtpCapitalInput, calculate_ctp_category_drc
from frtb_drc.kernel.securitisation import (
    SecuritisationNonCtpCapitalInput,
    calculate_securitisation_non_ctp_category_drc,
)
from frtb_drc.reference_data import (
    get_lgd_rule,
    get_maturity_policy,
    get_risk_weight_rule,
    iter_lgd_rules,
)
from frtb_drc.regimes import get_rule_profile
from frtb_drc.risk_weight_evidence import (
    effective_risk_weights,
    used_risk_weight_evidence_for_position_ids,
)
from frtb_drc.validation import DrcInputError


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
    )


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
