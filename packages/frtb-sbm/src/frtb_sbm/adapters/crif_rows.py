"""Row-dictionary CRIF adapter entrypoint for SBM."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.adapters.crif_fields import _rejected_row_from_exception
from frtb_sbm.adapters.crif_models import SbmAdapterResult, SbmAdapterWarning, SbmRejectedRow
from frtb_sbm.adapters.crif_row_mapping import _map_crif_row
from frtb_sbm.data_models import SbmSensitivity, SbmSignConvention
from frtb_sbm.validation import SbmInputError, validate_sbm_sensitivities


def adapt_crif_records(
    records: object,
    *,
    source_file: str = "crif.csv",
    desk_id: str = "UNKNOWN",
    legal_entity: str = "UNKNOWN",
    sign_convention: SbmSignConvention = SbmSignConvention.RECEIVE,
) -> SbmAdapterResult:
    """Map CRIF-like row dictionaries into canonical ``SbmSensitivity`` records.
    Parameters
    ----------
    records, source_file, desk_id, legal_entity, sign_convention :
        See function signature for types and defaults.

    Returns
    -------
    SbmAdapterResult
    """

    if not isinstance(records, Sequence) or isinstance(records, str | bytes):
        raise SbmInputError("records must be a sequence of mapping rows", field="records")
    sensitivities: list[SbmSensitivity] = []
    warnings: list[SbmAdapterWarning] = []
    rejected: list[SbmRejectedRow] = []
    accepted_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            rejected.append(
                SbmRejectedRow(
                    source_row_id=str(index),
                    reason="row must be a mapping",
                    field="records",
                    source_row=(),
                )
            )
            continue
        try:
            sensitivity, row_warnings = _map_crif_row(
                record,
                source_file=source_file,
                desk_id=desk_id,
                legal_entity=legal_entity,
                sign_convention=sign_convention,
                fallback_row_id=str(index),
            )
            validated = _validate_adapter_row(sensitivity, accepted_ids=accepted_ids)
        except (SbmInputError, UnsupportedRegulatoryFeatureError) as exc:
            rejected.append(_rejected_row_from_exception(record, exc, fallback_row_id=str(index)))
            continue
        sensitivities.extend(validated)
        accepted_ids.update(item.sensitivity_id for item in validated)
        warnings.extend(row_warnings)
    return SbmAdapterResult(
        sensitivities=tuple(sensitivities),
        warnings=tuple(warnings),
        rejected_rows=tuple(rejected),
    )


def _validate_adapter_row(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    accepted_ids: set[str],
) -> tuple[SbmSensitivity, ...]:
    validated = validate_sbm_sensitivities(sensitivities)
    for sensitivity in validated:
        if sensitivity.sensitivity_id in accepted_ids:
            raise SbmInputError(
                "duplicate sensitivity id",
                field="sensitivity_id",
                sensitivity_id=sensitivity.sensitivity_id,
            )
    return validated


__all__ = ["adapt_crif_records"]
