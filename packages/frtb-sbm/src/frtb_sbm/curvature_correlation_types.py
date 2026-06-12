"""Shared structural types for curvature correlation helpers.

Regulatory traceability:
    Basel MAR21.5 and SBM-CURV-001.
"""

from __future__ import annotations

from typing import Protocol

from frtb_sbm.data_models import SbmRiskClass


class CurvatureCorrelationFactor(Protocol):
    """Structural input required by curvature correlation helpers."""

    @property
    def risk_class(self) -> SbmRiskClass:
        """SBM risk class that owns the curvature factor.

        Returns
        -------
        SbmRiskClass
            Risk class used to choose the curvature correlation rule.
        """
        ...

    @property
    def bucket_id(self) -> str:
        """Regulatory bucket identifier for the curvature factor.

        Returns
        -------
        str
            Bucket identifier used for intra- and inter-bucket correlations.
        """
        ...

    @property
    def risk_factor(self) -> str:
        """Risk-factor label used by curvature correlation rules.

        Returns
        -------
        str
            Risk-factor label after curvature mapping normalization.
        """
        ...

    @property
    def qualifier(self) -> str | None:
        """Optional issuer, location, tranche, or equivalent correlation qualifier.

        Returns
        -------
        str | None
            Qualifier used by non-GIRR curvature correlation rules, when required.
        """
        ...


__all__ = ["CurvatureCorrelationFactor"]
