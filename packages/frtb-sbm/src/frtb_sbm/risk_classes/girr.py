"""GIRR delta and vega SBM risk-class capital kernels.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 for scenario aggregation; MAR21.39-MAR21.50 for
    GIRR delta sensitivities, correlations, and buckets; MAR21.90-MAR21.95
    for GIRR vega sensitivities, correlations, and buckets; U.S. NPR 2.0
    section V.A.7.a for the supported U.S. profile scenario flow.
"""

from __future__ import annotations

import numpy as np

from frtb_sbm._batch_lookup import batch_text_by_id as _batch_text_by_id
from frtb_sbm.adapters.sensitivities import build_sbm_batch
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmCalculationContext,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
)
from frtb_sbm.factor_grid import net_girr_delta_sensitivity_batch
from frtb_sbm.risk_classes.girr_correlations import _aggregate_girr_measure_capital
from frtb_sbm.validation import SbmInputError, normalise_currency_code
from frtb_sbm.weighted_sensitivity import weight_girr_vega_sensitivity_batch


def calculate_girr_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate GIRR delta risk-class capital from canonical sensitivity rows.

    Parameters
    ----------
    sensitivities
        Homogeneous GIRR delta sensitivity rows.
    profile_id
        Supported SBM regulatory profile identifier.
    reporting_currency
        Reporting currency used for GIRR delta weighting.
    pairwise_evidence_mode
        Pairwise correlation evidence capture mode.
    pairwise_evidence_limit
        Maximum pairwise evidence records to retain per aggregation branch.

    Returns
    -------
    RiskClassCapital
        GIRR delta risk-class capital with scenario and citation metadata.
    """

    batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.DELTA)
    return calculate_girr_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_girr_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate GIRR delta risk-class capital from a canonical batch.

    Parameters
    ----------
    batch
        Homogeneous GIRR delta sensitivity batch.
    profile_id
        Supported SBM regulatory profile identifier.
    reporting_currency
        Reporting currency used for GIRR delta weighting.
    pairwise_evidence_mode
        Pairwise correlation evidence capture mode.
    pairwise_evidence_limit
        Maximum pairwise evidence records to retain per aggregation branch.

    Returns
    -------
    RiskClassCapital
        GIRR delta risk-class capital with scenario and citation metadata.
    """

    factor_grid = net_girr_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    return _aggregate_girr_measure_capital(
        factor_grid.weighted_sensitivities,
        profile_id=profile_id,
        risk_measure=SbmRiskMeasure.DELTA,
        tenor_by_id=factor_grid.tenor_by_id,
        risk_factor_by_id=factor_grid.risk_factor_by_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _ensure_girr_delta_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError("GIRR delta batch must not be empty", field="batch")
    normalise_currency_code(context.reporting_currency, field="reporting_currency")
    scoped_desk_id = (context.desk_id or "").strip()
    scoped_legal_entity = (context.legal_entity or "").strip()
    for row_index in range(batch.row_count):
        sensitivity_id = batch.sensitivity_ids[row_index]
        if scoped_desk_id and batch.desk_ids[row_index] != scoped_desk_id:
            raise SbmInputError(
                f"desk_id {batch.desk_ids[row_index]} does not match "
                f"context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=sensitivity_id,
            )
        if scoped_legal_entity and batch.legal_entities[row_index] != scoped_legal_entity:
            raise SbmInputError(
                f"legal_entity {batch.legal_entities[row_index]} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=sensitivity_id,
            )


def _ensure_girr_vega_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError("GIRR vega batch must not be empty", field="batch")
    if batch.risk_class is not SbmRiskClass.GIRR:
        raise SbmInputError(
            "GIRR vega batch only accepts GIRR sensitivities",
            field="risk_class",
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise SbmInputError(
            "GIRR vega batch only accepts vega sensitivities",
            field="risk_measure",
        )
    scoped_desk_id = (context.desk_id or "").strip()
    scoped_legal_entity = (context.legal_entity or "").strip()
    if scoped_desk_id:
        mismatches = batch.desk_ids != scoped_desk_id
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"desk_id {batch.desk_ids[row_index]} does not match "
                f"context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )
    if scoped_legal_entity:
        mismatches = batch.legal_entities != scoped_legal_entity
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"legal_entity {batch.legal_entities[row_index]} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )


def calculate_girr_vega_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate GIRR vega risk-class capital from canonical sensitivity rows.

    Parameters
    ----------
    sensitivities
        Homogeneous GIRR vega sensitivity rows.
    profile_id
        Supported SBM regulatory profile identifier.
    pairwise_evidence_mode
        Pairwise correlation evidence capture mode.
    pairwise_evidence_limit
        Maximum pairwise evidence records to retain per aggregation branch.

    Returns
    -------
    RiskClassCapital
        GIRR vega risk-class capital with scenario and citation metadata.
    """

    batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.VEGA)
    return calculate_girr_vega_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_girr_vega_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate GIRR vega risk-class capital from a canonical batch.

    Parameters
    ----------
    batch
        Homogeneous GIRR vega sensitivity batch.
    profile_id
        Supported SBM regulatory profile identifier.
    pairwise_evidence_mode
        Pairwise correlation evidence capture mode.
    pairwise_evidence_limit
        Maximum pairwise evidence records to retain per aggregation branch.

    Returns
    -------
    RiskClassCapital
        GIRR vega risk-class capital with scenario and citation metadata.
    """

    weighted = weight_girr_vega_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    option_tenor_by_id = _batch_text_by_id(batch, batch.option_tenors, "option_tenor")
    tenor_by_id = _batch_text_by_id(batch, batch.tenors, "tenor")
    return _aggregate_girr_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_measure=SbmRiskMeasure.VEGA,
        tenor_by_id=tenor_by_id,
        option_tenor_by_id=option_tenor_by_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


__all__ = [
    "calculate_girr_delta_risk_class_capital",
    "calculate_girr_delta_risk_class_capital_from_batch",
    "calculate_girr_vega_risk_class_capital",
    "calculate_girr_vega_risk_class_capital_from_batch",
]
