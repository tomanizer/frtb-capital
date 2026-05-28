"""Tests for package-level public API consistency."""

import frtb_ima


def test_all_exports_resolve_to_package_attributes() -> None:
    exported_names = frtb_ima.__all__

    assert len(exported_names) == len(set(exported_names))
    for name in exported_names:
        assert hasattr(frtb_ima, name), name
