# CLAUDE.md — frtb-orchestration

Review `frtb-orchestration` as the suite aggregation boundary.

This is the only package allowed to depend on multiple capital components. Until
implementation starts, accepted behavior is explicit
`NotImplementedCapitalComponentError`. Reject silent zero-capital placeholders
and any calculation logic that belongs inside a component package.
