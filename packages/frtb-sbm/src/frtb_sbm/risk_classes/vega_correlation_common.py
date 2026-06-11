"""Shared support for non-GIRR vega correlation stages."""

from __future__ import annotations

from collections.abc import Mapping

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.csr_nonsec_reference_data import CSR_OTHER_SECTOR_BUCKET
from frtb_sbm.csr_sec_nonctp_reference_data import CSR_SEC_OTHER_SECTOR_BUCKET
from frtb_sbm.data_models import SbmRiskClass
from frtb_sbm.equity_reference_data import EQUITY_OTHER_SECTOR_BUCKET
from frtb_sbm.validation import SbmInputError

_MAR21_VEGA_INTRA_CITATION = ("basel_mar21_4_intra_bucket", "basel_mar21_94")
_MAR21_VEGA_INTER_CITATION = ("basel_mar21_4_inter_bucket", "basel_mar21_95")
_VEGA_NEUTRAL_TENOR = "1y"
_VEGA_NEUTRAL_LOCATION = "__VEGA_NO_DELIVERY_LOCATION__"


def _uses_absolute_weight_intra_bucket(risk_class: SbmRiskClass, bucket_id: str) -> bool:
    if risk_class is SbmRiskClass.EQUITY:
        return bucket_id == EQUITY_OTHER_SECTOR_BUCKET
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return bucket_id == CSR_OTHER_SECTOR_BUCKET
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET
    return False


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
