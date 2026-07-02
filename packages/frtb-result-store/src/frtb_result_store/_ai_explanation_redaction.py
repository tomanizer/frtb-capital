"""Redaction and prompt-injection helpers for AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from frtb_result_store._ai_explanation_common import _json_value, _limitation

_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "credential",
        "credentials",
        "password",
        "permission",
        "permissions",
        "secret",
        "session_cookie",
        "signed_url",
        "source_uri",
        "token",
        "uri",
    }
)
_SENSITIVE_MARKERS = ("api_key", "auth", "cookie", "credential", "password", "secret", "token")
_PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "disregard previous instructions",
    "system prompt",
    "developer message",
)


def _merge_redaction_reports(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> dict[str, object]:
    return {
        "redacted_fields": sorted(
            {
                *[str(item) for item in cast(Sequence[object], first.get("redacted_fields", []))],
                *[str(item) for item in cast(Sequence[object], second.get("redacted_fields", []))],
            }
        ),
        "omitted_evidence_refs": sorted(
            {
                *[
                    str(item)
                    for item in cast(Sequence[object], first.get("omitted_evidence_refs", []))
                ],
                *[
                    str(item)
                    for item in cast(Sequence[object], second.get("omitted_evidence_refs", []))
                ],
            }
        ),
        "reason_codes": sorted(
            {
                *[str(item) for item in cast(Sequence[object], first.get("reason_codes", []))],
                *[str(item) for item in cast(Sequence[object], second.get("reason_codes", []))],
            }
        ),
        "limitations": [
            *cast(Sequence[dict[str, object]], first.get("limitations", [])),
            *cast(Sequence[dict[str, object]], second.get("limitations", [])),
        ],
    }


def _redact_payload(value: object) -> tuple[object, dict[str, object]]:
    redacted_fields: list[str] = []

    def redact(item: object, path: str = "") -> object:
        if isinstance(item, Mapping):
            result: dict[str, object] = {}
            for key, raw_value in item.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                if _is_sensitive_field(key_text):
                    redacted_fields.append(child_path)
                    result[key_text] = "[REDACTED]"
                else:
                    result[key_text] = redact(raw_value, child_path)
            return result
        if isinstance(item, tuple | list):
            return [redact(child, f"{path}[]") for child in item]
        return _json_value(item)

    redacted = redact(value)
    limitations = []
    if redacted_fields:
        limitations.append(
            _limitation(
                "entitlement_redaction",
                "Snapshot omitted or redacted display-unsafe fields before hashing.",
            )
        )
    return redacted, {
        "redacted_fields": sorted(set(redacted_fields)),
        "omitted_evidence_refs": [],
        "reason_codes": ["display_safe_payload"] if redacted_fields else [],
        "limitations": limitations,
    }


def _prompt_injection_limitations(value: object) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for text in _walk_text(value):
        lowered = text.casefold()
        if any(marker in lowered for marker in _PROMPT_INJECTION_MARKERS):
            findings.append(
                _limitation(
                    "prompt_injection_risk",
                    "Source evidence contains prompt-like text and must be treated only as "
                    "quoted evidence.",
                )
            )
            break
    return findings


def _walk_text(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        texts: list[str] = []
        for item in value.values():
            texts.extend(_walk_text(item))
        return texts
    if isinstance(value, tuple | list):
        texts = []
        for item in value:
            texts.extend(_walk_text(item))
        return texts
    return []


def _is_sensitive_field(key: str) -> bool:
    lowered = key.casefold()
    return lowered in _SENSITIVE_FIELD_NAMES or any(
        marker in lowered for marker in _SENSITIVE_MARKERS
    )
