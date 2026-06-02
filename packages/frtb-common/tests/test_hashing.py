"""Tests for package-neutral deterministic hashing helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import pytest
from frtb_common import (
    is_sha256_hex,
    require_sha256_hex,
    stable_json_dumps,
    stable_json_hash,
)


class _Regime(StrEnum):
    BASEL = "basel"


@dataclass(frozen=True)
class _Payload:
    amount: float
    regime: _Regime

    def as_dict(self) -> dict[str, object]:
        return {"amount": self.amount, "regime": self.regime}


def test_stable_json_dumps_is_compact_sorted_and_jsonable() -> None:
    payload = {
        "when": date(2026, 6, 2),
        "nested": _Payload(amount=1.5, regime=_Regime.BASEL),
        "z": 3,
        "a": ("x", "y"),
    }

    encoded = stable_json_dumps(payload)

    assert encoded == (
        '{"a":["x","y"],"nested":{"amount":1.5,"regime":"basel"},"when":"2026-06-02","z":3}'
    )
    assert json.loads(encoded)["nested"]["regime"] == "basel"


def test_stable_json_hash_matches_sha256_of_stable_json_dumps() -> None:
    payload = {"b": 2, "a": _Regime.BASEL}
    expected = hashlib.sha256(bytes(stable_json_dumps(payload), "utf-8")).hexdigest()

    assert stable_json_hash(payload) == expected
    assert stable_json_hash({"a": _Regime.BASEL, "b": 2}) == expected


def test_stable_json_hash_is_input_sensitive() -> None:
    assert stable_json_hash({"amount": 1.0}) != stable_json_hash({"amount": 2.0})


def test_sha256_hex_validation_accepts_lowercase_digest_only() -> None:
    digest = "a" * 64

    assert is_sha256_hex(digest)
    assert require_sha256_hex(digest, field="input_hash") == digest

    assert not is_sha256_hex("A" * 64)
    assert not is_sha256_hex("a" * 63)
    assert not is_sha256_hex("g" * 64)
    assert not is_sha256_hex(123)


def test_require_sha256_hex_reports_field_name() -> None:
    with pytest.raises(ValueError, match="profile_hash must be a sha256 hex digest"):
        require_sha256_hex("not-a-digest", field="profile_hash")


def test_hashing_helpers_are_exported_from_top_level_package() -> None:
    import frtb_common

    assert frtb_common.stable_json_hash is stable_json_hash
    assert frtb_common.stable_json_dumps is stable_json_dumps
    assert frtb_common.is_sha256_hex is is_sha256_hex
    assert frtb_common.require_sha256_hex is require_sha256_hex
