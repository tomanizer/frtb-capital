"""Compatibility exports for RRAO audit payload assembly."""

# Keep direct private imports working for callers that reached into the old
# module before the assembly split.
from frtb_rrao.assembly._payload_components import (
    back_to_back_match_payload,
    back_to_back_match_payload_from_values,
    investment_fund_descriptor_payload,
    investment_fund_descriptor_payload_from_values,
    lineage_payload,
    lineage_payload_from_values,
)
from frtb_rrao.assembly._payload_components import (
    enum_or_value as _enum_or_value,
)
from frtb_rrao.assembly._payload_components import (
    float_value as _float_value,
)
from frtb_rrao.assembly.payloads import *  # noqa: F403
from frtb_rrao.assembly.payloads import __all__ as _payload_all
from frtb_rrao.assembly.payloads import position_payload_from_values

_COMPAT_NAMES = (
    back_to_back_match_payload,
    back_to_back_match_payload_from_values,
    _enum_or_value,
    _float_value,
    investment_fund_descriptor_payload,
    investment_fund_descriptor_payload_from_values,
    lineage_payload,
    lineage_payload_from_values,
    position_payload_from_values,
)
__all__ = _payload_all
