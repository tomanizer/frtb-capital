"""
Post-run audit records, NDJSON serialisation, and Markdown report rendering.

These dataclasses sit at the orchestration boundary. They collect decomposed
calculation results into serialisable records without adding storage or
analytics dependencies to the calculation layer.

Regulatory traceability:
    Supports auditability and run traceability for Basel MAR31-MAR33, U.S. NPR
    2.0 model-risk governance expectations, and EU CRR internal-model
    governance. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from frtb_common import CalculationScope
from frtb_common.serialization import jsonable

from frtb_ima._mapping_utils import empty_mapping as _empty_mapping
from frtb_ima._mapping_utils import freeze_mapping as _freeze_mapping
from frtb_ima._version import __version__
from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.input_manifest import CapitalRunInputManifest
from frtb_ima.org_scope import add_scope_payload, validate_scope_metadata
from frtb_ima.regimes import (
    DEFAULT_MODEL_VERSION,
    DeskEligibilityStatus,
    ModelVersion,
    RegulatoryRegime,
    get_policy,
)


@dataclass(frozen=True)
class DeskAuditRecord:
    """Serialisable audit record for one desk in one capital run."""

    run_id: str
    desk_id: str
    regime: str
    desk_eligibility: str = field(default="IMA_ELIGIBLE", kw_only=True)
    model_version: ModelVersion = field(default=DEFAULT_MODEL_VERSION, kw_only=True)
    code_version: str = field(default=__version__, kw_only=True)
    policy_hash: str = field(default="", kw_only=True)
    inputs_hash: str = field(kw_only=True)
    imcc: Mapping[str, object]
    ses: Mapping[str, object]
    pla: Mapping[str, object]
    backtesting: Mapping[str, object]
    capital: Mapping[str, object]
    elapsed_seconds: float
    nmrf_valuation: Mapping[str, object] = field(default_factory=_empty_mapping)
    input_manifest: CapitalRunInputManifest | None = field(default=None, kw_only=True)
    require_input_manifest: bool = field(default=False, kw_only=True)
    org_scope: CalculationScope | None = None
    as_of_date: date | None = None
    notes: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.desk_id:
            raise ValueError("desk_id must be non-empty")
        if not self.regime:
            raise ValueError("regime must be non-empty")
        model_version = _coerce_model_version(self.model_version)
        code_version = str(self.code_version)
        policy_hash = (
            str(self.policy_hash) if self.policy_hash else _default_policy_hash(self.regime)
        )
        if not code_version:
            raise ValueError("code_version must be non-empty")
        _validate_sha256_hex(policy_hash, "policy_hash")
        _validate_sha256_hex(self.inputs_hash, "inputs_hash")
        try:
            desk_eligibility = DeskEligibilityStatus(self.desk_eligibility).value
        except ValueError as exc:
            raise ValueError("desk_eligibility must be a DeskEligibilityStatus value") from exc
        if self.elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be non-negative")
        if self.require_input_manifest and self.input_manifest is None:
            raise ValueError("input_manifest is required for production-style audit records")
        if self.as_of_date is None and self.input_manifest is not None:
            object.__setattr__(self, "as_of_date", self.input_manifest.as_of_date)
        elif (
            self.input_manifest is not None
            and self.as_of_date is not None
            and self.input_manifest.as_of_date != self.as_of_date
        ):
            raise ValueError("input_manifest as_of_date must match audit record as_of_date")
        object.__setattr__(self, "desk_eligibility", desk_eligibility)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "code_version", code_version)
        object.__setattr__(self, "policy_hash", policy_hash)
        object.__setattr__(self, "inputs_hash", str(self.inputs_hash))
        object.__setattr__(
            self,
            "org_scope",
            validate_scope_metadata(self.org_scope, field="DeskAuditRecord.org_scope"),
        )
        object.__setattr__(self, "imcc", _freeze_mapping(self.imcc))
        object.__setattr__(self, "ses", _freeze_mapping(self.ses))
        object.__setattr__(self, "pla", _freeze_mapping(self.pla))
        object.__setattr__(self, "backtesting", _freeze_mapping(self.backtesting))
        object.__setattr__(self, "capital", _freeze_mapping(self.capital))
        object.__setattr__(
            self,
            "nmrf_valuation",
            _freeze_mapping(self.nmrf_valuation),
        )
        object.__setattr__(self, "notes", tuple(self.notes))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return add_scope_payload(
            {
                "run_id": self.run_id,
                "desk_id": self.desk_id,
                "regime": self.regime,
                "desk_eligibility": self.desk_eligibility,
                "model_version": self.model_version.as_dict(),
                "code_version": self.code_version,
                "policy_hash": self.policy_hash,
                "inputs_hash": self.inputs_hash,
                "as_of_date": self.as_of_date.isoformat() if self.as_of_date is not None else None,
                "imcc": jsonable(self.imcc),
                "ses": jsonable(self.ses),
                "pla": jsonable(self.pla),
                "backtesting": jsonable(self.backtesting),
                "capital": jsonable(self.capital),
                "nmrf_valuation": jsonable(self.nmrf_valuation),
                "input_manifest": (
                    self.input_manifest.compact_summary()
                    if self.input_manifest is not None
                    else None
                ),
                "elapsed_seconds": self.elapsed_seconds,
                "notes": list(self.notes),
                "metadata": jsonable(self.metadata),
            },
            self.org_scope,
        )

    def to_json_line(self) -> str:
        """Return this desk audit record as one NDJSON line.
        Returns
        -------
        str
            Result of the operation.
        """
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class CapitalRunAuditLog:
    """Collection of desk audit records for one capital run."""

    run_id: str
    regime: str
    desk_records: tuple[DeskAuditRecord, ...]
    model_version: ModelVersion = field(default=DEFAULT_MODEL_VERSION, kw_only=True)
    code_version: str = field(default=__version__, kw_only=True)
    policy_hash: str = field(default="", kw_only=True)
    inputs_hash: str = field(default="", kw_only=True)
    input_manifest: CapitalRunInputManifest | None = field(default=None, kw_only=True)
    require_input_manifest: bool = field(default=False, kw_only=True)
    calculation_scope: CalculationScope | None = None
    as_of_date: date | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.regime:
            raise ValueError("regime must be non-empty")
        model_version = _coerce_model_version(self.model_version)
        code_version = str(self.code_version)
        policy_hash = (
            str(self.policy_hash) if self.policy_hash else _default_policy_hash(self.regime)
        )
        desk_records = tuple(self.desk_records)
        inputs_hash = (
            str(self.inputs_hash) if self.inputs_hash else _default_inputs_hash(desk_records)
        )
        if not code_version:
            raise ValueError("code_version must be non-empty")
        _validate_sha256_hex(policy_hash, "policy_hash")
        _validate_sha256_hex(inputs_hash, "inputs_hash")
        if self.require_input_manifest and self.input_manifest is None:
            raise ValueError("input_manifest is required for production-style audit logs")
        if self.as_of_date is None and self.input_manifest is not None:
            object.__setattr__(self, "as_of_date", self.input_manifest.as_of_date)
        elif (
            self.input_manifest is not None
            and self.as_of_date is not None
            and self.input_manifest.as_of_date != self.as_of_date
        ):
            raise ValueError("input_manifest as_of_date must match audit log as_of_date")
        desk_ids = [record.desk_id for record in desk_records]
        if len(desk_ids) != len(set(desk_ids)):
            raise ValueError("desk_records contains duplicate desk_id values")
        for record in desk_records:
            if record.run_id != self.run_id:
                raise ValueError("all desk_records must have the same run_id")
            if record.regime != self.regime:
                raise ValueError("all desk_records must have the same regime")
            if record.model_version != model_version:
                raise ValueError("all desk_records must have the same model_version")
            if record.code_version != code_version:
                raise ValueError("all desk_records must have the same code_version")
            if record.policy_hash != policy_hash:
                raise ValueError("all desk_records must have the same policy_hash")
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "code_version", code_version)
        object.__setattr__(self, "policy_hash", policy_hash)
        object.__setattr__(self, "inputs_hash", inputs_hash)
        object.__setattr__(
            self,
            "calculation_scope",
            validate_scope_metadata(
                self.calculation_scope,
                field="CapitalRunAuditLog.calculation_scope",
            ),
        )
        object.__setattr__(self, "desk_records", desk_records)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def desk_count(self) -> int:
        """Number of desks in the audit log.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.desk_records)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return add_scope_payload(
            {
                "run_id": self.run_id,
                "regime": self.regime,
                "model_version": self.model_version.as_dict(),
                "code_version": self.code_version,
                "policy_hash": self.policy_hash,
                "inputs_hash": self.inputs_hash,
                "input_manifest": (
                    self.input_manifest.compact_summary()
                    if self.input_manifest is not None
                    else None
                ),
                "as_of_date": self.as_of_date.isoformat() if self.as_of_date is not None else None,
                "desk_count": self.desk_count,
                "desk_records": [record.as_dict() for record in self.desk_records],
                "metadata": jsonable(self.metadata),
            },
            self.calculation_scope,
            key="calculation_scope",
        )

    def to_ndjson(self) -> str:
        """Return desk records as newline-delimited JSON.
        Returns
        -------
        str
            Result of the operation.
        """
        return audit_records_to_ndjson(self.desk_records)


def audit_records_to_ndjson(records: Iterable[DeskAuditRecord]) -> str:
    """Serialise desk audit records to newline-delimited JSON.
    Parameters
    ----------
    records : Iterable[DeskAuditRecord]
        Records.

    Returns
    -------
    str
        Result of the operation.
    """
    lines = [record.to_json_line() for record in records]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def render_capital_run_audit_report(
    log: CapitalRunAuditLog,
    *,
    title: str = "FRTB IMA Capital Run Audit Report",
) -> str:
    """Render a deterministic Markdown audit report for a capital run.

    This is an orchestration-layer report view over already-computed audit
    records. It does not recalculate capital and does not attempt to be a final
    regulatory disclosure template.
    Parameters
    ----------
    log : CapitalRunAuditLog
        Log.
    title : str, optional
        Title.

    Returns
    -------
    str
        Result of the operation.
    """
    lines: list[str] = [
        f"# {title}",
        "",
        "> Prototype report only. Not for regulatory reporting.",
        "> NPR 2.0 values are proposed-rule parameters and are not final regulatory capital.",
        "",
        "## Run identity",
        "",
    ]
    lines.extend(
        _markdown_table(
            ("Field", "Value"),
            (
                ("Model ID", log.model_version.model_id),
                ("Model version", log.model_version.version),
                ("Model description", log.model_version.description),
                ("Code version", log.code_version),
                ("Policy hash", log.policy_hash),
                ("Inputs hash", log.inputs_hash),
            ),
        )
    )
    lines.extend(["", "## Run summary", ""])
    lines.extend(
        _markdown_table(
            ("Field", "Value"),
            (
                ("Run ID", log.run_id),
                ("Regime", log.regime),
                (
                    "As of date",
                    log.as_of_date.isoformat() if log.as_of_date is not None else "",
                ),
                ("Desk count", log.desk_count),
            ),
        )
    )

    if log.metadata:
        lines.extend(_json_section("Run metadata", log.metadata, heading_level=3))
    if log.input_manifest is not None:
        lines.extend(
            _json_section("Input lineage", log.input_manifest.compact_summary(), heading_level=2)
        )

    lines.extend(["", "## Desk summary", ""])
    lines.extend(
        _markdown_table(
            (
                "Desk",
                "As of date",
                "IMCC",
                "Total SES",
                "Models-based capital",
                "PLA zone",
                "Backtesting eligible",
                "Elapsed seconds",
            ),
            (
                (
                    record.desk_id,
                    record.as_of_date.isoformat() if record.as_of_date is not None else "",
                    _format_report_value(_mapping_value(record.imcc, "imcc")),
                    _format_report_value(_mapping_value(record.ses, "total_ses", "ses")),
                    _format_report_value(_mapping_value(record.capital, "models_based_capital")),
                    _format_report_value(_mapping_value(record.pla, "zone", "pla_zone")),
                    _format_report_value(_mapping_value(record.backtesting, "model_eligible")),
                    _format_report_value(record.elapsed_seconds),
                )
                for record in log.desk_records
            ),
        )
    )

    for record in log.desk_records:
        lines.extend(["", f"## Desk: {record.desk_id}", ""])
        lines.extend(
            _markdown_table(
                ("Field", "Value"),
                (
                    ("Run ID", record.run_id),
                    ("Regime", record.regime),
                    ("Model ID", record.model_version.model_id),
                    ("Model version", record.model_version.version),
                    ("Code version", record.code_version),
                    ("Policy hash", record.policy_hash),
                    ("Inputs hash", record.inputs_hash),
                    (
                        "As of date",
                        record.as_of_date.isoformat() if record.as_of_date is not None else "",
                    ),
                    ("Elapsed seconds", _format_report_value(record.elapsed_seconds)),
                ),
            )
        )
        if record.notes:
            lines.extend(["", "### Notes", ""])
            lines.extend(f"- {_escape_table_cell(note)}" for note in record.notes)
        if record.input_manifest is not None:
            lines.extend(
                _json_section(
                    "Input lineage",
                    record.input_manifest.compact_summary(),
                    heading_level=3,
                )
            )
        lines.extend(_json_section("IMCC", record.imcc, heading_level=3))
        lines.extend(_json_section("SES", record.ses, heading_level=3))
        lines.extend(_json_section("PLA", record.pla, heading_level=3))
        lines.extend(_json_section("Backtesting", record.backtesting, heading_level=3))
        lines.extend(_json_section("Capital", record.capital, heading_level=3))
        if record.nmrf_valuation:
            lines.extend(
                _json_section(
                    "NMRF valuation",
                    record.nmrf_valuation,
                    heading_level=3,
                )
            )
        if record.metadata:
            lines.extend(_json_section("Desk metadata", record.metadata, heading_level=3))

    return "\n".join(lines).rstrip() + "\n"


def write_capital_run_audit_report(
    log: CapitalRunAuditLog,
    path: str | Path,
    *,
    title: str = "FRTB IMA Capital Run Audit Report",
) -> None:
    """Write a deterministic Markdown audit report for a capital run.
    Parameters
    ----------
    log : CapitalRunAuditLog
        Log.
    path : str | Path
        Path.
    title : str, optional
        Title.
    """
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_capital_run_audit_report(log, title=title),
        encoding="utf-8",
    )


def write_audit_records_ndjson(
    records: Iterable[DeskAuditRecord],
    path: str | Path,
    *,
    append: bool = False,
) -> None:
    """Write desk audit records to an NDJSON file.
    Parameters
    ----------
    records : Iterable[DeskAuditRecord]
        Records.
    path : str | Path
        Path.
    append : bool, optional
        Append.
    """
    mode = "a" if append else "w"
    with Path(path).open(mode, encoding="utf-8") as handle:
        handle.write(audit_records_to_ndjson(records))


def _coerce_model_version(value: ModelVersion | Mapping[str, object]) -> ModelVersion:
    if isinstance(value, ModelVersion):
        return value
    if isinstance(value, Mapping):
        return ModelVersion(
            model_id=str(value["model_id"]),
            version=str(value["version"]),
            description=str(value["description"]),
        )
    raise TypeError("model_version must be a ModelVersion")


def _default_policy_hash(regime: str) -> str:
    try:
        policy = get_policy(RegulatoryRegime(regime))
    except ValueError as exc:
        raise ValueError(
            "policy_hash must be provided when regime is not a known RegulatoryRegime"
        ) from exc
    return policy.policy_hash


def _default_inputs_hash(desk_records: tuple[DeskAuditRecord, ...]) -> str:
    if len(desk_records) == 1:
        return desk_records[0].inputs_hash
    return compute_inputs_hash(
        desk_inputs={
            record.desk_id: record.inputs_hash
            for record in sorted(desk_records, key=lambda item: item.desk_id)
        }
    )


def _validate_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")


def _json_section(
    title: str,
    value: object,
    *,
    heading_level: int,
) -> list[str]:
    heading = "#" * heading_level
    return [
        "",
        f"{heading} {title}",
        "",
        "```json",
        json.dumps(jsonable(value), indent=2, sort_keys=True),
        "```",
    ]


def _markdown_table(
    headers: tuple[str, ...],
    rows: Iterable[tuple[object, ...]],
) -> list[str]:
    header = "| " + " | ".join(_escape_table_cell(item) for item in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_escape_table_cell(item) for item in row) + " |" for row in rows]
    return [header, separator, *body]


def _mapping_value(mapping: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return ""


def _format_report_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return ""
    return str(value)


def _escape_table_cell(value: object) -> str:
    text = _format_report_value(value)
    return text.replace("|", "\\|").replace("\n", "<br>")
