# SBM regulatory assumptions and implementation boundaries

This document records source-cited implementation decisions for `frtb-sbm`.
For a bidirectional code/regulation map, see
[`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md). For link-only source
metadata, see [`regulatory_sources.yml`](regulatory_sources.yml).

`frtb-sbm` delivers a partial runtime slice for GIRR delta/vega and FX delta
capital under cited Basel MAR21 mechanics. Phase 1 targets a cited GIRR delta
vertical slice only. No document or test in this package should describe outputs
as final regulatory capital.

## Phase-1 basis

The first capital-producing slice targets canonical inputs for:

1. Basel MAR21 GIRR delta mechanics, including bucket assignment, risk weights,
   intra-bucket aggregation, inter-bucket aggregation, and correlation scenarios.
2. U.S. NPR 2.0 proposed standardized non-default capital requirement, section
   V.A.7.a, as a comparison profile where explicitly supported.
3. Explicit fail-closed behavior for vega, curvature, and all non-GIRR risk
   classes until their own cited issues land.

The package treats the U.S. NPR 2.0 profile as proposed-rule material. Any
future final-rule change must update citations, profiles, fixtures, and expected
results in the same PR that changes behavior.

## Risk-factor assignment boundary

Risk-factor and bucket assignment is an upstream responsibility. The package
accepts caller-supplied canonical `SbmSensitivity` records with explicit bucket
and qualifier fields. Adapter modules may translate source-system fields into
canonical enums, but they must record source column lineage and mapping
warnings.

This boundary comes from the need to apply Basel MAR21.8 and section V.A.7.a
steps one and two deterministically. Unsupported or ambiguous mapping evidence
must fail before capital is calculated.

## Profile-driven parameters

Risk weights, bucket definitions, tenor sets, liquidity horizons, intra-bucket
correlations, inter-bucket correlations, scenario labels, and support flags
belong in versioned rule profiles and reference-data helpers (SBM-DEC-003).
Calculation kernels receive typed values and must not branch on hard-coded
regulator names.

Every rule-driven quantity must carry a citation id linked to a paragraph,
article, section, or table in the active profile.

## Aggregation boundary

Intra-bucket and inter-bucket aggregation are shared primitives reused across
risk classes (SBM-DEC-004). GIRR delta phase 1 exercises:

- weighted sensitivity calculation with cited risk weights;
- intra-bucket `Kb` calculation with pairwise correlation evidence;
- low, medium, and high correlation scenario totals;
- profile-prescribed scenario selection for the final risk-class capital.

Vega liquidity-horizon scaling and curvature up/down branch logic remain
unsupported until their canonical contracts and fixtures are implemented.

## Fail-closed unsupported scope

Any requested path without cited rule mapping and deterministic test evidence
must raise an explicit unsupported-feature or input error. The package must not
emit zero, empty, or placeholder capital for unsupported risk classes, risk
measures, buckets, or profile features (SBM-BOUNDARY-003).

## Audit and orchestration boundary

The first successful `SbmCapitalResult` must already include stable ids, profile
and input hashes, scenario metadata, and reconciliation records before
orchestration consumes it (SBM-DEC-007). SA composition (SBM + DRC + RRAO)
belongs in `frtb-orchestration`, not in this package.

## Synthetic fixtures only

Phase-1 tests and examples use synthetic canonical fixtures only. No proprietary
market data or adapter-specific conventions are used in the core runtime path.
