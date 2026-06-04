from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from frtb_common import jsonable, stable_json_hash
from frtb_drc._hashing import hash_payload


class _RiskClass(StrEnum):
    NON_SEC = "NON_SECURITISATION"


@dataclass(frozen=True)
class _Lineage:
    source_row_id: str

    def as_dict(self) -> dict[str, object]:
        return {"source_row_id": self.source_row_id}


def test_hash_payload_delegates_to_stable_json_hash() -> None:
    payload = {
        "calculation_date": date(2026, 6, 4),
        "risk_class": _RiskClass.NON_SEC,
        "lineage": _Lineage("row-1"),
        "amounts": (100.0, 50.0),
    }

    assert hash_payload(payload) == stable_json_hash(payload)


def test_hash_payload_preserves_legacy_jsonable_digest() -> None:
    payload = {
        "calculation_date": date(2026, 6, 4),
        "risk_class": _RiskClass.NON_SEC,
        "lineage": _Lineage("row-1"),
        "amounts": (100.0, 50.0),
    }
    encoded = json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")

    assert hash_payload(payload) == hashlib.sha256(encoded).hexdigest()
