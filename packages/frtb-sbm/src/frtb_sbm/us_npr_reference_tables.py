"""U.S. NPR 2.0 reference-table mirrors for the SBM comparison profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, TypeVar, cast

from frtb_sbm.reference_citation_routing import profile_citation_id
from frtb_sbm.reference_types import SbmFxBucketDefinition

ItemT = TypeVar("ItemT")


def remap_citation_id(items: tuple[ItemT, ...], citation_id: str) -> tuple[ItemT, ...]:
    """Return a tuple of dataclass rows with a uniform citation id.

    Parameters
    ----------
    items : tuple[ItemT, ...]
        Frozen reference-data rows with a ``citation_id`` field.
    citation_id : str
        Citation id to assign to every mirrored row.

    Returns
    -------
    tuple[ItemT, ...]
        Mirrored rows with the supplied citation id.
    """

    return tuple(cast(ItemT, replace(cast(Any, item), citation_id=citation_id)) for item in items)


def mirror_fx_buckets(
    basel_buckets: tuple[SbmFxBucketDefinition, ...],
    *,
    citation_id: str,
) -> tuple[SbmFxBucketDefinition, ...]:
    """Mirror FX bucket rows with NPR-labelled citation ids.

    Parameters
    ----------
    basel_buckets : tuple[SbmFxBucketDefinition, ...]
        Basel FX bucket rows.
    citation_id : str
        Citation id to assign to each mirrored bucket.

    Returns
    -------
    tuple[SbmFxBucketDefinition, ...]
        Mirrored FX buckets.
    """

    return tuple(
        SbmFxBucketDefinition(bucket.bucket_id, bucket.currency, citation_id)
        for bucket in basel_buckets
    )


def mirror_with_profile_citation(
    profile: str,
    basel_items: tuple[ItemT, ...],
    basel_citation_id: str,
) -> tuple[ItemT, ...]:
    """Mirror a Basel table using profile-owned citation routing.

    Parameters
    ----------
    profile : str
        Comparison-profile identifier.
    basel_items : tuple[ItemT, ...]
        Basel reference-data rows with a ``citation_id`` field.
    basel_citation_id : str
        Basel citation id to route through the profile citation map.

    Returns
    -------
    tuple[ItemT, ...]
        Mirrored rows with profile-owned citation ids.
    """

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
    """Mirror rows when citation_id is not a dataclass field name.

    Parameters
    ----------
    basel_items : tuple[ItemT, ...]
        Basel reference-data rows.
    citation_mapper : Callable[[ItemT, str], ItemT]
        Row-specific copier that applies the supplied citation id.
    citation_id : str
        Citation id to assign to every mirrored row.

    Returns
    -------
    tuple[ItemT, ...]
        Mirrored rows with profile-owned citation ids.
    """

    return tuple(citation_mapper(item, citation_id) for item in basel_items)


__all__ = [
    "mirror_bucket_like",
    "mirror_fx_buckets",
    "mirror_with_profile_citation",
    "remap_citation_id",
]
