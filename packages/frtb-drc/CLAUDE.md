# CLAUDE.md — frtb-drc

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-drc` as the owner of default risk charge capital only.

The package has a capital-producing partial implementation for U.S. NPR 2.0
non-securitisation, securitisation non-CTP, and correlation trading portfolio
(CTP) DRC row and batch paths, plus Basel MAR22 non-securitisation row and
batch paths, Basel MAR22 securitisation non-CTP and CTP row and batch paths,
and EU CRR3 non-securitisation and securitisation non-CTP row and batch paths.
EU CRR3 CTP and all PRA UK CRR paths must fail explicitly until cited profile
mappings and deterministic tests exist.

Reject silent zero-capital placeholders, sibling capital-package imports,
uncited capital-producing inputs, scoped runs that mix desks or legal entities,
and issuer aggregation shortcuts that would hide missing DRC mechanics.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. Review DRC refactors toward this layout:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Adapters own row, batch, Arrow, and future CRIF-like ingress into the
package-owned DRC batch; validation modules own profile/path input rules and
public errors; kernels own cited default-risk math and must not import Arrow or
dataframes; assembly owns result records, hashes, citations, and audit payloads;
and `registry.py` owns non-securitisation, securitisation, and CTP dispatch.

Reject empty stage packages that shadow existing modules. Use
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) as
the import-shadowing guardrail before adding `adapters/`, `validation/`,
`kernel/`, or `assembly/`.
