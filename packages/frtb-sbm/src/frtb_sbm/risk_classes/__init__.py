"""Risk-class-specific SBM assembly modules."""

from frtb_sbm.risk_classes.commodity import calculate_commodity_delta_risk_class_capital
from frtb_sbm.risk_classes.equity import calculate_equity_delta_risk_class_capital
from frtb_sbm.risk_classes.fx import calculate_fx_delta_risk_class_capital

__all__ = [
    "calculate_commodity_delta_risk_class_capital",
    "calculate_equity_delta_risk_class_capital",
    "calculate_fx_delta_risk_class_capital",
]
