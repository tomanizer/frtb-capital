"""CSR securitisation CTP weighting support helpers.

These helpers keep CTP decomposition evidence checks shared between delta
and vega weighting paths without routing through compatibility modules.
"""

from __future__ import annotations

from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import SbmSensitivityBatch


def _ensure_csr_sec_ctp_decomposition_evidence_for_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
) -> None:
    from frtb_sbm.csr_sec_ctp_reference_data import (
        CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG,
        CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,
    )

    if batch.mapping_citation_ids is None:
        return
    flags = set(batch.mapping_citation_ids[row_index])
    if CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG not in flags:
        return
    if CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG in flags:
        return
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm CSR securitisation CTP requires decomposition evidence when "
        "index constituent decomposition is requested; "
        f"sensitivity_id={cast(str, batch.sensitivity_ids[row_index])!r}"
    )
