"""Parser for minimal v1 IMA mapping specs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from frtb_ima.adapters._daily_pnl_mapping_types import (
    DailyPnlTableMapping,
    FieldMapping,
    ImaMappingSpec,
    MappingSpecError,
)
from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.adapters._rfet_observation_mapping_types import RfetObservationTableMapping
from frtb_ima.adapters._risk_factor_master_mapping_types import RiskFactorMasterTableMapping
from frtb_ima.adapters._scenario_pnl_mapping_types import ScenarioPnlTableMapping


def load_ima_mapping_spec(path: str | Path) -> ImaMappingSpec:
    """Load a v1 IMA ``mapping.yaml`` file.

    Parameters
    ----------
    path : str | Path
        Filesystem path to the mapping spec.

    Returns
    -------
    ImaMappingSpec
        Parsed and validated v1 IMA mapping spec.
    """

    spec_path = Path(path)
    return parse_ima_mapping_spec(spec_path.read_text(encoding="utf-8"))


def parse_ima_mapping_spec(text: str) -> ImaMappingSpec:
    """Parse a v1 IMA mapping spec from a small YAML subset.

    Parameters
    ----------
    text : str
        Mapping spec text using the supported YAML subset.

    Returns
    -------
    ImaMappingSpec
        Parsed and validated v1 IMA mapping spec.
    """

    raw = _parse_yaml_mapping(text)
    return _mapping_spec_from_raw(raw, source_text=text)


def _mapping_spec_from_raw(raw: Mapping[str, object], *, source_text: str) -> ImaMappingSpec:
    tables = _required_mapping(raw, "tables")
    daily_pnl = tables.get("daily_pnl_vectors")
    if daily_pnl is not None and not isinstance(daily_pnl, Mapping):
        raise MappingSpecError("daily_pnl_vectors must be a mapping")
    sign_convention = _required_mapping(raw, "sign_convention")
    if "pnl_positive_means" not in sign_convention:
        raise MappingSpecError("sign_convention.pnl_positive_means is required")
    risk_factor_master_raw = tables.get("risk_factor_master")
    if risk_factor_master_raw is not None and not isinstance(risk_factor_master_raw, Mapping):
        raise MappingSpecError("risk_factor_master must be a mapping")
    risk_factor_master = (
        _risk_factor_master_mapping(risk_factor_master_raw)
        if isinstance(risk_factor_master_raw, Mapping)
        else None
    )
    rfet_raw = tables.get("rfet_observations")
    if rfet_raw is not None and not isinstance(rfet_raw, Mapping):
        raise MappingSpecError("rfet_observations must be a mapping")
    rfet = _rfet_observation_mapping(rfet_raw) if isinstance(rfet_raw, Mapping) else None
    scenario_pnl_raw = tables.get("scenario_pnl_vectors")
    if scenario_pnl_raw is not None and not isinstance(scenario_pnl_raw, Mapping):
        raise MappingSpecError("scenario_pnl_vectors must be a mapping")
    scenario_pnl = (
        _scenario_pnl_mapping(scenario_pnl_raw) if isinstance(scenario_pnl_raw, Mapping) else None
    )
    return ImaMappingSpec(
        mapping_spec_version=_required_int(raw, "mapping_spec_version"),
        target_schema=_required_str(raw, "target_schema"),
        source_system=_required_str(raw, "source_system"),
        base_currency=_required_str(raw, "base_currency"),
        timezone=_required_str(raw, "timezone"),
        pnl_positive_means=_required_str(sign_convention, "pnl_positive_means"),
        daily_pnl_vectors=(
            DailyPnlTableMapping(
                source=_required_str(daily_pnl, "source"),
                target=_required_str(daily_pnl, "target"),
                fields=_field_mappings(_required_mapping(daily_pnl, "fields")),
            )
            if isinstance(daily_pnl, Mapping)
            else None
        ),
        risk_factor_master=risk_factor_master,
        rfet_observations=rfet,
        scenario_pnl_vectors=scenario_pnl,
        risk_factor_aliases=_string_mapping(
            raw.get("risk_factor_aliases", {}), "risk_factor_aliases"
        ),
        spec_hash=stable_mapping_hash({"mapping_spec": source_text}),
    )


def _risk_factor_master_mapping(raw: Mapping[str, object]) -> RiskFactorMasterTableMapping:
    return RiskFactorMasterTableMapping(
        source=_required_str(raw, "source"),
        target=_required_str(raw, "target"),
        fields=_field_mappings(_required_mapping(raw, "fields")),
    )


def _rfet_observation_mapping(raw: Mapping[str, object]) -> RfetObservationTableMapping:
    return RfetObservationTableMapping(
        source=_required_str(raw, "source"),
        target=_required_str(raw, "target"),
        fields=_field_mappings(_required_mapping(raw, "fields")),
    )


def _scenario_pnl_mapping(raw: Mapping[str, object]) -> ScenarioPnlTableMapping:
    return ScenarioPnlTableMapping(
        source=_required_str(raw, "source"),
        target=_required_str(raw, "target"),
        fields=_field_mappings(_required_mapping(raw, "fields")),
        missing_cells=_optional_str(raw, "missing_cells", default="reject"),
    )


def _field_mappings(raw_fields: Mapping[str, object]) -> Mapping[str, FieldMapping]:
    return {
        str(target): _field_mapping_from_value(target=str(target), value=value)
        for target, value in raw_fields.items()
    }


def _field_mapping_from_value(*, target: str, value: object) -> FieldMapping:
    if isinstance(value, str):
        if not value:
            raise MappingSpecError(f"{target} source column must be non-empty")
        return FieldMapping(source=value)
    if isinstance(value, Mapping):
        source = value.get("source")
        constant = value.get("constant")
        values = _string_mapping(value.get("values", {}), f"{target}.values")
        if source is not None and not isinstance(source, str):
            raise MappingSpecError(f"{target}.source must be a string")
        return FieldMapping(
            source=source, constant=None if constant is None else str(constant), values=values
        )
    raise MappingSpecError(f"{target} field mapping must be a source column or mapping")


def _parse_yaml_mapping(text: str) -> dict[str, object]:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_yaml_comment(raw_line).rstrip()
        if not line.strip():
            continue
        if "\t" in raw_line:
            raise MappingSpecError(f"tabs are not supported in mapping YAML at line {line_number}")
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise MappingSpecError(f"expected key/value mapping at line {line_number}")
        key, raw_value = stripped.split(":", 1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise MappingSpecError(f"invalid indentation at line {line_number}")
        value_text = raw_value.strip()
        if value_text:
            stack[-1][1][key.strip()] = _parse_yaml_scalar(value_text)
        else:
            child: dict[str, object] = {}
            stack[-1][1][key.strip()] = child
            stack.append((indent, child))
    return root


def _strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def _parse_yaml_scalar(value: str) -> object:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _required_mapping(raw: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    value = raw.get(field_name)
    if not isinstance(value, Mapping):
        raise MappingSpecError(f"{field_name} must be a mapping")
    return value


def _required_str(raw: Mapping[str, object], field_name: str) -> str:
    value = raw.get(field_name)
    if value is None:
        raise MappingSpecError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise MappingSpecError(f"{field_name} must be non-empty")
    return text


def _optional_str(raw: Mapping[str, object], field_name: str, *, default: str) -> str:
    value = raw.get(field_name, default)
    if value is None:
        return default
    text = str(value).strip()
    return default if not text else text


def _required_int(raw: Mapping[str, object], field_name: str) -> int:
    value = raw.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MappingSpecError(f"{field_name} must be an integer")
    return value


def _string_mapping(value: object, field_name: str) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise MappingSpecError(f"{field_name} must be a mapping")
    return {str(key): str(item) for key, item in value.items()}
