"""Canonical SBM batch-path registry.

Regulatory traceability:
    ADR 0045 canonical batch pipeline consolidation; Basel MAR21 delta, vega,
    and curvature paths implemented by this package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from frtb_sbm._errors import SbmInputError
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure

SbmBatchPath = tuple[SbmRiskClass, SbmRiskMeasure]


@dataclass(frozen=True)
class SbmBatchSpec:
    """Registry row for one supported SBM batch pipeline path.

    Attributes
    ----------
    risk_class
        SBM risk class owned by the path.
    risk_measure
        SBM risk measure owned by the path.
    path_key
        Stable snake-case path identifier for diagnostics and generated names.
    label
        Human-readable label used in errors and documentation.
    """

    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    path_key: str
    label: str

    @property
    def path(self) -> SbmBatchPath:
        """Return the tuple key used by path dispatchers.

        Returns
        -------
        SbmBatchPath
        """

        return (self.risk_class, self.risk_measure)


def _spec(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    label: str,
) -> SbmBatchSpec:
    return SbmBatchSpec(
        risk_class=risk_class,
        risk_measure=risk_measure,
        path_key=f"{risk_class.value.lower()}_{risk_measure.value.lower()}",
        label=label,
    )


SBM_BATCH_PATH_ORDER: tuple[SbmBatchPath, ...] = (
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE),
)

_SBM_BATCH_SPEC_DATA: dict[SbmBatchPath, SbmBatchSpec] = {
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, "GIRR delta"
    ),
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA): _spec(
        SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, "GIRR vega"
    ),
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, "GIRR curvature"
    ),
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.FX, SbmRiskMeasure.DELTA, "FX delta"
    ),
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA): _spec(SbmRiskClass.FX, SbmRiskMeasure.VEGA, "FX vega"),
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.FX, SbmRiskMeasure.CURVATURE, "FX curvature"
    ),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA, "equity delta"
    ),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA): _spec(
        SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA, "equity vega"
    ),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE, "equity curvature"
    ),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA, "commodity delta"
    ),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA): _spec(
        SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA, "commodity vega"
    ),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE, "commodity curvature"
    ),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA, "CSR non-securitisation delta"
    ),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA): _spec(
        SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA, "CSR non-securitisation vega"
    ),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.CSR_NONSEC,
        SbmRiskMeasure.CURVATURE,
        "CSR non-securitisation curvature",
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.DELTA,
        "CSR securitisation non-CTP delta",
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA): _spec(
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.VEGA,
        "CSR securitisation non-CTP vega",
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.CURVATURE,
        "CSR securitisation non-CTP curvature",
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA): _spec(
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskMeasure.DELTA,
        "CSR securitisation CTP delta",
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA): _spec(
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskMeasure.VEGA,
        "CSR securitisation CTP vega",
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE): _spec(
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskMeasure.CURVATURE,
        "CSR securitisation CTP curvature",
    ),
}

SBM_BATCH_SPECS: Mapping[SbmBatchPath, SbmBatchSpec] = MappingProxyType(_SBM_BATCH_SPEC_DATA)


def sbm_batch_spec(risk_class: SbmRiskClass, risk_measure: SbmRiskMeasure) -> SbmBatchSpec:
    """Return the registry row for an SBM batch path.

    Parameters
    ----------
    risk_class
        SBM risk class.
    risk_measure
        SBM risk measure.

    Returns
    -------
    SbmBatchSpec
    """

    try:
        return SBM_BATCH_SPECS[(risk_class, risk_measure)]
    except KeyError as exc:
        raise SbmInputError(
            "unsupported SBM batch path "
            f"risk_class={risk_class.value}, risk_measure={risk_measure.value}",
            field="risk_class,risk_measure",
        ) from exc


__all__ = [
    "SBM_BATCH_PATH_ORDER",
    "SBM_BATCH_SPECS",
    "SbmBatchPath",
    "SbmBatchSpec",
    "sbm_batch_spec",
]
