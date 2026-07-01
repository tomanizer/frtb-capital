"""CVA risk-factor-adjacent metadata drilldown helpers."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_cva.data_models import CvaCapitalResult


@dataclass(frozen=True)
class CvaRiskFactorMetadataRow:
    """Counterparty, credit-spread, hedge, and source metadata for CVA drilldown."""

    row_id: str
    source_row_id: str | None
    counterparty_id: str | None
    reference_key: str | None
    bucket_id: str | None
    risk_class: str | None
    sensitivity_ids: tuple[str, ...]
    sector: str | None
    credit_quality: str | None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible drilldown row.

        Returns
        -------
        dict[str, object]
            Serialized CVA metadata row.
        """

        return {
            "row_id": self.row_id,
            "source_row_id": self.source_row_id,
            "counterparty_id": self.counterparty_id,
            "reference_key": self.reference_key,
            "bucket_id": self.bucket_id,
            "risk_class": self.risk_class,
            "sensitivity_ids": list(self.sensitivity_ids),
            "sector": self.sector,
            "credit_quality": self.credit_quality,
        }


def build_cva_risk_factor_metadata_rows(
    result: CvaCapitalResult,
) -> tuple[CvaRiskFactorMetadataRow, ...]:
    """Project CVA counterparty and SA-CVA source metadata from a result.

    Parameters
    ----------
    result
        Completed CVA capital result carrying BA-CVA and SA-CVA audit records.

    Returns
    -------
    tuple[CvaRiskFactorMetadataRow, ...]
        Deterministically ordered CVA metadata rows.
    """

    rows: list[CvaRiskFactorMetadataRow] = []
    for line in result.ba_cva_netting_set_lines or ():
        rows.append(
            CvaRiskFactorMetadataRow(
                row_id=line.netting_set_id,
                source_row_id=line.source_row_id,
                counterparty_id=line.counterparty_id,
                reference_key=line.counterparty_id,
                bucket_id=None,
                risk_class="BA_CVA",
                sensitivity_ids=(),
                sector=line.sector.value,
                credit_quality=line.credit_quality.value,
            )
        )
    for risk_class in result.sa_cva_risk_class_capitals or ():
        for bucket in risk_class.bucket_capitals:
            rows.append(
                CvaRiskFactorMetadataRow(
                    row_id=f"{risk_class.risk_class.value}:{bucket.bucket_id}",
                    source_row_id=None,
                    counterparty_id=None,
                    reference_key=bucket.bucket_id,
                    bucket_id=bucket.bucket_id,
                    risk_class=risk_class.risk_class.value,
                    sensitivity_ids=tuple(sorted(bucket.sensitivity_ids)),
                    sector=None,
                    credit_quality=None,
                )
            )
    return tuple(sorted(rows, key=lambda row: (row.risk_class or "", row.row_id)))


__all__ = ["CvaRiskFactorMetadataRow", "build_cva_risk_factor_metadata_rows"]
