"""Explicit FX translation helpers for DRC base-currency calculations."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import replace

from frtb_drc._citations import merge_citations as _merge_citations
from frtb_drc._hashing import hash_payload as _hash_payload
from frtb_drc._identifiers import slug as _slug
from frtb_drc._validation_utils import require_text as _require_text
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    DrcCalculationContext,
    DrcFxConversion,
    DrcFxRate,
    DrcPosition,
    DrcSourceLineage,
)
from frtb_drc.validation import DrcInputError


def validate_fx_rates(context: DrcCalculationContext) -> None:
    """Validate explicit context FX rates without performing conversion.
    Parameters
    ----------
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.
    """

    for currency, rate in context.fx_rates.items():
        currency_key = _require_text(currency, "fx_rates currency key")
        if currency != currency_key:
            raise DrcInputError("fx_rates currency keys must be normalized non-empty text")
        if not isinstance(rate, DrcFxRate):
            raise DrcInputError("fx_rates must map currency codes to DrcFxRate records")
        _validate_fx_rate(rate, context=context)
        if currency_key != rate.source_currency:
            raise DrcInputError(
                f"fx_rates key {currency_key} does not match rate source_currency "
                f"{rate.source_currency}"
            )


def convert_positions_to_base_currency(
    positions: Iterable[DrcPosition],
    *,
    context: DrcCalculationContext,
) -> tuple[tuple[DrcPosition, ...], tuple[DrcFxConversion, ...]]:
    """Return calculation positions with monetary fields translated to base currency.
    Parameters
    ----------
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    tuple[tuple[DrcPosition, ...], tuple[DrcFxConversion, ...]]
        FX-translated positions and conversion audit records.
    """

    converted: list[DrcPosition] = []
    used_rates: dict[str, DrcFxRate] = {}
    counts: dict[str, int] = {}
    for position in positions:
        if position.currency == context.base_currency:
            converted.append(position)
            continue
        rate = require_fx_rate(
            context,
            source_currency=position.currency,
            position_id=position.position_id,
        )
        used_rates[position.currency] = rate
        counts[position.currency] = counts.get(position.currency, 0) + 1
        converted.append(_convert_position(position, context=context, rate=rate))
    conversions = fx_conversion_records(used_rates, counts)
    return tuple(converted), conversions


def require_fx_rate(
    context: DrcCalculationContext,
    *,
    source_currency: str,
    position_id: str | None = None,
) -> DrcFxRate:
    """Return a validated FX rate for one source currency or fail closed.
    Parameters
    ----------
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.
    source_currency : str
        Source currency code to translate from.
    position_id : str | None, optional
        Position identifier for error context.

    Returns
    -------
    DrcFxRate
        FX rate matching the source currency and run base currency.
    """

    try:
        rate = context.fx_rates[source_currency]
    except KeyError as exc:
        position_label = "" if position_id is None else f" for position {position_id}"
        raise DrcInputError(
            f"missing FX rate {source_currency}->{context.base_currency}{position_label}; "
            "provide context.fx_rates with explicit rate source lineage"
        ) from exc
    _validate_fx_rate(rate, context=context)
    return rate


def fx_conversion_records(
    used_rates: Mapping[str, DrcFxRate],
    counts: Mapping[str, int],
) -> tuple[DrcFxConversion, ...]:
    """Build stable per-currency FX conversion lineage records.
    Parameters
    ----------
    used_rates : Mapping[str, DrcFxRate]
        FX rates applied during position conversion.
    counts : Mapping[str, int]
        Position counts per source currency.

    Returns
    -------
    tuple[DrcFxConversion, ...]
        Deterministically ordered FX conversion audit records.
    """

    conversions: list[DrcFxConversion] = []
    for currency in sorted(used_rates):
        rate = used_rates[currency]
        conversions.append(
            DrcFxConversion(
                source_currency=rate.source_currency,
                target_currency=rate.target_currency,
                rate=float(rate.rate),
                as_of_date=rate.as_of_date,
                source_id=rate.source_id,
                position_count=int(counts[currency]),
                lineage=rate.lineage,
                citation_ids=rate.citation_ids,
            )
        )
    return tuple(conversions)


def fx_branch_metadata(conversions: tuple[DrcFxConversion, ...]) -> tuple[BranchMetadata, ...]:
    """Represent applied FX conversion choices in run-level branch metadata.
    Parameters
    ----------
    conversions : tuple[DrcFxConversion, ...]
        Applied FX conversion lineage records.

    Returns
    -------
    tuple[BranchMetadata, ...]
        Branch metadata describing FX translation choices.
    """

    return tuple(
        BranchMetadata(
            branch_id=f"drc-fx-{_slug(conversion.source_currency)}-{_slug(conversion.target_currency)}",
            branch_type=BranchType.NORMAL,
            source_id=conversion.source_id,
            selected=True,
            reason=(
                f"translated {conversion.position_count} DRC position(s) from "
                f"{conversion.source_currency} to {conversion.target_currency} at "
                f"{conversion.rate} as of {conversion.as_of_date.isoformat()} before "
                "gross default exposure calculation"
            ),
            citations=conversion.citation_ids,
        )
        for conversion in conversions
    )


def input_hash_with_fx(
    input_hash: str,
    conversions: tuple[DrcFxConversion, ...],
) -> str:
    """Include FX-rate lineage in the run input hash when conversion is applied.
    Parameters
    ----------
    input_hash : str
        Precomputed input digest before FX lineage.
    conversions : tuple[DrcFxConversion, ...]
        Applied FX conversion lineage records.

    Returns
    -------
    str
        Input hash updated with FX conversion lineage.
    """

    if not conversions:
        return input_hash
    payload = {
        "input_hash": input_hash,
        "fx_conversions": [conversion.as_dict() for conversion in conversions],
    }
    return _hash_payload(payload)


def fx_citation_ids(conversions: tuple[DrcFxConversion, ...]) -> tuple[str, ...]:
    """Return sorted FX citation ids from applied conversion records.
    Parameters
    ----------
    conversions : tuple[DrcFxConversion, ...]
        Applied FX conversion lineage records.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers required by the applied FX conversions.
    """

    citation_ids: set[str] = set()
    for conversion in conversions:
        citation_ids.update(conversion.citation_ids)
    return tuple(sorted(citation_ids))


def _convert_position(
    position: DrcPosition,
    *,
    context: DrcCalculationContext,
    rate: DrcFxRate,
) -> DrcPosition:
    return replace(
        position,
        notional=position.notional * rate.rate,
        market_value=None if position.market_value is None else position.market_value * rate.rate,
        cumulative_pnl=None
        if position.cumulative_pnl is None
        else position.cumulative_pnl * rate.rate,
        currency=context.base_currency,
        citation_ids=_merge_citations(position.citation_ids, rate.citation_ids),
    )


def _validate_fx_rate(rate: DrcFxRate, *, context: DrcCalculationContext) -> None:
    _require_text(rate.source_currency, "fx_rate.source_currency")
    _require_text(rate.target_currency, "fx_rate.target_currency")
    _require_text(rate.source_id, "fx_rate.source_id")
    _validate_lineage(rate.lineage)
    if rate.target_currency != context.base_currency:
        raise DrcInputError(
            f"FX rate {rate.source_currency}->{rate.target_currency} does not target "
            f"context base_currency {context.base_currency}"
        )
    if rate.as_of_date != context.calculation_date:
        raise DrcInputError(
            f"FX rate {rate.source_currency}->{rate.target_currency} as_of_date "
            f"{rate.as_of_date.isoformat()} does not match calculation_date "
            f"{context.calculation_date.isoformat()}"
        )
    if not math.isfinite(rate.rate) or rate.rate <= 0.0:
        raise DrcInputError(
            f"FX rate {rate.source_currency}->{rate.target_currency} must be finite and positive"
        )
    if rate.source_currency == rate.target_currency and rate.rate != 1.0:
        raise DrcInputError(f"FX rate {rate.source_currency}->{rate.target_currency} must be 1.0")
    if not rate.citation_ids:
        raise DrcInputError("fx_rate.citation_ids must contain at least one citation")
    for citation_id in rate.citation_ids:
        _require_text(citation_id, "fx_rate.citation_ids")


def _validate_lineage(lineage: DrcSourceLineage) -> None:
    if not isinstance(lineage, DrcSourceLineage):
        raise DrcInputError("fx_rate.lineage must be DrcSourceLineage")
    _require_text(lineage.source_system, "fx_rate.lineage.source_system")
    _require_text(lineage.source_file, "fx_rate.lineage.source_file")
    _require_text(lineage.source_row_id, "fx_rate.lineage.source_row_id")


__all__ = [
    "convert_positions_to_base_currency",
    "fx_branch_metadata",
    "fx_citation_ids",
    "fx_conversion_records",
    "input_hash_with_fx",
    "require_fx_rate",
    "validate_fx_rates",
]
