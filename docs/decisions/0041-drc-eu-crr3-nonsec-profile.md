# 41. DRC EU CRR3 non-securitisation profile slice

Date: 2026-06-04

## Status

Accepted

## Context

`frtb-drc` exposed `EU_CRR3` as a known rule-profile identity, but it failed
closed for every DRC risk class. Issue #583 adds the first EU CRR3 DRC
comparison slice: non-securitisation row and batch capital.

This is a material model change under ADR 0005 because it changes supported
regimes, requirement status, profile hashes, runtime routing, and committed
fixture outputs. It does not claim complete EU DRC support: securitisation
non-CTP and correlation trading portfolio DRC still need separate Article
325z-325ad mapping evidence.

## Decision

Support `EU_CRR3` / `NON_SECURITISATION` as a capital-producing DRC profile
cell with profile-owned Article 325w, Article 325x, and Article 325y evidence.

The supported cell must provide:

- Article 325w LGD reference data for non-securitisation instruments;
- Article 325x maturity scaling and same-obligor netting evidence;
- Article 325y bucket, hedge-benefit-ratio, category-capital, and credit-quality
  mapping citations;
- EU-specific profile hashes and support-matrix metadata;
- deterministic row and Arrow batch fixture coverage proving the successful
  runtime path;
- explicit fail-closed behavior for EU CRR3 securitisation non-CTP and CTP
  until Articles 325z-325ad are separately mapped and tested.

The implementation may reuse Basel-aligned letter-grade risk-weight values where
Article 325y and the package's CQS mapping evidence support the same comparison
calibration, but EU CRR3 results must not emit Basel citation ids or Basel
profile hashes.

## Consequences

- `frtb-drc` remains a partial-runtime package because EU CRR3 securitisation
  non-CTP, EU CRR3 CTP, and all PRA UK CRR DRC cells still fail closed.
- The package support matrix now reports only EU CRR3 non-securitisation as
  supported for the EU profile.
- The package changelog fragment records the material profile-support expansion;
  the package version bump is deferred to the release PR in accordance with ADR
  0015.
- Model documentation, requirement registry rows, and fixture documentation must
  distinguish this comparison slice from complete or final EU regulatory capital.

## References

- ADR 0005: material change policy and ADR-driven change control.
- ADR 0015: deferred versioning and changelog fragments.
- GitHub issue #583.
- Regulation (EU) 2024/1623 Article 325w.
- Regulation (EU) 2024/1623 Article 325x.
- Regulation (EU) 2024/1623 Article 325y.
- Regulation (EU) 2024/1623 Articles 325z-325ad.
