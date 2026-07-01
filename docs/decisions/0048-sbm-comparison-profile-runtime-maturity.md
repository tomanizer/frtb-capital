# 48. SBM comparison-profile runtime maturity

Date: 2026-07-01

## Status

Accepted

## Context

The SBM comparison-profile recovery in #1008 followed the review of PR #989.
That PR attempted to open all 21 U.S. NPR 2.0, EU CRR3, and PRA UK CRR
profile/risk-class/measure cells, but it did not align package metadata, the
maturity registry, model documentation, traceability, and fixture evidence. It
also collided with the existing ADR 0047 filename. PR #989 is therefore
non-authoritative evidence for this decision.

`frtb-sbm` currently has deterministic synthetic runtime evidence for:

- `BASEL_MAR21`: delta, vega, and curvature across all seven SBM risk classes
  under Basel MAR21.1-MAR21.101.
- `US_NPR_2_0`: GIRR delta only, as proposed-rule comparison material under
  Federal Register 91 FR 14952 section V.A.7.a.

`EU_CRR3` is source-mapped only at the article-family level for Regulation (EU)
2024/1623 Articles 325e-325az. `PRA_UK_CRR` is source-mapped for planning to
PRA PS1/26 Appendix 1 / PRA2026/1 Articles 325c-325ay, but no PRA SBM runtime
cell has exact-cell citations, profile-owned reference data, or fixture
evidence yet.

## Decision

Keep `frtb-sbm` package maturity at `partial_runtime`.

At package level:

- `partial_runtime` means at least one public runtime path calculates capital,
  but the package still has deliberately unsupported regulatory profile, method,
  or sub-feature paths that fail closed.
- `implemented under audit` is a cell-level traceability status. It means a
  supported profile/risk-class/measure path has cited rule data, public runtime
  entrypoints, deterministic synthetic fixture or approved shared-fixture
  evidence, and validation remains pending.
- `validation pending` means synthetic/internal evidence exists but independent
  model-validation evidence is not complete. Outputs must not be described as
  final regulatory capital.

At profile/risk-class/measure level:

- A runtime gate may open only when the exact cell has profile-owned citation
  metadata and deterministic evidence for successful capital output, or an ADR
  explicitly approves shared fixture evidence for that exact cell.
- Basel-mirrored numerics do not count as implementation evidence for U.S. NPR
  2.0, EU CRR3, or PRA UK CRR by themselves. A comparison-profile cell may
  produce the same number as Basel only when it carries the comparison profile
  id, profile-owned citation ids, profile hash, and fixture evidence.
- Unsupported cells must fail closed with `UnsupportedRegulatoryFeatureError`
  or the established package input error for malformed inputs. They must not
  emit zero or placeholder capital.

The current comparison-profile support matrix is:

| Profile | Delta | Vega | Curvature | Package action |
| --- | --- | --- | --- | --- |
| `US_NPR_2_0` GIRR | implemented under audit | unsupported fail-closed | unsupported fail-closed | Keep only GIRR delta capital-producing. |
| `US_NPR_2_0` non-GIRR classes | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | Add cells one at a time with profile-owned evidence. |
| `EU_CRR3` all classes | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | Add cells only after article-level mapping and fixtures. |
| `PRA_UK_CRR` all classes | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | Source mapped to PS1/26 Appendix 1; add cells only with exact-cell citations, reference data, and fixtures. |

## Consequences

- `PACKAGE_METADATA.implementation_status` remains `PARTIAL`.
- `PACKAGE_METADATA.validation_status` remains `PENDING`.
- `docs/quality/package_maturity.toml` remains `partial_runtime` and must point
  to support-matrix and unsupported-runtime-path evidence.
- Documentation must distinguish package-level maturity from cell-level
  "implemented under audit" status.
- Public API and traceability docs must describe U.S. NPR 2.0 GIRR delta as
  proposed-rule comparison material only, not final regulatory capital.
- Future comparison-profile PRs must update the support matrix, fixture
  evidence, traceability, and package maturity surfaces together.

## References

- #1008: SBM comparison-profile runtime maturity recovery.
- #1009: support-matrix decision.
- #1010: maturity standard.
- #1011: rebuild implementation from fresh main.
- #1012: authoritative status surfaces.
- #1013: ADR governance repair.
- #1014: fixture-backed coverage standard.
- #1015: regulatory citation review.
- PR #989: non-authoritative attempted implementation.
- Federal Register 91 FR 14952 section V.A.7.a.
- Regulation (EU) 2024/1623 Articles 325e-325az.
- PRA PS1/26 Appendix 1 / PRA2026/1 Articles 325c-325ay.
- `docs/modules/frtb-sbm/NON_BASEL_PROFILE_REQUIREMENTS.md`, `SBM-NBP-020`.
