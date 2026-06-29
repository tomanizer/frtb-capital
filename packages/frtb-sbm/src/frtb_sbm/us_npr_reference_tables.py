"""U.S. NPR 2.0 reference-table mirrors for the SBM comparison profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TypeVar

from frtb_sbm.reference_citation_routing import profile_citation_id
from frtb_sbm.reference_types import SbmFxBucketDefinition

ItemT = TypeVar("ItemT")


def remap_citation_id(items: tuple[ItemT, ...], citation_id: str) -> tuple[ItemT, ...]:
    """Return a tuple of dataclass rows with a uniform citation id."""

    return tuple(replace(item, citation_id=citation_id) for item in items)


def mirror_fx_buckets(
    basel_buckets: tuple[SbmFxBucketDefinition, ...],
    *,
    citation_id: str,
) -> tuple[SbmFxBucketDefinition, ...]:
    """Mirror FX bucket rows with NPR-labelled citation ids."""

    return tuple(
        SbmFxBucketDefinition(bucket.bucket_id, bucket.currency, citation_id)
        for bucket in basel_buckets
    )


def mirror_with_profile_citation(
    profile: str,
    basel_items: tuple[ItemT, ...],
    basel_citation_id: str,
) -> tuple[ItemT, ...]:
    """Mirror a Basel table using profile-owned citation routing."""

    return remap_citation_id(
        basel_items,
        profile_citation_id(profile, basel_citation_id),
    )


def mirror_bucket_like(
    basel_items: tuple[ItemT, ...],
    *,
    citation_mapper: Callable[[ItemT, str], ItemT],
    citation_id: str,
) -> tuple[ItemT, ...]:
    """Mirror rows when citation_id is not a dataclass field name."""

    return tuple(citation_mapper(item, citation_id) for item in basel_items)


__all__ = [
    "mirror_bucket_like",
    "mirror_fx_buckets",
    "mirror_with_profile_citation",
    "remap_citation_id",
]