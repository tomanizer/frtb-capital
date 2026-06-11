# CLAUDE.md — frtb-cva

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-cva` as the owner of CVA capital only.

## Delivered slice

- Reduced and full BA-CVA stand-alone and portfolio capital
  (`ba_cva.py`, `capital.py`) per MAR50.14-MAR50.26.
- SA-CVA across all six delta risk classes and five vega risk-class paths per
  MAR50.42-MAR50.77 when `sa_cva_approved=True`; CCS vega is explicitly
  rejected because MAR50.45 and MAR50.63 do not define a CCS vega capital path.
- Mixed SA-CVA with BA-CVA netting-set carve-outs (`MIXED_CARVE_OUT`) per
  MAR50.8; SA-CVA sensitivities must carry context-level evidence for the
  non-carved slice.
- Qualified-index routing for CCS bucket 8, RCS buckets 16/17, and equity
  buckets 12/13 where MAR50.50 metadata is supplied.
- Optional CRIF adapter, Arrow/batch handoff, attribution, impact, deterministic
  input hashing, audit serialization, and reconciliation.

## Reject

- Silent zero-capital placeholders for unsupported methods.
- Sibling capital-package imports.
- Exposure-at-default or sensitivity shortcuts without cited calculation contracts.
- SA-CVA calls that accept BA-CVA counterparty/netting-set inputs without error.
- Documentation that presents outputs as final regulatory capital.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. Review CVA refactors toward this layout:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Adapters own row, batch, Arrow, and CRIF ingress into package-owned CVA batches;
validation modules own BA-CVA, SA-CVA, and mixed-method input rules and public
errors; kernels own cited capital math and must not import Arrow or dataframes;
assembly owns result records, hashes, citations, and audit payloads; and
`registry.py` owns method, entity, and risk-class dispatch.

Reject empty stage packages that shadow existing modules. Use
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) as
the import-shadowing guardrail before adding `adapters/`, `validation/`,
`kernel/`, or `assembly/`.

## Unsupported (fail closed)

- MAR50.9 materiality-threshold alternative.
- U.S., EU, and UK simplified CCR-substitution / alternative-approach
  elections that are outside the package-owned CVA capital kernel.

See [`docs/REGULATORY_TRACEABILITY.md`](docs/REGULATORY_TRACEABILITY.md).
