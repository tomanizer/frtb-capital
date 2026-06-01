"""
Non-GIRR vega assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.90-MAR21.95 — vega buckets, weights, and correlations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
    select_max_correlation_scenario,
)
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.commodity_reference_data import (
    commodity_delta_intra_bucket_correlation,
)
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_OTHER_SECTOR_BUCKET,
    csr_nonsec_delta_intra_bucket_correlation,
)
from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_delta_intra_bucket_correlation
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_OTHER_SECTOR_BUCKET,
    csr_sec_nonctp_delta_intra_bucket_correlation,
)
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    BucketCapital,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.equity_reference_data import (
    EQUITY_OTHER_SECTOR_BUCKET,
    EQUITY_SPOT_RISK_FACTOR,
    equity_delta_intra_bucket_correlation,
)
from frtb_sbm.reference_data import (
    fx_delta_intra_bucket_correlation,
    vega_option_tenor_correlation,
)
from frtb_sbm.risk_classes.commodity import build_commodity_inter_bucket_correlation_map
from frtb_sbm.risk_classes.csr_nonsec import build_csr_nonsec_inter_bucket_correlation_map
from frtb_sbm.risk_classes.csr_sec_nonctp import (
    build_csr_sec_nonctp_inter_bucket_correlation_map,
)
from frtb_sbm.risk_classes.equity import build_equity_inter_bucket_correlation_map
from frtb_sbm.risk_classes.fx import build_fx_inter_bucket_correlation_map
from frtb_sbm.validation import SbmInputError
from frtb_sbm.weighted_sensitivity import (
    weight_non_girr_vega_sensitivities,
    weight_non_girr_vega_sensitivity_batch,
)

_NON_GIRR_VEGA_RISK_CLASSES = frozenset(
    {
        SbmRiskClass.FX,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
    }
)

_MAR21_VEGA_INTRA_CITATION = ("basel_mar21_4_intra_bucket", "basel_mar21_94")
_MAR21_VEGA_INTER_CITATION = ("basel_mar21_4_inter_bucket", "basel_mar21_95")
_MAR21_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)
_VEGA_NEUTRAL_TENOR = "1y"
_VEGA_NEUTRAL_LOCATION = "__VEGA_NO_DELIVERY_LOCATION__"


def calculate_non_girr_vega_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited non-GIRR vega risk-class capital for a supported profile."""

    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    risk_classes = {item.risk_class for item in sensitivities}
    if len(risk_classes) != 1:
        raise UnsupportedNonGirrVegaPathError("non-GIRR vega requires homogeneous risk class")
    risk_class = next(iter(risk_classes))
    if risk_class not in _NON_GIRR_VEGA_RISK_CLASSES:
        raise UnsupportedNonGirrVegaPathError(
            f"non-GIRR vega does not support risk_class={risk_class.value}"
        )
    weighted = weight_non_girr_vega_sensitivities(
        sensitivities,
        profile_id=profile_id,
    )
    return aggregate_non_girr_vega_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_class=risk_class,
        risk_factor_by_id=_text_by_id(sensitivities, "risk_factor"),
        qualifier_by_id=_optional_text_by_id(sensitivities, "qualifier"),
        option_tenor_by_id=_optional_text_by_id(sensitivities, "option_tenor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_non_girr_vega_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited non-GIRR vega risk-class capital from a package-owned batch."""

    if batch.row_count == 0:
        raise SbmInputError("batch must not be empty", field="batch")
    risk_class = batch.risk_class
    if risk_class not in _NON_GIRR_VEGA_RISK_CLASSES:
        raise UnsupportedNonGirrVegaPathError(
            f"non-GIRR vega does not support risk_class={risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise UnsupportedNonGirrVegaPathError(
            f"non-GIRR vega does not support risk_measure={batch.risk_measure.value}"
        )
    weighted = weight_non_girr_vega_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    return aggregate_non_girr_vega_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_class=risk_class,
        risk_factor_by_id=_batch_text_by_id(batch, batch.risk_factors, "risk_factor"),
        qualifier_by_id=_batch_optional_text_by_id(batch, batch.qualifiers),
        option_tenor_by_id=_batch_required_text_by_id(batch, batch.option_tenors, "option_tenor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_non_girr_vega_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted non-GIRR vega sensitivities through shared primitives."""

    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return _aggregate_csr_sec_nonctp_vega_measure_capital(
            weighted,
            profile_id=profile_id,
            risk_factor_by_id=risk_factor_by_id,
            qualifier_by_id=qualifier_by_id,
            option_tenor_by_id=option_tenor_by_id,
            pairwise_evidence_mode=pairwise_evidence_mode,
            pairwise_evidence_limit=pairwise_evidence_limit,
        )

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        absolute = _uses_absolute_weight_intra_bucket(risk_class, bucket_id)
        matrix = build_non_girr_vega_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            risk_class=risk_class,
            bucket_id=bucket_id,
            risk_factor_by_id=risk_factor_by_id,
            qualifier_by_id=qualifier_by_id,
            option_tenor_by_id=option_tenor_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                absolute_weight_intra=absolute,
                absolute_weight_citation_ids=_absolute_weight_citations(risk_class, bucket_id)
                if absolute
                else (),
            )
        )

    bucket_ids = tuple(spec.bucket_id for spec in intra_specs)
    inter_bucket_correlations = build_non_girr_vega_inter_bucket_correlation_map(
        risk_class,
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.VEGA,
        intra_bucket_citation_ids=_intra_bucket_citations(risk_class),
        inter_bucket_citation_ids=_inter_bucket_citations(risk_class),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def build_non_girr_vega_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return MAR21.94 non-GIRR vega intra-bucket correlations."""

    size = len(ordered)
    if size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    if _uses_absolute_weight_intra_bucket(risk_class, bucket_id):
        return np.eye(size, dtype=np.float64)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = non_girr_vega_intra_bucket_correlation(
                profile_id,
                risk_class=risk_class,
                bucket_id=bucket_id,
                risk_factor_a=_lookup_axis(
                    risk_factor_by_id,
                    sensitivity_a.sensitivity_id,
                    "risk_factor",
                ),
                risk_factor_b=_lookup_axis(
                    risk_factor_by_id,
                    sensitivity_b.sensitivity_id,
                    "risk_factor",
                ),
                qualifier_a=qualifier_by_id.get(sensitivity_a.sensitivity_id, ""),
                qualifier_b=qualifier_by_id.get(sensitivity_b.sensitivity_id, ""),
                option_tenor_a=_lookup_axis(
                    option_tenor_by_id,
                    sensitivity_a.sensitivity_id,
                    "option_tenor",
                ),
                option_tenor_b=_lookup_axis(
                    option_tenor_by_id,
                    sensitivity_b.sensitivity_id,
                    "option_tenor",
                ),
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def non_girr_vega_intra_bucket_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_a: str,
    risk_factor_b: str,
    qualifier_a: str = "",
    qualifier_b: str = "",
    option_tenor_a: str,
    option_tenor_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return min(1, corresponding delta rho * option-tenor rho) per MAR21.94."""

    delta_correlation, delta_citations = _corresponding_delta_correlation(
        profile_id,
        risk_class=risk_class,
        bucket_id=bucket_id,
        risk_factor_a=risk_factor_a,
        risk_factor_b=risk_factor_b,
        qualifier_a=qualifier_a,
        qualifier_b=qualifier_b,
    )
    option_correlation, option_citations = vega_option_tenor_correlation(
        profile_id,
        option_tenor1=option_tenor_a,
        option_tenor2=option_tenor_b,
    )
    return (
        min(1.0, delta_correlation * option_correlation),
        _merge_citation_ids(_MAR21_VEGA_INTRA_CITATION, delta_citations, option_citations),
    )


def build_non_girr_vega_inter_bucket_correlation_map(
    risk_class: SbmRiskClass,
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return MAR21.95 vega inter-bucket correlations from delta gamma tables."""

    if risk_class is SbmRiskClass.FX:
        return build_fx_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.EQUITY:
        return build_equity_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.COMMODITY:
        return build_commodity_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return build_csr_nonsec_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return build_csr_nonsec_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return build_csr_sec_nonctp_inter_bucket_correlation_map(
            bucket_ids,
            profile_id=profile_id,
        )
    raise UnsupportedNonGirrVegaPathError(
        f"non-GIRR vega inter-bucket correlations do not support {risk_class.value}"
    )


class UnsupportedNonGirrVegaPathError(SbmInputError):
    """Raised for inconsistent non-GIRR vega path requests."""


def _aggregate_csr_sec_nonctp_vega_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    grouped = group_weighted_sensitivities_by_bucket(weighted)
    core_specs: list[IntraBucketScenarioSpec] = []
    other_spec: IntraBucketScenarioSpec | None = None
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_non_girr_vega_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket_id=bucket_id,
            risk_factor_by_id=risk_factor_by_id,
            qualifier_by_id=qualifier_by_id,
            option_tenor_by_id=option_tenor_by_id,
        )
        spec = IntraBucketScenarioSpec(
            bucket_id=bucket_id,
            weighted_sensitivities=tuple(bucket_weighted),
            base_correlation_matrix=matrix,
            absolute_weight_intra=bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET,
            absolute_weight_citation_ids=_absolute_weight_citations(
                SbmRiskClass.CSR_SEC_NONCTP,
                bucket_id,
            )
            if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET
            else (),
        )
        if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
            other_spec = spec
        else:
            core_specs.append(spec)

    scenario_labels = (
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    )
    scenario_totals: dict[SbmScenarioLabel, float] = {}
    scenario_details: list[RiskClassScenarioDetail] = []
    selected_buckets: tuple[BucketCapital, ...] = ()
    for scenario in scenario_labels:
        core_capital = 0.0
        core_buckets: tuple[BucketCapital, ...] = ()
        core_details: tuple[RiskClassScenarioDetail, ...] = ()
        if core_specs:
            inter_map = build_csr_sec_nonctp_inter_bucket_correlation_map(
                tuple(spec.bucket_id for spec in core_specs),
                profile_id=profile_id,
            )
            core_result = aggregate_risk_class_with_scenarios(
                tuple(core_specs),
                inter_map,
                risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                risk_measure=SbmRiskMeasure.VEGA,
                scenarios=(scenario,),
                apply_scenario_adjustment=True,
                intra_bucket_citation_ids=_intra_bucket_citations(SbmRiskClass.CSR_SEC_NONCTP),
                inter_bucket_citation_ids=_inter_bucket_citations(SbmRiskClass.CSR_SEC_NONCTP),
                pairwise_evidence_mode=pairwise_evidence_mode,
                pairwise_evidence_limit=pairwise_evidence_limit,
            )
            core_capital = core_result.selected_capital
            core_buckets = core_result.buckets
            core_details = core_result.scenario_details

        other_capital = 0.0
        other_buckets: tuple[BucketCapital, ...] = ()
        other_details: tuple[RiskClassScenarioDetail, ...] = ()
        if other_spec is not None:
            other_result = aggregate_risk_class_with_scenarios(
                (other_spec,),
                {},
                risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                risk_measure=SbmRiskMeasure.VEGA,
                scenarios=(scenario,),
                apply_scenario_adjustment=False,
                intra_bucket_citation_ids=_absolute_weight_citations(
                    SbmRiskClass.CSR_SEC_NONCTP,
                    other_spec.bucket_id,
                ),
                inter_bucket_citation_ids=_inter_bucket_citations(SbmRiskClass.CSR_SEC_NONCTP),
                pairwise_evidence_mode=pairwise_evidence_mode,
                pairwise_evidence_limit=pairwise_evidence_limit,
            )
            other_capital = other_result.selected_capital
            other_buckets = other_result.buckets
            other_details = other_result.scenario_details

        scenario_totals[scenario] = core_capital + other_capital
        if scenario is SbmScenarioLabel.MEDIUM:
            selected_buckets = core_buckets + other_buckets
        core_detail = core_details[0] if core_details else None
        other_detail = other_details[0] if other_details else None
        scenario_details.append(
            RiskClassScenarioDetail(
                scenario=scenario,
                capital=core_capital + other_capital,
                inter_bucket_correlations=(
                    (core_detail.inter_bucket_correlations if core_detail else ())
                    + (other_detail.inter_bucket_correlations if other_detail else ())
                ),
                alternative_sb_used=(
                    (core_detail.alternative_sb_used if core_detail else False)
                    or (other_detail.alternative_sb_used if other_detail else False)
                ),
                intra_buckets=(
                    (core_detail.intra_buckets if core_detail else ())
                    + (other_detail.intra_buckets if other_detail else ())
                ),
                citation_ids=_MAR21_SCENARIO_CITATION,
            )
        )

    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.VEGA,
        citation_ids=("basel_mar21_7_scenario_selection",),
    )
    return RiskClassCapital(
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.VEGA,
        selected_capital=selection.selected_capital,
        buckets=selected_buckets,
        citation_ids=_merge_citation_ids(
            _MAR21_SCENARIO_CITATION,
            _intra_bucket_citations(SbmRiskClass.CSR_SEC_NONCTP),
            _inter_bucket_citations(SbmRiskClass.CSR_SEC_NONCTP),
        ),
        scenario_totals=selection.scenario_totals,
        selected_scenario=selection.selected_scenario,
        scenario_details=tuple(scenario_details),
        scenario_selection=selection.branch_metadata,
    )


def _corresponding_delta_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_a: str,
    risk_factor_b: str,
    qualifier_a: str,
    qualifier_b: str,
) -> tuple[float, tuple[str, ...]]:
    if risk_class is SbmRiskClass.FX:
        return fx_delta_intra_bucket_correlation(
            profile_id,
            bucket1=bucket_id,
            bucket2=bucket_id,
        )
    if risk_class is SbmRiskClass.EQUITY:
        return equity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
            risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
            issuer_a=qualifier_a,
            issuer_b=qualifier_b,
        )
    if risk_class is SbmRiskClass.COMMODITY:
        return commodity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            commodity_a=risk_factor_a,
            commodity_b=risk_factor_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
            location_a=_VEGA_NEUTRAL_LOCATION,
            location_b=_VEGA_NEUTRAL_LOCATION,
        )
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return csr_nonsec_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            risk_factor_a=risk_factor_a,
            risk_factor_b=risk_factor_b,
            issuer_a=qualifier_a,
            issuer_b=qualifier_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
        )
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return csr_sec_nonctp_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            tranche_a=qualifier_a,
            tranche_b=qualifier_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
            risk_factor_a=risk_factor_a,
            risk_factor_b=risk_factor_b,
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return csr_sec_ctp_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            name_a=qualifier_a,
            name_b=qualifier_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
            risk_factor_a=risk_factor_a,
            risk_factor_b=risk_factor_b,
        )
    raise UnsupportedNonGirrVegaPathError(
        f"non-GIRR vega intra-bucket correlations do not support {risk_class.value}"
    )


def _uses_absolute_weight_intra_bucket(risk_class: SbmRiskClass, bucket_id: str) -> bool:
    if risk_class is SbmRiskClass.EQUITY:
        return bucket_id == EQUITY_OTHER_SECTOR_BUCKET
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return bucket_id == CSR_OTHER_SECTOR_BUCKET
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET
    return False


def _absolute_weight_citations(risk_class: SbmRiskClass, bucket_id: str) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.EQUITY and bucket_id == EQUITY_OTHER_SECTOR_BUCKET:
        return ("basel_mar21_79",)
    if risk_class is SbmRiskClass.CSR_NONSEC and bucket_id == CSR_OTHER_SECTOR_BUCKET:
        return ("basel_mar21_56",)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP and bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
        return ("basel_mar21_68",)
    return ()


def _intra_bucket_citations(risk_class: SbmRiskClass) -> tuple[str, ...]:
    delta_citation_by_class = {
        SbmRiskClass.FX: ("basel_mar21_86",),
        SbmRiskClass.EQUITY: ("basel_mar21_78", "basel_mar21_79"),
        SbmRiskClass.COMMODITY: ("basel_mar21_83",),
        SbmRiskClass.CSR_NONSEC: ("basel_mar21_54", "basel_mar21_55", "basel_mar21_56"),
        SbmRiskClass.CSR_SEC_NONCTP: ("basel_mar21_67", "basel_mar21_68"),
        SbmRiskClass.CSR_SEC_CTP: ("basel_mar21_58",),
    }
    return _merge_citation_ids(
        _MAR21_VEGA_INTRA_CITATION,
        delta_citation_by_class.get(risk_class, ()),
    )


def _inter_bucket_citations(risk_class: SbmRiskClass) -> tuple[str, ...]:
    delta_citation_by_class = {
        SbmRiskClass.FX: ("basel_mar21_89",),
        SbmRiskClass.EQUITY: ("basel_mar21_80",),
        SbmRiskClass.COMMODITY: ("basel_mar21_85",),
        SbmRiskClass.CSR_NONSEC: ("basel_mar21_57",),
        SbmRiskClass.CSR_SEC_NONCTP: ("basel_mar21_70",),
        SbmRiskClass.CSR_SEC_CTP: ("basel_mar21_57",),
    }
    return _merge_citation_ids(
        _MAR21_VEGA_INTER_CITATION,
        delta_citation_by_class.get(risk_class, ()),
    )


def _text_by_id(sensitivities: Sequence[SbmSensitivity], field: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for sensitivity in sensitivities:
        value = getattr(sensitivity, field)
        values[sensitivity.sensitivity_id] = _require_text(
            value,
            field,
            sensitivity.sensitivity_id,
        )
    return values


def _optional_text_by_id(sensitivities: Sequence[SbmSensitivity], field: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for sensitivity in sensitivities:
        value = getattr(sensitivity, field)
        if value is None:
            continue
        values[sensitivity.sensitivity_id] = _require_text(
            value,
            field,
            sensitivity.sensitivity_id,
        )
    return values


def _batch_text_by_id(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_],
    _field: str,
) -> Mapping[str, str]:
    return {
        str(batch.sensitivity_ids[row_index]): str(values[row_index])
        for row_index in range(batch.row_count)
    }


def _batch_required_text_by_id(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_] | None,
    field: str,
) -> Mapping[str, str]:
    if values is None:
        raise SbmInputError(f"{field} is required", field=field)
    return _batch_text_by_id(batch, values, field)


def _batch_optional_text_by_id(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_] | None,
) -> Mapping[str, str]:
    if values is None:
        return {}
    return {
        str(batch.sensitivity_ids[row_index]): str(value)
        for row_index, value in enumerate(values)
        if value is not None
    }


def _lookup_axis(values: Mapping[str, str], sensitivity_id: str, field: str) -> str:
    try:
        value = values[sensitivity_id]
    except KeyError as exc:
        raise SbmInputError(
            f"missing non-GIRR vega {field} for weighted sensitivity",
            field=field,
            sensitivity_id=sensitivity_id,
        ) from exc
    return _require_text(value, field, sensitivity_id)


def _require_text(value: object, field: str, sensitivity_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError(
            "non-empty text is required",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value.strip()


def _merge_citation_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


__all__ = [
    "aggregate_non_girr_vega_measure_capital",
    "build_non_girr_vega_inter_bucket_correlation_map",
    "build_non_girr_vega_intra_bucket_correlation_matrix",
    "calculate_non_girr_vega_risk_class_capital",
    "calculate_non_girr_vega_risk_class_capital_from_batch",
    "non_girr_vega_intra_bucket_correlation",
]
