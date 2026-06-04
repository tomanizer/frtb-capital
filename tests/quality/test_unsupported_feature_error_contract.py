from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import CvaMethod, CvaRegulatoryProfile, ensure_cva_profile_method_supported
from frtb_ima.regimes import RegulatoryRegime, get_policy


def test_ima_unsupported_feature_uses_shared_base() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="type_a_type_b"):
        policy.require_supported("type_a_type_b_nmrf_taxonomy")


def test_cva_unsupported_profile_uses_shared_base() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="US_NPR20_VB"):
        ensure_cva_profile_method_supported(
            CvaRegulatoryProfile.US_NPR20_VB,
            CvaMethod.BA_CVA_REDUCED,
        )
