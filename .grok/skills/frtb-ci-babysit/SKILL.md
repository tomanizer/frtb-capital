---
name: frtb-ci-babysit
description: >-
  Babysit an frtb-capital PR from push to merge-ready: stabilise CI, incorporate
  Gemini and Copilot reviews, run a final quality subagent audit.
when-to-use: >-
  Use when asked to babysit, watch, or fix a frtb-capital PR, monitor CI until
  green, incorporate bot review feedback, or runs /frtb-ci-babysit.
argument-hint: "[<pr-number>] [--agent <name>]"
allowed-tools: Shell, Read, Grep, Glob, Write, StrReplace, Task
---

# FRTB CI babysit

Babysit an `frtb-capital` pull request from push through merge-readiness. Four
sequential phases; complete each before advancing.

Read `AGENTS.md`, `CLAUDE.md`, and `.grok/skills/frtb-capital/SKILL.md` before
editing code.

## Cross-agent entrypoints

| Agent | Entry |
| --- | --- |
| Grok | `/frtb-ci-babysit` (this skill) |
| Claude Code | `/frtb-ci-babysit` → `.claude/commands/frtb-ci-babysit.md` |
| Codex | `AGENTS.md` → CI babysit section |
| Cursor | `.cursor/rules/frtb-capital.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |

## Arguments

| Input | Meaning |
| --- | --- |
| `<pr-number>` | Optional. If omitted, use `gh pr view` on the current branch. |
| `--agent <name>` | Worktree agent id when creating a checkout: `grok`, `claude`, `codex`, `cursor`, or `copilot`. Default: infer from context or `grok`. |

Requires `gh` authenticated for the repository and a compliant agent worktree for
commits.

---

## Step 0 — Start state

**Success criteria:** `PR` exported; worktree guard passed; baseline recorded.

```bash
# Optional: gh pr checkout <N> first if user supplied a PR number
gh pr view ${PR:-} --json number,title,headRefName,baseRefName,isDraft,mergeable,state
export PR=$(gh pr view ${PR:-} --json number --jq .number)
```

If no PR exists for the current branch, stop and ask the user. Set `$PR` once;
do not re-derive it later.

Worktree compliance (required before any edit):

```bash
python3 scripts/agent_worktree.py guard
```

On failure:

```bash
make agent-new AGENT=<agent> TASK=ci-babysit
# cd to printed worktree; gh pr checkout $PR if needed
```

Record: PR number, head SHA, draft state, base branch, CI run count, unresolved
human review thread count.

---

## Phase 1 — CI stabilisation

**Success criteria:** All required checks for this PR are `success`; acceptable
checks are explicitly `skipped` per the table below.

### Monitor

```bash
gh pr checks $PR --watch
```

Prefer the aggregate `ci-required` check when present. On failure, inspect logs:

```bash
gh run view <run-id> --log-failed
```

### Required jobs (current `.github/workflows/ci.yml`)

| Job | When it must pass on PRs | Notes |
| --- | --- | --- |
| `quality-control` | Always | Never skipped; includes maturity and drift gates. |
| `version-bump-guard` | Always | Fails if non-`release/*` PR bumps versions. |
| `uv-lock-guard` | Always | Fails if `uv.lock` changes without dependency-spec changes. |
| `ci-required` | Always | Aggregates child job results. |
| `lint` | When `changes.code` | Includes `format-check` step inside lint. |
| `typecheck` | When `changes.code` | |
| `build` | When `changes.code` | |
| `test (3.11)` | When `changes.code` | Only PR Python test job. |
| `docs` | When `changes.docs` | Runs `make docs-check`. |
| `dependency-audit` | When `changes.dependency` | |
| `sbom` | When `changes.dependency` | |
| `examples` | When `changes.examples` | |
| `notebooks` | When `changes.notebooks` | |

**Skipped on pull requests (expected, not failures):**

| Job | Why |
| --- | --- |
| `test (3.12)`, `test (3.13)` | `test-compat` runs only on `schedule` and `workflow_dispatch`, not on PRs. |

Do not treat skipped `test-compat` matrix jobs on a PR as a defect.

### Failure handling

1. Read the failed job log in full.
2. Classify: **branch-related** (fix locally), **flaky/infra** (`gh run rerun <run-id> --failed`), or **ambiguous** (one diagnosis pass first).
3. Avoid pushing CI fixes on top of unaddressed review threads when the fix will
   invalidate bot reviews — order fixes deliberately.

### Local validation

```bash
make agent-guard
make ci-local-fast                # lint + format + typecheck + tests
make ci-local                     # + coverage + build
make quality-control              # import smoke + maturity + drift reports
```

On maturity failures, inspect `dist/quality/package-maturity.json` after
`make maturity-check` or download the `package-maturity` CI artifact.

Repeat until required jobs are green.

---

## Phase 2 — Gemini automated review

**Success criteria:** Gemini review read; valid findings fixed or documented;
CI green on post-fix SHA.

Gemini reviews: body contains 🙄 or author login matches `gemini` (case-insensitive).

```bash
gh pr view $PR --json reviews --jq '
  .reviews[]
  | select(
      (.body | test("🙄")) or
      (.author.login | ascii_downcase | test("gemini"))
    )
  | {author: .author.login, state: .state, body: .body[:200]}
'
```

Wait for the review before Phase 3. For each finding: fix and validate, or record
why it is a false positive (leave thread unresolved for humans).

When incorporated and CI is green:

```bash
gh pr ready $PR
```

Draft → open triggers Copilot Code Review.

---

## Phase 3 — Copilot review

**Success criteria:** Copilot feedback triaged; CI green on final SHA.

Author login matches `copilot` or `github-copilot`. Check inline comments:

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
gh api "repos/$REPO/pulls/$PR/comments" \
  --jq '[.[] | select(.user.login | ascii_downcase | test("copilot"))]'
```

Same decision process as Gemini. Push fixes and confirm CI before Phase 4.

---

## Phase 4 — Final audit (subagent)

**Success criteria:** Subagent returns explicit **PASS**; otherwise fix, push, re-run.

Spawn a read-only reviewer subagent with this brief:

> Audit PR #$PR on `frtb-capital` before merge-ready.
>
> 1. **Package boundary** — no sibling capital imports except orchestration.
> 2. **`CLAUDE.md` review checklist** — all ten items; cite failures.
> 3. **`make quality-control`** — report failed requirement ids from
>    `dist/quality/package-maturity.json` if any.
> 4. **Evidence** — touched `implemented` / `partial_runtime` packages have
>    non-placeholder maturity evidence.
> 5. **Regulatory citations** — new thresholds in `src/` have paragraph citations.
> 6. **Tests** — new public functions have normal-path and invalid-input tests.
>
> Verdict: **PASS** or **FAIL** with a numbered finding list.

On **FAIL**: apply fixes, push, green CI, re-audit. On **PASS**: continue to output.

---

## Final output

Report must include:

- PR URL and number
- Head SHA at completion
- CI conclusion per required job (list skipped jobs explicitly)
- Unresolved **human** thread count
- Draft state (must be `false` for merge-ready)
- `mergeable` from `gh pr view`
- Subagent verdict
- `git status --short`

**Merge-ready when:** required CI green, not draft, no unresolved human threads,
subagent **PASS**, mergeability not `CONFLICTING`.

---

## Worktree policy

Never commit from the protected main clone (`~/Documents/Projects/frtb-capital`).
Use `~/Documents/Projects/frtb-capital-worktrees/<agent>/<task>` on branch
`<agent>/<task>`. See `docs/AGENT_WORKTREE_POLICY.md`.