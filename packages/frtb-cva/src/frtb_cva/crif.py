"""
Optional CRIF/vendor-to-canonical CVA adapter (stdlib only).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from frtb_cva.data_models import (
    BaCvaHedgeType,
    CreditQuality,
    CvaCounterparty,
    CvaHedge,
    CvaNettingSet,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.validation import (
    AmountSignConvention,
    CvaInputError,
    normalise_ead_amount,
    normalise_sensitivity_amount,
    validate_cva_counterparties,
    validate_cva_hedges,
    validate_cva_netting_sets,
    validate_sa_cva_sensitivities,
)

_COUNTERPARTY_ID_FIELDS = ("CounterpartyID", "counterparty_id", "CptyID")
_NETTING_SET_ID_FIELDS = ("NettingSetID", "netting_set_id")
_HEDGE_ID_FIELDS = ("HedgeID", "hedge_id")
_SENSITIVITY_ID_FIELDS = ("SensitivityID", "sensitivity_id", "RiskFactorID")
_AMOUNT_FIELDS = ("Amount", "amount", "SensitivityAmount")
_EAD_FIELDS = ("EAD", "ead", "Exposure")
_TAG_FIELDS = ("SensitivityTag", "sensitivity_tag", "Tag")
_SIGN_FIELDS = ("SignConvention", "sign_convention")


@dataclass(frozen=True)
class CvaAdapterWarning:
    source_row_id: str
    field: str
    message: str


@dataclass(frozen=True)
class CvaRejectedRow:
    source_row_id: str
    reason: str
    field: str


@dataclass(frozen=True)
class CvaAdapterResult:
    counterparties: tuple[CvaCounterparty, ...] = ()
    netting_sets: tuple[CvaNettingSet, ...] = ()
    hedges: tuple[CvaHedge, ...] = ()
    sensitivities: tuple[SaCvaSensitivity, ...] = ()
    warnings: tuple[CvaAdapterWarning, ...] = ()
    rejected_rows: tuple[CvaRejectedRow, ...] = ()


def adapt_cva_records(
    records: object,
    *,
    record_kind: str,
    source_system: str = "cva-adapter",
    source_file: str = "records",
    amount_sign_convention: AmountSignConvention = "positive_loss",
    ead_sign_convention: str = "non_negative",
) -> CvaAdapterResult:
    """Map external rows to canonical CVA records for one record kind."""

    if isinstance(records, (str, bytes, Mapping)) or not isinstance(records, Iterable):
        raise CvaInputError("records must be an iterable of mapping rows", field="records")
    allowed_kinds = {"counterparty", "netting_set", "hedge", "sensitivity"}
    if record_kind not in allowed_kinds:
        raise CvaInputError(f"unsupported record_kind {record_kind}", field="record_kind")
    materialised = tuple(records)
    warnings: list[CvaAdapterWarning] = []
    rejected: list[CvaRejectedRow] = []
    counterparties: list[CvaCounterparty] = []
    netting_sets: list[CvaNettingSet] = []
    hedges: list[CvaHedge] = []
    sensitivities: list[SaCvaSensitivity] = []

    for row_number, raw in enumerate(materialised, start=1):
        if not isinstance(raw, Mapping):
            rejected.append(
                CvaRejectedRow(
                    source_row_id=f"row-{row_number}",
                    reason="record must be a mapping",
                    field="record",
                )
            )
            continue
        record = dict(raw)
        source_row_id = str(
            record.get("source_row_id") or record.get("RowID") or f"row-{row_number}"
        )
        try:
            if record_kind == "counterparty":
                counterparties.append(
                    _counterparty_from_record(
                        record,
                        source_row_id,
                        source_system,
                        source_file,
                    )
                )
            elif record_kind == "netting_set":
                netting_sets.append(
                    _netting_set_from_record(
                        record,
                        source_row_id,
                        source_system,
                        source_file,
                        ead_sign_convention=ead_sign_convention,
                    )
                )
            elif record_kind == "hedge":
                hedges.append(_hedge_from_record(record, source_row_id, source_system, source_file))
            elif record_kind == "sensitivity":
                sensitivities.append(
                    _sensitivity_from_record(
                        record,
                        source_row_id,
                        source_system,
                        source_file,
                        amount_sign_convention=amount_sign_convention,
                        warnings=warnings,
                    )
                )
        except CvaInputError as exc:
            rejected.append(
                CvaRejectedRow(
                    source_row_id=source_row_id,
                    reason=str(exc),
                    field=exc.field,
                )
            )

    validated_counterparties = validate_cva_counterparties(counterparties) if counterparties else ()
    validated_netting_sets = (
        validate_cva_netting_sets(netting_sets, counterparties=validated_counterparties)
        if netting_sets
        else ()
    )
    validated_hedges = validate_cva_hedges(hedges) if hedges else ()
    validated_sensitivities = validate_sa_cva_sensitivities(sensitivities) if sensitivities else ()

    return CvaAdapterResult(
        counterparties=validated_counterparties,
        netting_sets=validated_netting_sets,
        hedges=validated_hedges,
        sensitivities=validated_sensitivities,
        warnings=tuple(warnings),
        rejected_rows=tuple(rejected),
    )


def _first_field(record: Mapping[str, object], *names: str) -> object | None:
    for name in names:
        if name in record:
            return record[name]
    return None


def _required_field(
    record: Mapping[str, object],
    *names: str,
    field_name: str,
) -> str:
    value = _first_field(record, *names)
    if value is None:
        raise CvaInputError(f"missing required field: {field_name}", field=field_name)
    return str(value)


def _optional_float(value: object | None, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise CvaInputError("value must be numeric", field="value")
    return float(value)


def _lineage(
    source_row_id: str,
    *,
    source_system: str,
    source_file: str,
    column_map: tuple[tuple[str, str], ...],
) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system=source_system,
        source_file=source_file,
        source_row_id=source_row_id,
        source_column_map=column_map,
    )


def _counterparty_from_record(
    record: Mapping[str, object],
    source_row_id: str,
    source_system: str,
    source_file: str,
) -> CvaCounterparty:
    counterparty_id = _required_field(
        record,
        *_COUNTERPARTY_ID_FIELDS,
        field_name="counterparty_id",
    )
    return CvaCounterparty(
        counterparty_id=counterparty_id,
        desk_id=str(record.get("desk_id") or record.get("DeskID") or "desk-1"),
        legal_entity=str(record.get("legal_entity") or record.get("LegalEntity") or "LE-001"),
        sector=CvaSector(str(record.get("sector") or record.get("Sector") or "SOVEREIGN")),
        credit_quality=CreditQuality(
            str(record.get("credit_quality") or record.get("CreditQuality") or "INVESTMENT_GRADE")
        ),
        region=str(record.get("region") or record.get("Region") or "EMEA"),
        source_row_id=source_row_id,
        lineage=_lineage(
            source_row_id,
            source_system=source_system,
            source_file=source_file,
            column_map=(),
        ),
    )


def _netting_set_from_record(
    record: Mapping[str, object],
    source_row_id: str,
    source_system: str,
    source_file: str,
    *,
    ead_sign_convention: str,
) -> CvaNettingSet:
    ead = normalise_ead_amount(
        _optional_float(_first_field(record, *_EAD_FIELDS), 0.0),
        source_sign_convention=ead_sign_convention,  # type: ignore[arg-type]
    )
    return CvaNettingSet(
        netting_set_id=_required_field(
            record,
            *_NETTING_SET_ID_FIELDS,
            field_name="netting_set_id",
        ),
        counterparty_id=_required_field(
            record,
            *_COUNTERPARTY_ID_FIELDS,
            field_name="counterparty_id",
        ),
        ead=ead,
        effective_maturity=_optional_float(
            record.get("effective_maturity") or record.get("Maturity"),
            1.0,
        ),
        discount_factor=_optional_float(record.get("discount_factor"), 1.0),
        currency=str(record.get("currency") or "USD"),
        sign_convention=str(record.get("sign_convention") or "non_negative"),
        uses_imm_ead=bool(record.get("uses_imm_ead", True)),
        carved_out_to_ba_cva=bool(record.get("carved_out_to_ba_cva", False)),
        source_row_id=source_row_id,
        lineage=_lineage(
            source_row_id,
            source_system=source_system,
            source_file=source_file,
            column_map=(),
        ),
    )


def _hedge_from_record(
    record: Mapping[str, object],
    source_row_id: str,
    source_system: str,
    source_file: str,
) -> CvaHedge:
    return CvaHedge(
        hedge_id=_required_field(record, *_HEDGE_ID_FIELDS, field_name="hedge_id"),
        source_row_id=source_row_id,
        counterparty_id=_required_field(
            record,
            *_COUNTERPARTY_ID_FIELDS,
            field_name="counterparty_id",
        ),
        hedge_type=BaCvaHedgeType(str(record.get("hedge_type") or "SINGLE_NAME_CDS")),
        notional=_optional_float(record.get("notional"), 0.0),
        remaining_maturity=_optional_float(record.get("remaining_maturity"), 1.0),
        discount_factor=_optional_float(record.get("discount_factor"), 1.0),
        discount_factor_explicit=bool(record.get("discount_factor_explicit", False)),
        reference_sector=CvaSector(str(record.get("reference_sector") or "SOVEREIGN")),
        reference_credit_quality=CreditQuality(
            str(record.get("reference_credit_quality") or "INVESTMENT_GRADE")
        ),
        reference_region=str(record.get("reference_region") or "EMEA"),
        reference_relation=HedgeReferenceRelation(
            str(record.get("reference_relation") or "DIRECT")
        ),
        eligibility=HedgeEligibility(str(record.get("eligibility") or "ELIGIBLE")),
        is_internal=bool(record.get("is_internal", False)),
        eligibility_evidence_id=str(record["eligibility_evidence_id"])
        if record.get("eligibility_evidence_id")
        else None,
        lineage=_lineage(
            source_row_id,
            source_system=source_system,
            source_file=source_file,
            column_map=(),
        ),
    )


def _sensitivity_from_record(
    record: Mapping[str, object],
    source_row_id: str,
    source_system: str,
    source_file: str,
    *,
    amount_sign_convention: AmountSignConvention,
    warnings: list[CvaAdapterWarning],
) -> SaCvaSensitivity:
    tag_raw = str(_first_field(record, *_TAG_FIELDS) or "CVA").upper()
    if tag_raw not in {"CVA", "HDG"}:
        warnings.append(
            CvaAdapterWarning(
                source_row_id=source_row_id,
                field="sensitivity_tag",
                message=f"ambiguous tag {tag_raw}; rejected",
            )
        )
        raise CvaInputError("ambiguous CVA/HDG sensitivity tag", field="sensitivity_tag")
    sign_raw = str(_first_field(record, *_SIGN_FIELDS) or amount_sign_convention)
    amount = normalise_sensitivity_amount(
        _optional_float(_first_field(record, *_AMOUNT_FIELDS), 0.0),
        source_sign_convention=amount_sign_convention,
    )
    return SaCvaSensitivity(
        sensitivity_id=_required_field(
            record,
            *_SENSITIVITY_ID_FIELDS,
            field_name="sensitivity_id",
        ),
        risk_class=SaCvaRiskClass(str(record.get("risk_class") or "GIRR")),
        risk_measure=SaCvaRiskMeasure(str(record.get("risk_measure") or "DELTA")),
        sensitivity_tag=SensitivityTag(tag_raw),
        bucket_id=str(record.get("bucket_id") or "USD"),
        risk_factor_key=str(record.get("risk_factor_key") or "5y"),
        tenor=str(record["tenor"]) if record.get("tenor") is not None else None,
        amount=amount,
        amount_currency=str(record.get("amount_currency") or "USD"),
        sign_convention=sign_raw,
        source_row_id=source_row_id,
        hedge_id=str(record["hedge_id"]) if record.get("hedge_id") is not None else None,
        lineage=_lineage(
            source_row_id,
            source_system=source_system,
            source_file=source_file,
            column_map=(("Amount", "amount"), ("Tag", "sensitivity_tag")),
        ),
    )


__all__ = ["CvaAdapterResult", "CvaAdapterWarning", "CvaRejectedRow", "adapt_cva_records"]
