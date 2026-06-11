"""Tests for shared SBM fixture helper validation."""

from __future__ import annotations

import pytest

from tests.sbm_fixture_helpers import load_sbm_fixture_context


def test_load_sbm_fixture_context_rejects_missing_context() -> None:
    with pytest.raises(ValueError, match="Missing 'context' key"):
        load_sbm_fixture_context({})


def test_load_sbm_fixture_context_rejects_missing_context_field() -> None:
    with pytest.raises(ValueError, match="Missing 'run_id' key"):
        load_sbm_fixture_context({"context": {}})
