# frtb-capital

Use this skill when working in the `frtb-capital` repository with Grok or
Grok Build.

## Required Reading

Before changing code, read:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/AGENT_WORKTREE_POLICY.md`
- The relevant package-level `AGENTS.md` and `CLAUDE.md`

Grok Build also reads the `AGENTS.md` and `CLAUDE.md` instruction families
directly; this skill is a short repo-specific reminder and entrypoint.

## Working Rules

- Before editing, run `make agent-ensure AGENT=grok TASK=<task-slug>` from any
  checkout (including protected `main`). If not already in a compliant worktree,
  the command creates or reuses `frtb-capital-worktrees/grok/<task-slug>` and
  prints `next: cd ...` — **run that `cd` before changing files**. Pick
  `<task-slug>` from the user request (kebab-case, e.g. `drc-package-journey`).
- Respect package boundaries. Capital packages must not import sibling capital
  packages; shared types belong in `frtb-common`.
- Keep suite aggregation in `frtb-orchestration`.
- SA is composed from `frtb-sbm`, `frtb-drc`, and `frtb-rrao`; it is not a
  standalone package.
- Use Python 3.11+, dataclasses, enums, and pure functions.
- `numpy` is the default runtime numerical dependency for calculation kernels.
  Adding another runtime dependency requires an ADR.
- Use synthetic data only.
- Add deterministic tests for calculation changes.
- Cite specific regulatory paragraphs for regulatory behavior.
- Do not present prototype outputs as final regulatory capital.

For IMA work, read `packages/frtb-ima/AGENTS.md` and
`packages/frtb-ima/CLAUDE.md` before editing IMA code.

For PR babysitting, use `/frtb-ci-babysit` or
`.grok/skills/frtb-ci-babysit/SKILL.md`.

For documentation audits across all packages, use `/frtb-doc-audit` or
`.grok/skills/frtb-doc-audit/SKILL.md`.

For simplification / maintainability audits, use `/frtb-simplify-audit` or
`.grok/skills/frtb-simplify-audit/SKILL.md`.
