from __future__ import annotations

import numpy as np
import pytest
from frtb_drc import DrcInputError, DrcRiskClass
from frtb_drc import _batch_columns as columns


def test_drc_batch_column_wrappers_preserve_coercion_semantics() -> None:
    optional_text = columns._optional_text_array([None, " issuer ", ""], 3, copy=True)
    optional_float = columns._optional_float_array([None, "", np.nan, "12.5"], 4, copy=True)
    risk_classes = columns._enum_array(
        ["NON_SECURITISATION"],
        DrcRiskClass,
        "risk_class",
        copy=True,
    )
    nullable_risk_classes = columns._nullable_enum_array(
        [None, "", "CORRELATION_TRADING_PORTFOLIO"],
        DrcRiskClass,
        "risk_class",
        3,
        copy=True,
    )

    assert optional_text.tolist() == [None, "issuer", None]
    assert np.isnan(optional_float[:3]).all()
    assert optional_float[3] == 12.5
    assert risk_classes.tolist() == ["NON_SECURITISATION"]
    assert nullable_risk_classes.tolist() == [None, None, "CORRELATION_TRADING_PORTFOLIO"]


def test_drc_batch_column_wrappers_preserve_errors_and_source_map_sorting() -> None:
    with pytest.raises(DrcInputError, match="risk_class contains unsupported value: BAD"):
        columns._enum_array(["BAD"], DrcRiskClass, "risk_class", copy=True)
    with pytest.raises(DrcInputError, match="optional numeric field must be numeric"):
        columns._optional_float("bad")

    source_maps = columns._freeze_source_column_maps(
        [[("target_b", "canonical_b"), ("target_a", "canonical_a")]],
        1,
    )

    assert source_maps == ((("target_a", "canonical_a"), ("target_b", "canonical_b")),)
