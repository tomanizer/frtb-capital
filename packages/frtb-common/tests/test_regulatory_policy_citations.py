"""Tests for the regulatory citation enforcement helper in frtb-common."""

from dataclasses import dataclass, field
from types import MappingProxyType

import pytest

from frtb_common import assert_policy_has_regulatory_citations
from frtb_common.regulatory.policy_citations import MissingRegulatoryCitationsError
from frtb_common.status import UnsupportedRegulatoryFeatureError


@dataclass(frozen=True)
class SimplePolicy:
    risk_weight: float = 0.06
    confidence_level: float = 0.975
    modelling_choice: str = "foo"
    cited_by: dict[str, str] = field(
        default_factory=lambda: {
            "risk_weight": "Basel MAR22.15",
            "confidence_level": "Basel MAR33.4",
        }
    )


@dataclass(frozen=True)
class NestedPolicy:
    simple: SimplePolicy
    another_value: float = 0.12
    cited_by: MappingProxyType = field(
        default_factory=lambda: MappingProxyType({"another_value": "MAR50.3"})
    )


def test_simple_policy_passes_when_fully_cited():
    policy = SimplePolicy()
    assert_policy_has_regulatory_citations(
        policy, allowed_without_citation=["modelling_choice"]
    )


def test_raises_clear_error_on_missing_citation():
    policy = SimplePolicy(cited_by={"risk_weight": "Basel MAR22.15"})
    with pytest.raises(MissingRegulatoryCitationsError) as exc:
        assert_policy_has_regulatory_citations(
            policy, allowed_without_citation=["modelling_choice"]
        )
    assert "confidence_level" in str(exc.value)


def test_recurses_into_nested_policies():
    inner = SimplePolicy()
    nested = NestedPolicy(simple=inner)
    assert_policy_has_regulatory_citations(
        nested, allowed_without_citation=["modelling_choice"]
    )


def test_supports_custom_citation_attribute_name():
    @dataclass(frozen=True)
    class CustomPolicy:
        foo: float = 0.5
        regulatory_citations: dict = field(
            default_factory=lambda: {"foo": "NPR 2.0 §__.220"}
        )

    policy = CustomPolicy()
    assert_policy_has_regulatory_citations(
        policy, citation_attr="regulatory_citations"
    )
