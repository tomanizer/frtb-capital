from __future__ import annotations

import hashlib
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest
from frtb_common import stable_json_hash
from frtb_cva._payloads import (
    _optional_float_value,
    batch_lineage_payload,
    hash_payload,
    input_payload,
)
from frtb_cva.validation import CvaInputError


def test_payload_optional_float_preserves_numeric_null_semantics() -> None:
    assert _optional_float_value(np.nan) is None
    assert _optional_float_value("1.25") == pytest.approx(1.25)


def test_hash_payload_delegates_to_stable_json_hash(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    payload = input_payload(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )

    assert hash_payload(payload) == stable_json_hash(payload)


def test_hash_payload_preserves_legacy_compact_json_digest(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    payload = input_payload(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")

    assert hash_payload(payload) == hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize("value", [True, np.bool_(False), "not numeric", object()])
def test_payload_optional_float_rejects_non_numeric_values(value: object) -> None:
    with pytest.raises(CvaInputError, match="value must be numeric"):
        _optional_float_value(value)


def test_payload_optional_float_rejects_infinite_values() -> None:
    with pytest.raises(CvaInputError, match="value must be finite"):
        _optional_float_value(math.inf)


def test_batch_lineage_payload_preserves_omitted_lineage_sentinel() -> None:
    batch = SimpleNamespace(
        lineage_source_systems=[""],
        lineage_source_files=[""],
        lineage_source_row_ids=["row-1"],
        source_column_maps=[()],
    )

    assert batch_lineage_payload(batch, 0) is None
