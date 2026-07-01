"""RRAO residual-risk metadata drilldown helpers."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_rrao.data_models import RraoCapitalResult


@dataclass(frozen=True)
class RraoRiskFactorMetadataRow:
    """Residual-risk category, source, and classification metadata for one line."""

    position_id: str
    source_row_id: str
    residual_risk_category: str
    evidence_type: str
    classification: str
    reason_code: str
    is_excluded: bool
    exclusion_reason: str | None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible drilldown row.

        Returns
        -------
        dict[str, object]
            Serialized RRAO metadata row.
        """

        return {
            "position_id": self.position_id,
            "source_row_id": self.source_row_id,
            "residual_risk_category": self.residual_risk_category,
            "evidence_type": self.evidence_type,
            "classification": self.classification,
            "reason_code": self.reason_code,
            "is_excluded": self.is_excluded,
            "exclusion_reason": self.exclusion_reason,
        }


def build_rrao_risk_factor_metadata_rows(
    result: RraoCapitalResult,
) -> tuple[RraoRiskFactorMetadataRow, ...]:
    """Project residual-risk source and classification metadata from a result.

    Parameters
    ----------
    result
        Completed RRAO capital result carrying line-level audit records.

    Returns
    -------
    tuple[RraoRiskFactorMetadataRow, ...]
        Deterministically ordered residual-risk metadata rows.
    """

    rows = [
        RraoRiskFactorMetadataRow(
            position_id=line.position_id,
            source_row_id=line.source_row_id,
            residual_risk_category=line.classification.value,
            evidence_type=line.evidence_type.value,
            classification=line.classification.value,
            reason_code=line.reason_code,
            is_excluded=line.is_excluded,
            exclusion_reason=(
                None if line.exclusion_reason is None else line.exclusion_reason.value
            ),
        )
        for line in (*(result.lines or ()), *(result.excluded_lines or ()))
    ]
    return tuple(sorted(rows, key=lambda row: (row.position_id, row.source_row_id)))


__all__ = ["RraoRiskFactorMetadataRow", "build_rrao_risk_factor_metadata_rows"]
