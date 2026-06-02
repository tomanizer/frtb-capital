# Simplification audit rubric

This rubric defines a repeatable audit for code simplification across the
`frtb-capital` suite. It is an audit process, not an instruction to refactor
immediately.

## Purpose

Use this audit to find:

- duplicated code inside one package;
- duplicated package-neutral code across packages;
- dead, placeholder, or storage-only code;
- code that belongs in `frtb-common`;
- code that belongs in a package-local internal helper module;
- modules or functions whose complexity makes future regulatory changes risky.

The audit must preserve package ownership. It must not recommend moving
component-specific regulatory semantics into `frtb-common`.

## Required checks

Run from a compliant agent worktree:

```bash
python3 scripts/agent_worktree.py guard
find packages/frtb-common packages/frtb-ima packages/frtb-sbm packages/frtb-drc packages/frtb-rrao packages/frtb-cva packages/frtb-orchestration -path '*/src/*' -name '*.py' -print | xargs wc -l | sort -nr
rg "def _hash_payload|def .*input_hash|def .*policy_hash|sha256|json\\.dumps|is_reconciled|def _object_array_from_arrow|def _object_array_from_column|def _required_text_array|def _readonly_array|def _required_text\\(" packages/*/src -n
rg "TODO|FIXME|placeholder|storage-only|unused|working assumption|NotImplemented|not implemented|accepted_row_dataclasses_materialized" packages/*/src packages/*/tests -n
rg "from frtb_(ima|sbm|drc|rrao|cva)|import frtb_(ima|sbm|drc|rrao|cva)" packages/*/src -n
```

Also run an AST-based duplicate-function scan when possible. Exact duplicate
private helpers are stronger evidence than similar names alone.

## Classification

Classify every finding by scope:

| Scope | Meaning | Normal follow-up |
| --- | --- | --- |
| `audit-only` | Observation or product decision; no code change yet | Track or decide explicitly |
| `package-local` | Can be fixed inside one package | One package PR |
| `frtb-common` | Package-neutral mechanics repeated across packages | Shared-library PR, then consumers |
| `ADR-required` | Changes public boundary, dependency policy, regulatory meaning, or material calculation flow | ADR before implementation |

Classify every finding by priority:

| Priority | Meaning |
| --- | --- |
| `P0` | Drift risk can change capital, audit hashes, unsupported-feature behavior, or package boundaries |
| `P1` | High maintenance cost or high probability of inconsistent future changes |
| `P2` | Readability and reviewability improvement with limited behavioral risk |
| `P3` | Cosmetic cleanup or deferred simplification |

## `frtb-common` decision rule

Move code to `frtb-common` only when all are true:

1. The code is package-neutral mechanics.
2. The code is repeated in at least two packages, preferably three.
3. The code does not encode regulatory classifications, risk weights,
   correlations, profile mappings, capital formulas, or component result
   semantics.
4. The shared behavior can be tested in `frtb-common` without importing capital
   component packages.

Good candidates include deterministic JSON hashing, SHA256 hex validation,
Arrow-to-NumPy primitive conversion, batch array coercion, source-file hashing,
and package-neutral CRIF normalization.

Do not move risk weights, citations, classification decisions, jurisdiction
profile support, aggregation formulas, line/subtotal result semantics, or
unsupported-feature decisions into `frtb-common`.

## Report template

Each component report should use this structure:

```text
# <package> simplification audit

## Scope
## Hotspot map
## Duplicated code
## Dead or storage-only code
## `frtb-common` candidates
## Package-local factoring candidates
## Over-complexity
## What must not move
## Recommended sequence
## Validation required
```

## Re-run cadence

Run a full suite audit after major component milestones, after broad ingestion
or handoff work, and before large model-documentation promotion runs. For normal
development, run a package-local audit before refactoring any module above 500
lines or any public calculation entrypoint.

