"""DRC risk-factor-adjacent metadata drilldown helpers.

DRC does not use the same market-risk-factor schema as SBM or IMA. This module
projects existing DRC result records into stable issuer/obligor/source drilldown
rows for result-store and Navigator consumers without querying canonical
metadata stores or changing capital mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_drc.data_models import DrcCapitalResult


@dataclass(frozen=True)
class DrcRiskFactorMetadataRow:
    """Issuer, obligor, bucket, netting, and source metadata for one DRC row."""

    position_id: str
    source_row_id: str
    issuer_id: str | None
    obligor_id: str | None
    bucket_key: str | None
    netting_group_ids: tuple[str, ...]
    gross_jtd_ids: tuple[str, ...]
    scaled_jtd_ids: tuple[str, ...]
    maturity_years: float | None
    lgd_source: str | None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible drilldown row.

        Returns
        -------
        dict[str, object]
            Serialized DRC metadata row.
        """

        return {
            "position_id": self.position_id,
            "source_row_id": self.source_row_id,
            "issuer_id": self.issuer_id,
            "obligor_id": self.obligor_id,
            "bucket_key": self.bucket_key,
            "netting_group_ids": list(self.netting_group_ids),
            "gross_jtd_ids": list(self.gross_jtd_ids),
            "scaled_jtd_ids": list(self.scaled_jtd_ids),
            "maturity_years": self.maturity_years,
            "lgd_source": self.lgd_source,
        }


def build_drc_risk_factor_metadata_rows(
    result: DrcCapitalResult,
) -> tuple[DrcRiskFactorMetadataRow, ...]:
    """Project preserved DRC source and issuer metadata from a capital result.

    Parameters
    ----------
    result
        Completed DRC capital result carrying input positions and intermediate
        audit records.

    Returns
    -------
    tuple[DrcRiskFactorMetadataRow, ...]
        Deterministically ordered drilldown metadata rows.
    """

    gross_by_position: dict[str, set[str]] = {}
    lgd_by_position: dict[str, str] = {}
    for gross in result.gross_jtds or ():
        gross_by_position.setdefault(gross.position_id, set()).add(gross.gross_jtd_id)
        lgd_by_position.setdefault(gross.position_id, gross.lgd_source)

    scaled_by_position: dict[str, set[str]] = {}
    for scaled in result.maturity_scaled_jtds or ():
        scaled_by_position.setdefault(scaled.position_id, set()).add(scaled.scaled_jtd_id)

    netting_by_position: dict[str, set[str]] = {}
    for net in result.net_jtds or ():
        for position_id in net.position_ids:
            netting_by_position.setdefault(position_id, set()).add(net.netting_group_id)

    rows = [
        DrcRiskFactorMetadataRow(
            position_id=position.position_id,
            source_row_id=position.source_row_id,
            issuer_id=position.issuer_id,
            obligor_id=position.issuer_id,
            bucket_key=position.bucket_key,
            netting_group_ids=tuple(sorted(netting_by_position.get(position.position_id, ()))),
            gross_jtd_ids=tuple(sorted(gross_by_position.get(position.position_id, ()))),
            scaled_jtd_ids=tuple(sorted(scaled_by_position.get(position.position_id, ()))),
            maturity_years=position.maturity_years,
            lgd_source=lgd_by_position.get(position.position_id),
        )
        for position in result.input_positions or ()
    ]
    return tuple(sorted(rows, key=lambda row: (row.position_id, row.source_row_id)))


__all__ = ["DrcRiskFactorMetadataRow", "build_drc_risk_factor_metadata_rows"]
