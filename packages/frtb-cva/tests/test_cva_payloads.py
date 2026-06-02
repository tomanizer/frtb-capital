from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest
from frtb_cva._payloads import _optional_float_value, batch_lineage_payload
from frtb_cva.validation import CvaInputError


def test_payload_optional_float_preserves_numeric_null_semantics() -> None:
    assert _optional_float_value(np.nan) is None
    assert _optional_float_value("1.25") == pytest.approx(1.25)


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
