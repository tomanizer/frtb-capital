# DRC Mutation Survivor Notes

This file records surviving mutants reviewed for the 2026-07-02 baseline.

The baseline has **no allowlisted survivors**. All 388 surviving mutants are
counted in the denominator for the `83.24%` killed-only score documented in
`mutation_baseline.md`.

## Current Survivor Categories

The remaining survivors are retained as future hardening targets.

- CTP validation, context-input hashing, and branch diagnostic mutations where
  current tests assert accepted/rejected capital paths but do not pin every
  audit metadata field independently.
- CTP and securitisation netting mutations where aggregate net JTD and capital
  assertions catch most wrong totals but equivalent-looking ordering, grouping,
  and rejected-offset diagnostics remain alive.
- Non-securitisation DRC mutations around selected hedge-benefit and weighted
  short/long edge cases where fixture checks cover capital totals but do not
  exhaust all intermediate branch values.
- Securitisation non-CTP category and bucket mutations where tests cover
  delivered fixture branches and high-level category totals but leave some
  per-branch metadata and zero/one constant substitutions alive.
- Gross JTD fair-value-cap result mutations where current tests assert binding
  and non-binding behavior but do not independently pin every dataclass field
  emitted for the audit record.

## Allowlisting Rule

Do not remove a survivor from the mutation denominator without adding a specific
entry below with the mutant id, module, rationale, reviewer, and date.

No survivor entries are currently allowlisted.
