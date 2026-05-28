"""
FRTB Default Risk Charge (DRC) package.

Prototype implementation of FRTB DRC (Basel MAR22 / U.S. NPR 2.0 / CRR3).

See docs/FRTB-DRC-PRD-v1.0.md and docs/FRTB-DRC-Requirements-Specification.md.
See docs/REGULATORY_TRACEABILITY.md for citations.

Prototype only. Not for regulatory reporting.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Core exports (populated issue-by-issue)
from frtb_drc.crif import get_rename_cols
from frtb_drc.data_models import (
    CreditQuality,
    NettedIssuerSeniority,
    Position,
    RiskClassDRC,
    RulesVersion,
    Seniority,
)
from frtb_drc.jtd import (
    apply_hedging_benefit,
    compute_gross_jtd,
    net_positions_by_issuer_seniority,
)
from frtb_drc.reference_data import (
    get_lgd,
    get_risk_weight,
    load_reference_data,
)

__all__ = [
    "CreditQuality",
    "NettedIssuerSeniority",
    "Position",
    "RiskClassDRC",
    "RulesVersion",
    "Seniority",
    "__version__",
    "apply_hedging_benefit",
    "compute_gross_jtd",
    "get_lgd",
    "get_rename_cols",
    "get_risk_weight",
    "load_reference_data",
    "net_positions_by_issuer_seniority",
]
