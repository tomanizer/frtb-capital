from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from frtb_sbm.reference_citations_pra_uk_crr import (
    PRA_UK_CRR_CITATIONS,
    PRA_UK_CRR_LEGISLATION_CHAPTER_URL,
    PRA_UK_CRR_PS1_26_URL,
)
from frtb_sbm.reference_profiles import PRA_UK_CRR_URL

REGULATORY_SOURCES_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "regulatory_sources.yml"
)


def test_regulatory_sources_manifest_lists_comparison_profiles() -> None:
    manifest = yaml.safe_load(REGULATORY_SOURCES_PATH.read_text(encoding="utf-8"))
    source_ids = {entry["id"] for entry in manifest["sources"]}

    assert {
        "us_npr_2_0_91_fr_14952",
        "eu_crr3_2024_1623",
        "uk_crr_sbm_retained",
        "uk_pra_ps1_26_sbm",
    }.issubset(source_ids)


@pytest.mark.parametrize(
    "url",
    [
        PRA_UK_CRR_LEGISLATION_CHAPTER_URL,
        "https://www.legislation.gov.uk/eur/2013/575/article/325r",
        "https://www.legislation.gov.uk/eur/2013/575/article/325u",
    ],
)
def test_pra_uk_crr_legislation_urls_are_reachable(url: str) -> None:
    import urllib.request

    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=20) as response:
        assert response.status == 200


def test_pra_uk_crr_ps1_26_url_is_registered_in_manifest() -> None:
    manifest = yaml.safe_load(REGULATORY_SOURCES_PATH.read_text(encoding="utf-8"))
    ps1_entry = next(entry for entry in manifest["sources"] if entry["id"] == "uk_pra_ps1_26_sbm")

    assert ps1_entry["url"] == PRA_UK_CRR_PS1_26_URL


def test_reference_profiles_pra_url_matches_citation_module() -> None:
    assert PRA_UK_CRR_URL == PRA_UK_CRR_LEGISLATION_CHAPTER_URL


def test_pra_uk_crr_citations_use_article_level_legislation_urls() -> None:
    for citation_id, citation in PRA_UK_CRR_CITATIONS.items():
        if citation_id == "pra_uk_crr_art_325r_sbm_scope":
            assert citation.url == PRA_UK_CRR_PS1_26_URL
            continue
        assert citation.url.startswith("https://www.legislation.gov.uk/eur/2013/575/article/")
        assert "crossheading/sensitivities-based-method" not in citation.url