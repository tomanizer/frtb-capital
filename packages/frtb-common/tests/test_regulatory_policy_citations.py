"""Tests for the regulatory citation enforcement helper in frtb-common."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import frtb_common
import pytest
from frtb_common import assert_policy_has_regulatory_citations
from frtb_common.regulatory.policy_citations import MissingRegulatoryCitationsError


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
    cited_by: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({"another_value": "MAR50.3"})
    )


@dataclass(frozen=True)
class MappedPolicy:
    children: Mapping[str, SimplePolicy]
    cited_by: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NumericModellingChoicePolicy:
    modelling_choice: float = 0.5
    cited_by: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParentWithChoice:
    child: NumericModellingChoicePolicy
    cited_by: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValueObject:
    amount: float = 1.0
    weight: float = 2.0
    label: str = "not-a-policy"


@dataclass(frozen=True)
class PolicyWithValueObject:
    value: ValueObject
    risk_weight: float = 0.06
    cited_by: dict[str, str] = field(default_factory=lambda: {"risk_weight": "MAR22.15"})


def test_simple_policy_passes_when_fully_cited() -> None:
    policy = SimplePolicy()
    assert_policy_has_regulatory_citations(policy, allowed_without_citation=["modelling_choice"])


def test_raises_clear_error_on_missing_citation() -> None:
    policy = SimplePolicy(cited_by={"risk_weight": "Basel MAR22.15"})
    with pytest.raises(MissingRegulatoryCitationsError) as exc:
        assert_policy_has_regulatory_citations(
            policy, allowed_without_citation=["modelling_choice"]
        )
    assert "confidence_level" in str(exc.value)


@pytest.mark.parametrize("citation_value", ["", "   ", None])
def test_raises_on_blank_or_missing_citation_values(citation_value: object) -> None:
    policy = SimplePolicy(
        cited_by={
            "risk_weight": "Basel MAR22.15",
            "confidence_level": citation_value,
        }
    )

    with pytest.raises(MissingRegulatoryCitationsError) as exc:
        assert_policy_has_regulatory_citations(
            policy, allowed_without_citation=["modelling_choice"]
        )

    assert "confidence_level" in str(exc.value)


def test_recurses_into_nested_policies() -> None:
    inner = SimplePolicy()
    nested = NestedPolicy(simple=inner)
    assert_policy_has_regulatory_citations(nested, allowed_without_citation=["modelling_choice"])


def test_recurses_into_mapping_held_nested_policies() -> None:
    mapped = MappedPolicy(
        children={
            "uncited": SimplePolicy(cited_by={"risk_weight": "Basel MAR22.15"}),
        }
    )

    with pytest.raises(MissingRegulatoryCitationsError) as exc:
        assert_policy_has_regulatory_citations(
            mapped, allowed_without_citation=["modelling_choice"]
        )

    message = str(exc.value)
    assert "MappedPolicy.children['uncited']" in message
    assert "confidence_level" in message


def test_bare_allowlist_only_applies_to_root_policy() -> None:
    policy = ParentWithChoice(child=NumericModellingChoicePolicy())

    with pytest.raises(MissingRegulatoryCitationsError) as exc:
        assert_policy_has_regulatory_citations(
            policy, allowed_without_citation=["modelling_choice"]
        )

    assert "ParentWithChoice.child" in str(exc.value)


def test_path_allowlist_can_exempt_nested_policy_field() -> None:
    policy = ParentWithChoice(child=NumericModellingChoicePolicy())

    assert_policy_has_regulatory_citations(
        policy,
        allowed_without_citation=["ParentWithChoice.child.modelling_choice"],
    )


def test_recursion_ignores_unmarked_value_objects() -> None:
    policy = PolicyWithValueObject(value=ValueObject())

    assert_policy_has_regulatory_citations(policy)


def test_supports_custom_citation_attribute_name() -> None:
    @dataclass(frozen=True)
    class CustomPolicy:
        foo: float = 0.5
        regulatory_citations: dict[str, str] = field(
            default_factory=lambda: {"foo": "NPR 2.0 §__.220"}
        )

    policy = CustomPolicy()
    assert_policy_has_regulatory_citations(policy, citation_attr="regulatory_citations")


def test_top_level_exports_match_regulatory_module() -> None:
    assert (
        frtb_common.assert_policy_has_regulatory_citations is assert_policy_has_regulatory_citations
    )
    assert frtb_common.MissingRegulatoryCitationsError is MissingRegulatoryCitationsError
