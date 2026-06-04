from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import CvaRegulatoryProfile
from frtb_cva.reference_data import profile_citation_id
from frtb_ima.regimes import RegulatoryRegime, get_policy


def test_ima_unsupported_feature_uses_shared_base() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="type_a_type_b"):
        policy.require_supported("type_a_type_b_nmrf_taxonomy")


def test_cva_unmapped_profile_citation_uses_shared_base() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="US_NPR20_VB"):
        profile_citation_id("basel_mar50_999", CvaRegulatoryProfile.US_NPR20_VB)
