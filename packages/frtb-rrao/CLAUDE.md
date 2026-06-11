# CLAUDE.md — frtb-rrao

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-rrao` as the owner of residual risk add-on capital only.

The package has an implemented v1 canonical-input calculation path for Basel
MAR23, U.S. NPR 2.0 proposed section `__.211`, and the EU CRR3 Article 325u
comparison profile. Reviewers should verify that supported inputs produce cited
line add-ons and zero-capital exclusion records, while PRA UK CRR, unmapped
profile features, ambiguous evidence, and unsupported adapter paths fail
explicitly before a capital result is emitted.

Reject silent zero-capital placeholders, sibling capital-package imports,
free-form residual-risk classification shortcuts, and any documentation claim
that treats U.S. NPR 2.0 output as final regulatory capital.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. Review RRAO refactors toward this
layout:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Adapters own row, batch, Arrow, and CRIF-like ingress into the package-owned
RRAO batch; validation modules own classification/evidence rules and public
errors; kernels own cited residual-risk add-on math and must not import Arrow or
dataframes; assembly owns result records, hashes, citations, and audit payloads;
and `registry.py` owns profile and factor-type dispatch.

Reject empty stage packages that shadow existing modules. Use
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) as
the import-shadowing guardrail before adding `adapters/`, `validation/`,
`kernel/`, or `assembly/`.
