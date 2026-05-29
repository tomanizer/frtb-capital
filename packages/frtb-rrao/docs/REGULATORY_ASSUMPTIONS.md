# RRAO regulatory assumptions and implementation boundaries

This document records source-cited implementation decisions for `frtb-rrao`.
For a bidirectional code/regulation map, see
[`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md). For link-only source
metadata, see [`regulatory_sources.yml`](regulatory_sources.yml).

`frtb-rrao` is currently partial. The package calculates supported canonical
Basel MAR23 and U.S. NPR 2.0 residual-risk inputs, and no document or test in
this package should describe outputs as final regulatory capital.

## v1 basis

The first capital-producing slice targets canonical inputs for:

1. Basel MAR23 residual-risk add-on mechanics, including MAR23.2-MAR23.8.
2. U.S. NPR 2.0 proposed residual risk capital requirement, section V.A.7.b
   and proposed section `__.211`.
3. Explicit zero-capital lines only where Basel MAR23.4-MAR23.7 or proposed
   section `__.211(b)` support an exclusion.

The package treats the U.S. NPR 2.0 profile as proposed-rule material. Any
future final-rule change must update citations, profiles, fixtures, and
expected results in the same PR that changes behavior.

## Classification evidence boundary

Classification evidence is an input to the capital layer. The package must not
infer exotic exposure, other residual risk, or an exclusion from free-form trade
descriptions. Adapter modules may translate source-system fields into canonical
enums, but they must record source column lineage and mapping warnings.

This boundary comes from the need to apply Basel MAR23.2-MAR23.7 and proposed
section `__.211(a)`-`__.211(b)` deterministically. Unsupported or ambiguous
classification evidence must fail before capital is calculated.

## Gross effective notional boundary

RRAO capital is calculated on gross notional under Basel MAR23.8 and on gross
effective notional under proposed section `__.211(c)(2)`. The package therefore
expects non-negative finite notionals after adapter normalisation.

If a source system supplies signed notionals, the adapter may normalise to an
absolute gross effective notional only when it records the source convention in
lineage. The calculation kernel must reject negative or non-finite notionals.

## Additive capital boundary

For supported included positions, line capital is:

```text
gross_effective_notional * risk_weight
```

The v1 risk weights are 1.0% for exotic exposures and 0.1% for other residual
risks, anchored to Basel MAR23.8(2)(a)-MAR23.8(2)(b) and proposed section
`__.211(c)(1)(i)`-`__.211(c)(1)(ii)`.

No diversification, offsetting, hedge benefit, correlation aggregation,
maturity scaling, or scenario aggregation applies in v1 unless a future
regulatory profile cites and tests a different treatment.

## Investment fund inclusion boundary

For the U.S. NPR 2.0 profile, proposed section `__.211(a)(3)` is implemented
only through an explicit `RraoInvestmentFundDescriptor`. The descriptor must
show that the position uses the proposed section `__.205(e)(3)(iii)` backstop
fund method, that look-through is not available for the included portion, that
the fund mandate permits residual-risk exposure types, and that the reported
gross effective notional equals the cited included portion.

The package does not infer investment-fund treatment from fund name, strategy,
or free-form description. The descriptor must choose whether the included
portion maps to the exotic 1.0% treatment or the other-residual-risk 0.1%
treatment, and classification validates that choice against the selected U.S.
profile rule. Basel, EU, and PRA investment-fund capital paths remain
unsupported until they have separate cited mappings and fixtures.

## Exclusion boundary

Exclusions are successful zero-capital outcomes only when the selected profile
contains a cited exclusion rule and the input supplies the required evidence.

The planned U.S. profile covers proposed section `__.211(b)` exclusions,
including listed positions, CCP or QCCP clearable positions, non-path-dependent
options with two or fewer underlyings, exact third-party back-to-back
transactions, deliverable hedge pairs, U.S. government or GSE debt,
fallback-capital positions, qualifying internal desk transactions, and
agency-determined exclusions.

If exclusion evidence is missing, the position must remain subject to normal
classification or fail validation. The package must not silently convert missing
evidence into zero capital.

## Jurisdiction support

| Profile | Status | Boundary |
| --- | --- | --- |
| Basel MAR23 | Supported for v1 canonical-input mechanics. | Profile covers MAR23.2-MAR23.8 mechanics and exclusions. |
| U.S. NPR 2.0 | Supported for v1 canonical-input mechanics. | Proposed-rule material from section V.A.7.b and proposed section `__.211`; not final U.S. regulatory capital. |
| EU Article 325u / Delegated Regulation 2022/2328 | Unsupported for capital until issue #91. | The package can document Article 1 exotic underlyings, Article 2 Annex instruments, and Article 3 non-presumptive risks, but must fail closed until deterministic fixtures exist. |
| PRA UK CRR | Unsupported. | No package-local PRA RRAO source mapping exists yet. |

## Public implementation references

Public GitHub examples may inform adapter field names and explain-output shape,
but they are not regulatory sources. In particular, a two-bucket implementation
that maps source labels directly to `RRAO_1_PERCENT` or `RRAO_01_PERCENT` is not
enough for this package's capital kernel; canonical inputs must preserve
classification evidence, source lineage, and citation ids.

## Out of scope

`frtb-rrao` intentionally excludes:

- pricing or payoff modelling for exotic instruments;
- legal interpretation of trade contracts;
- market data sourcing;
- generation of sensitivities or default-risk inputs;
- SBM, DRC, CVA, IMA, and SA total composition;
- firm-level consolidation and regulatory submission packaging;
- final-rule change management outside cited profile updates.

Upstream systems own pricing, product classification evidence, reporting
notional extraction, and source-system lineage. `frtb-orchestration` owns SA
composition and suite aggregation.

## Maintenance rules

When a PR adds or changes a regulatory behavior:

1. Cite the specific paragraph, proposed section, article, or annex entry.
2. Update [`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md).
3. Update [`regulatory_sources.yml`](regulatory_sources.yml) when source
   families or implementation references change.
4. Add deterministic tests for every implemented calculation or exclusion path.
5. Keep unsupported jurisdiction/profile paths failing explicitly.
