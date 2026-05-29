# Intended Use

## Model Purpose

`frtb-rrao` calculates the Standardised Approach residual risk add-on for
canonical residual-risk inputs. It applies cited classification, exclusion, and
gross effective notional rules for Basel MAR23, U.S. NPR 2.0 proposed section
`__.211`, and the EU CRR3 comparison profile covering Article 325u and
Delegated Regulation (EU) 2022/2328.

The package is an ex-post capital layer. It does not price trades, source
market data, determine trading-book eligibility, or submit regulatory returns.

## Intended Users

The intended users are quantitative developers, market-risk methodology teams,
model validators, and engineering reviewers evaluating deterministic residual
risk add-on mechanics and audit controls.

The package may be used to:

- calculate supported canonical RRAO line add-ons and zero-capital exclusion
  records;
- validate source lineage, classification evidence, and exclusion evidence;
- produce deterministic audit payloads, input hashes, profile hashes, and
  additive allocation reports;
- demonstrate how an upstream risk engine can hand residual-risk inputs to a
  transparent capital layer.

The package must not be used to:

- produce final regulatory capital;
- replace independent model validation or legal interpretation;
- infer residual-risk classification from free-form product descriptions;
- perform SBM, DRC, CVA, IMA, SA total, or firm-level aggregation.

## Regulatory Anchors

- Basel MAR23.2-MAR23.8 define residual-risk scope, exclusions, and add-on
  percentages.
- U.S. NPR 2.0 section V.A.7.b and proposed section `__.211` define proposed
  U.S. residual-risk inclusion, exclusion, and gross effective notional
  treatment.
- Regulation (EU) No 575/2013 Article 325u and Delegated Regulation (EU)
  2022/2328 Articles 1-3 and Annex define the EU comparison profile.

For code-to-source mapping, use
[`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-rrao/docs/REGULATORY_TRACEABILITY.md).
