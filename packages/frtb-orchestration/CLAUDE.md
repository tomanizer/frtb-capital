# CLAUDE.md — frtb-orchestration

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-orchestration` as the suite aggregation boundary.

This is the only package allowed to depend on multiple capital components.
`calculate_suite_capital` and `compose_standardised_approach_capital` are
implemented; reject documentation or code that describes them as scaffold-only
unless an ADR explicitly defers scope.

Reject silent zero-capital placeholders and any calculation logic that belongs
inside a component package.

Current runtime source should consume `frtb_common.ComponentCapitalSummary` for
SA components and structural IMA/CVA summary contracts only. It must not import
sibling capital packages or private batch modules in production code; tests may
use concrete component fixtures to verify adapter compatibility.

Review suite changes against ADR 0039, ADR 0032, ADR 0022, and ADR 0029.