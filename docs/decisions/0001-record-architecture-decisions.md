# 1. Record architecture decisions

Date: 2026-05-28

## Status

Accepted

## Context

This suite implements regulatory bank capital models. Under SR 11-7 and PRA SS 1/23, model design decisions must be documented, traceable, and reviewable. The codebase itself must carry an auditable record of why each modelling choice was made — not just what it does today.

Architectural Decision Records (ADRs) are a lightweight format for this purpose. They sit alongside the code and stay in version control with it.

## Decision

Every architectural or material modelling decision will be recorded as an ADR in `docs/decisions/`. ADRs follow the standard format:

1. **Title and number** (e.g. `0042-interpolated-expected-shortfall.md`).
2. **Date.**
3. **Status** — `Proposed`, `Accepted`, `Deprecated`, or `Superseded by 00xx`.
4. **Context** — what is the question, why does it matter.
5. **Decision** — what we are doing.
6. **Consequences** — what follows from this decision, both positive and negative.
7. **References** — links to PRs, discussions, regulatory citations.

ADRs are numbered sequentially in their filename. Numbers are not reused.

Material changes (see
[`0005-material-change-policy.md`](0005-material-change-policy.md)) require an
ADR. Non-material changes do not.

## Consequences

- The full history of design decisions is searchable in the repo, not buried in PR comments.
- ADRs become part of the SR 11-7 model documentation pack as decision evidence.
- ADR review becomes part of PR review for material changes.
- Some friction added to material changes; this is intentional.

## References

- Michael Nygard, "Documenting Architecture Decisions": https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- SR 11-7: Guidance on Model Risk Management.
