"""Risk-class-specific SBM assembly modules."""

from frtb_sbm.risk_classes.commodity import (
    calculate_commodity_delta_risk_class_capital,
    calculate_commodity_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_nonsec import (
    calculate_csr_nonsec_delta_risk_class_capital,
    calculate_csr_nonsec_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_sec_ctp import (
    calculate_csr_sec_ctp_delta_risk_class_capital,
    calculate_csr_sec_ctp_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_sec_nonctp import (
    calculate_csr_sec_nonctp_delta_risk_class_capital,
    calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.equity import (
    calculate_equity_delta_risk_class_capital,
    calculate_equity_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.fx import (
    calculate_fx_delta_risk_class_capital,
    calculate_fx_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.girr import (
    calculate_girr_delta_risk_class_capital,
    calculate_girr_delta_risk_class_capital_from_batch,
    calculate_girr_vega_risk_class_capital,
    calculate_girr_vega_risk_class_capital_from_batch,
)

__all__ = [
    "calculate_commodity_delta_risk_class_capital",
    "calculate_commodity_delta_risk_class_capital_from_batch",
    "calculate_csr_nonsec_delta_risk_class_capital",
    "calculate_csr_nonsec_delta_risk_class_capital_from_batch",
    "calculate_csr_sec_ctp_delta_risk_class_capital",
    "calculate_csr_sec_ctp_delta_risk_class_capital_from_batch",
    "calculate_csr_sec_nonctp_delta_risk_class_capital",
    "calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch",
    "calculate_equity_delta_risk_class_capital",
    "calculate_equity_delta_risk_class_capital_from_batch",
    "calculate_fx_delta_risk_class_capital",
    "calculate_fx_delta_risk_class_capital_from_batch",
    "calculate_girr_delta_risk_class_capital",
    "calculate_girr_delta_risk_class_capital_from_batch",
    "calculate_girr_vega_risk_class_capital",
    "calculate_girr_vega_risk_class_capital_from_batch",
]
