# Agent prompt for a simplification audit

Use this prompt to ask an agent for a repeatable audit-only simplification run.

```text
Run a Simplification Audit across frtb-ima, frtb-sbm, frtb-drc, frtb-rrao,
frtb-cva, frtb-orchestration, and frtb-common.

Do not edit runtime code. Produce markdown audit reports under
docs/quality/simplification/<date>/.

First run:
- python3 scripts/agent_worktree.py guard
- the required checks from docs/quality/simplification/rubric.md
- an AST-based duplicate private function scan if practical

For each component, apply this rubric:
- duplicated code inside the package
- duplicated package-neutral code across components
- dead, unused, placeholder, or storage-only code
- code that should move to frtb-common
- code that should move to an internal component module
- code that is too complex and can be simplified
- code that must not move because it carries regulatory semantics
- tests required before any refactor

Respect AGENTS.md and package boundaries. Do not recommend moving regulatory
semantics into frtb-common. Separate findings into P0/P1/P2/P3 priorities and
identify whether each finding is audit-only, package-local, frtb-common, or
ADR-required.

End with a suite summary that groups common cross-package opportunities and
proposes an implementation order. Keep implementation recommendations separate
from findings so follow-up PRs can remain package-scoped.
```

