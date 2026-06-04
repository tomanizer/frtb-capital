# CLAUDE.md — frtb-drc

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-drc` as the owner of default risk charge capital only.

The package has a capital-producing partial implementation for U.S. NPR 2.0
non-securitisation, securitisation non-CTP, and correlation trading portfolio
(CTP) DRC row and batch paths, plus Basel MAR22 non-securitisation row and
batch paths and Basel MAR22 securitisation non-CTP and CTP row and batch
paths. All EU CRR3 and PRA UK CRR paths must fail explicitly until cited
profile mappings and deterministic tests exist.

Reject silent zero-capital placeholders, sibling capital-package imports,
uncited capital-producing inputs, scoped runs that mix desks or legal entities,
and issuer aggregation shortcuts that would hide missing DRC mechanics.
