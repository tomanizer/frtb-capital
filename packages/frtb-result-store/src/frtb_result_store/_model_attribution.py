"""Capital attribution record dataclass."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from frtb_common import AttributionMethod, CapitalContribution

from frtb_result_store.model_enums import VALID_ATTRIBUTION_TARGET_TYPES, ResultStoreContractError
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _registered_upper_value,
    _require_finite_number,
    _require_non_empty_text,
    _validate_optional_text,
)


@dataclass(frozen=True, slots=True)
class CapitalAttributionRecord:
    """Attribution row for Euler, residual, or unsupported contribution methods."""

    run_id: str
    node_id: str
    contribution_id: str
    source_id: str
    source_level: str
    category: str
    base_amount: float
    method: AttributionMethod | str
    bucket_key: str | None = None
    marginal_multiplier: float | None = None
    contribution: float | None = None
    residual: float = 0.0
    reason: str = ""
    target_type: str | None = None
    target_id: str | None = None
    unsupported_reason: str | None = None
    artifact_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _require_non_empty_text(self.contribution_id, "contribution_id")
        _require_non_empty_text(self.source_id, "source_id")
        _require_non_empty_text(self.source_level, "source_level")
        object.__setattr__(
            self,
            "source_level",
            _registered_upper_value(
                self.source_level,
                VALID_ATTRIBUTION_TARGET_TYPES,
                "source_level",
            ),
        )
        object.__setattr__(self, "method", _coerce_enum(self.method, AttributionMethod, "method"))
        if self.target_type is None:
            object.__setattr__(self, "target_type", self.source_level)
        else:
            object.__setattr__(
                self,
                "target_type",
                _registered_upper_value(
                    self.target_type,
                    VALID_ATTRIBUTION_TARGET_TYPES,
                    "target_type",
                ),
            )
        if self.target_id is None:
            object.__setattr__(self, "target_id", self.source_id)
        else:
            _require_non_empty_text(self.target_id, "target_id")
        _validate_optional_text(self.artifact_id, "artifact_id")
        _validate_optional_text(self.bucket_key, "bucket_key")
        _require_non_empty_text(self.category, "category")
        object.__setattr__(
            self, "base_amount", _require_finite_number(self.base_amount, "base_amount")
        )
        if self.marginal_multiplier is not None:
            object.__setattr__(
                self,
                "marginal_multiplier",
                _require_finite_number(self.marginal_multiplier, "marginal_multiplier"),
            )
        if self.contribution is not None:
            object.__setattr__(
                self,
                "contribution",
                _require_finite_number(self.contribution, "contribution"),
            )
        object.__setattr__(self, "residual", _require_finite_number(self.residual, "residual"))
        if not isinstance(self.reason, str):
            raise ResultStoreContractError("reason must be text", field="reason")
        unsupported_reason = self.unsupported_reason
        if unsupported_reason is None:
            unsupported_reason = (
                self.reason
                if self.method in (AttributionMethod.RESIDUAL, AttributionMethod.UNSUPPORTED)
                else ""
            )
        if not isinstance(unsupported_reason, str):
            raise ResultStoreContractError(
                "unsupported_reason must be text",
                field="unsupported_reason",
            )
        object.__setattr__(self, "unsupported_reason", unsupported_reason)
        if not self.reason and unsupported_reason:
            object.__setattr__(self, "reason", unsupported_reason)
        if self.method == AttributionMethod.ANALYTICAL_EULER:
            if self.marginal_multiplier is None or self.contribution is None:
                raise ResultStoreContractError(
                    "analytical Euler attribution requires marginal_multiplier and contribution",
                    field="method",
                )
        _freeze_metadata(self, self.metadata)

    @classmethod
    def from_contribution(
        cls,
        *,
        run_id: str,
        node_id: str,
        contribution: CapitalContribution,
        target_type: str | None = None,
        target_id: str | None = None,
        artifact_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CapitalAttributionRecord:
        """Create a stored attribution record from the shared contribution DTO.
        Parameters
        ----------
        run_id : str
            Run id.
        node_id : str
            Node id.
        contribution : CapitalContribution
            Contribution.
        target_type : str | None, optional
            Target type.
        target_id : str | None, optional
            Target id.
        artifact_id : str | None, optional
            Artifact id.
        metadata : Mapping[str, object] | None, optional
            Metadata.

        Returns
        -------
        CapitalAttributionRecord
            Result of the operation.
        """

        return cls(
            run_id=run_id,
            node_id=node_id,
            contribution_id=contribution.contribution_id,
            source_id=contribution.source_id,
            source_level=contribution.source_level,
            bucket_key=contribution.bucket_key,
            category=contribution.category,
            base_amount=contribution.base_amount,
            marginal_multiplier=contribution.marginal_multiplier,
            contribution=contribution.contribution,
            method=contribution.method,
            residual=contribution.residual,
            reason=contribution.reason,
            target_type=target_type,
            target_id=target_id,
            unsupported_reason=(
                contribution.reason
                if contribution.method
                in (AttributionMethod.RESIDUAL, AttributionMethod.UNSUPPORTED)
                else ""
            ),
            artifact_id=artifact_id,
            metadata={} if metadata is None else metadata,
        )

    @property
    def attribution_id(self) -> str:
        """Stable storage alias for the shared contribution identifier.
        Returns
        -------
        str
            Result of the operation.
        """

        return self.contribution_id
