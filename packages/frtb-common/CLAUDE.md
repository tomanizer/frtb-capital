# CLAUDE.md — frtb-common

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-common` as the suite foundation package.

Reject changes that create dependency cycles, pull model-specific behavior into
shared code prematurely, or add runtime dependencies without an ADR. Shared
types should be small, stable, and neutral across IMA, SBM, DRC, RRAO, CVA, and
orchestration.

Current shared scope includes status metadata, explicit unsupported-feature
errors, Arrow tabular handoff primitives, CRIF-to-Arrow normalization,
standardised-component orchestration handoffs, JSON serialization helpers, and
regulatory citation test helpers. Review changes against ADR 0011, ADR 0023,
and ADR 0029 before accepting new shared API.
