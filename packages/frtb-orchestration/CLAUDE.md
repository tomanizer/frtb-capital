# CLAUDE.md — frtb-orchestration

Review `frtb-orchestration` as the suite aggregation boundary.

This is the only package allowed to depend on multiple capital components. Until
implementation starts, accepted behavior is explicit
`NotImplementedCapitalComponentError`. Reject silent zero-capital placeholders
and any calculation logic that belongs inside a component package.

Current runtime source should consume `frtb_common.ComponentCapitalSummary` for
SA components and structural CVA/IMA summary contracts only. It must not import
sibling capital packages or private batch modules in production code; tests may
use concrete component fixtures to verify adapter compatibility.
