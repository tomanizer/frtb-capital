---
name: frtb-ci-babysit
description: >-
  Babysit an frtb-capital PR from push to merge-ready: classify required CI,
  stabilise CI, gate PR template, resolve review threads, incorporate bot reviews
  when available, run final quality audit.
when-to-use: >-
  Use when asked to babysit, watch, or fix a frtb-capital PR, monitor CI until
  green, incorporate bot review feedback, resolve PR conversations, or runs
  /frtb-ci-babysit.
argument-hint: "[<pr-number>] [--agent <name>] [--ci-only | --skip-reviews | --reviews-only]"
allowed-tools: Shell, Read, Grep, Glob, Write, StrReplace, Task
---

# FRTB CI babysit

Babysit an `frtb-capital` pull request from push through merge-readiness. Phases
run in order; complete each before advancing unless a mode flag skips phases.

Read `AGENTS.md`, `CLAUDE.md`, and `.grok/skills/frtb-capital/SKILL.md` before
editing code.

**Reference files** (read when the step points to them):

| File | Use |
| --- | --- |
| `references/ci-job-matrix.md` | Step 0.5 — which CI jobs must pass |
| `references/pr-template-gate.md` | Step 0.6 — PR body / ADR 0015 gates |
| `references/conversations.md` | Phase 3.5 — consider and resolve all threads |
| `references/qc-failures.md` | Phase 1 — `quality-control` failures |

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
| `--agent <name>` | Worktree agent id (`BABYSITTER`): `grok`, `claude`, `codex`, `cursor`, `copilot`. Default: infer or `grok`. |
| `--ci-only` | Phases 0 → 0.5 → 0.6 → 1 only; skip 2, 3, 3.5, 4. Report CI + template + thread counts. |
| `--skip-reviews` | Skip Phases 2–3 (still run 3.5 unless `--ci-only`). Use for docs-only or when user requests no bot wait. |
| `--reviews-only` | Phases 0, 2, 3, 3.5 only (assume CI already green). Re-validate SHA; run 1 if checks fail. |

Requires `gh` authenticated for the repository and a compliant agent worktree for
commits.

Record `BABYSITTER` from `--agent` or context. Fallback reviews must use a
**different** reviewer than `BABYSITTER` (do not trigger Cursor Bugbot if
`BABYSITTER=cursor`; Phase 4 subagent is not a substitute for Phase 2 when Gemini
could still run).

---

## Step 0 — Start state

**Success criteria:** `PR` exported; worktree guard passed; baseline recorded.

```bash
gh pr view ${PR:-} --json number,title,headRefName,baseRefName,isDraft,mergeable,state
export PR=$(gh pr view ${PR:-} --json number --jq .number)
export HEAD_SHA=$(gh pr view $PR --json headRefOid -q .headRefOid)
```

If no PR exists for the current branch, stop and ask the user. Set `$PR` and
`HEAD_SHA` once per “review generation”; refresh `HEAD_SHA` after every push (see
**SHA discipline**).

Worktree compliance (required before any edit):

```bash
make agent-ensure AGENT=<agent> TASK=ci-babysit
```

If not already in a compliant worktree, this creates or reuses one and prints
`next: cd ...` — **change directory there before any edit**. Then `gh pr checkout $PR`
if babysitting an existing PR.

If `mergeable` is `CONFLICTING`, stop: report conflict; do not babysit until the
author rebases or merges base. Offer to resolve only if the user explicitly asks.

Record: PR number, `HEAD_SHA`, draft state, base branch, CI run count, unresolved
review thread count, `BABYSITTER`, and mode flags.

### SHA discipline

After **every** `git push` to the PR branch:

1. `export HEAD_SHA=$(gh pr view $PR --json headRefOid -q .headRefOid)`
2. If SHA changed since the start of Phase 2, 3, or 4, **re-run Phase 1** until
   required jobs are green for the new SHA.
3. Bot reviews tied to the old SHA are stale; re-run Phase 2/3 only if not skipped.

Cap fix loops: **at most 3** push/fix cycles in Phase 1 and **at most 3** in
Phase 4. On the 4th failure, stop and report with logs and thread state.

---

## Step 0.5 — Classify changed paths

**Success criteria:** `REQUIRED_JOBS` list derived; docs-only fast path flag set.

```bash
python3 scripts/ci/classify_changed_paths.py
```

Parse `changes_code`, `changes_docs`, `changes_dependency`, `changes_notebooks`,
`changes_examples`, `changes_workflow` from stdout. Build `REQUIRED_JOBS` per
`references/ci-job-matrix.md`.

Set `DOCS_ONLY_FAST_PATH=true` when `changes_code=false`, `changes_docs=true`,
and `changes_workflow=false`.

When `DOCS_ONLY_FAST_PATH` and user did not pass `--skip-reviews`, default to
skipping Phases 2–3 (record reason in the final report).

---

## Step 0.6 — PR template gate

**Success criteria:** Template sections satisfied or blockers listed.

Follow `references/pr-template-gate.md`. Fix PR body via `gh pr edit $PR --body-file`
when the babysitter can correct omissions (checkboxes, `Closes #N`, verification).

Unresolved template blockers are **merge blockers** (especially missing `Closes #N`
when the PR claims to close issues, or version bumps on non-`release/*` branches).

Re-run this step after the last push before merge-ready.

---

## Reviewer availability helpers

Use these patterns on PR issue comments, review bodies, check summaries, and
job logs. Case-insensitive matching is enough.

### Gemini unavailable (skip Gemini wait)

Match any of:

- `try again later`
- `blocked for 24`
- `24 hour`
- `rate limit` / `quota exceeded`
- `not available` (in a Gemini/Code Assist context)
- No Gemini review after **5 minutes** from first green CI on the current `HEAD_SHA`

### Copilot unavailable (skip Phase 3)

Match any of:

- `run out of ai credits`
- `ai credits for the month`
- `out of credits`
- `copilot subscription`
- `billing` + `copilot` (in the same comment)
- Copilot review explicitly failed or disabled for the repo

Collect recent PR text:

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
gh api "repos/$REPO/issues/$PR/comments" --paginate \
  --jq '.[].body' | head -c 200000
gh pr view $PR --json reviews --jq '.reviews[].body'
```

When a phase is skipped, record `SKIPPED: <phase> — <reason>` in the final report.

---

## Phase 1 — CI stabilisation

**Success criteria:** Every job in `REQUIRED_JOBS` is `success`; acceptable skips
documented in `references/ci-job-matrix.md`.

Skip this phase when `--reviews-only` and all `REQUIRED_JOBS` are already green on
`HEAD_SHA`; on any failure, run Phase 1 fully.

### Monitor

```bash
gh pr checks $PR --watch
```

Prefer aggregate `ci-required` when present. On failure:

```bash
gh run view <run-id> --log-failed
```

Use `references/qc-failures.md` for `quality-control` failures.

### Local validation

Narrow commands per Step 0.5 / `references/ci-job-matrix.md`:

```bash
make agent-guard
# docs-only: make docs-check
# code: make ci-local-fast or make ci-local; then make quality-control when QC failed on CI
```

Repeat until `REQUIRED_JOBS` are green (max **3** fix loops). Refresh `HEAD_SHA` after
each push.

---

## Phase 2 — External code review (Gemini or fallbacks)

**Skip when:** `--ci-only`, `--skip-reviews`, or `DOCS_ONLY_FAST_PATH` (default).

**Success criteria:** One external review path completed (incorporated or
documented skip), or all paths skipped with explicit reasons; CI green on `HEAD_SHA`
before Phase 3/4.

Track `PHASE2_STATUS`: `gemini` | `cursor-bugbot` | `pr-comment-review` | `skipped`.

### 2a — Try Gemini

Poll for a Gemini/Code Assist review (🙄 in body or author login matches `gemini`):

```bash
gh pr view $PR --json reviews --jq '
  .reviews[]
  | select(
      (.body | test("🙄")) or
      (.author.login | ascii_downcase | test("gemini"))
    )
  | {author: .author.login, state: .state, body: .body[:500]}
'
```

- If a review arrives: triage findings (fix + validate, or document false positives).
  Set `PHASE2_STATUS=gemini`. Go to **2d**.
- If PR text matches **Gemini unavailable** patterns: skip Gemini. Go to **2b**.
- If **5 minutes** elapse with no Gemini review and no availability error: treat as
  unavailable; go to **2b**. Recheck every **30–60 seconds** during the window.

### 2b — Fallback reviews (Gemini unavailable only)

Try each path below **in order**. Stop at the first path that produces actionable
review content. Do not use the babysitting agent as the “external” reviewer.

#### Fallback 1 — Cursor Bugbot (preferred GitHub trigger)

Skip when `BABYSITTER=cursor`.

Post a **new top-level** PR comment:

```bash
gh pr comment $PR --body "@cursoragent review"
```

If Bugbot does not respond within the poll window, retry once with `cursor review`
or `bugbot run` before Fallback 2.

Poll up to **5 minutes** (recheck every **30–60 seconds**) for Bugbot check or
`cursor` / `bugbot` review comments.

If findings arrive: triage. Set `PHASE2_STATUS=cursor-bugbot`. Go to **2d**.

#### Fallback 2 — Non-author PR review comment

Spawn a read-only subagent (not `BABYSITTER`). Post summary via `gh pr review $PR
--comment --body-file ...`. Set `PHASE2_STATUS=pr-comment-review`. Go to **2d**.

#### Fallback 3 — Skip external review

Set `PHASE2_STATUS=skipped` with reason. Phase 4 still runs.

### 2c — Incorporate findings

Apply valid fixes, validate locally (narrow per 0.5), push, refresh `HEAD_SHA`, re-run
Phase 1 if SHA changed.

### 2d — Mark PR ready (for Copilot when available)

If draft and Copilot not pre-flagged unavailable:

```bash
gh pr ready $PR
```

---

## Phase 3 — Copilot review (optional)

**Skip when:** `--ci-only`, `--skip-reviews`, `DOCS_ONLY_FAST_PATH`, or Copilot unavailable.

**Success criteria:** Copilot triaged, or **skipped** with reason; CI green on `HEAD_SHA`.

### 3a — Availability

Scan for **Copilot unavailable** patterns before waiting. If matched:
`COPILOT_STATUS=skipped` → Phase 3.5.

### 3b — Wait and incorporate

Wait up to **5 minutes** after `gh pr ready` (recheck every **30–60 seconds**).
On credit/quota messages: skip. Triage findings; push; refresh SHA; re-run Phase 1 if needed.

---

## Phase 3.5 — Review conversations (consider and resolve)

**Skip when:** `--ci-only` only. Run after Phases 2–3, or after Phase 1 when reviews
were skipped. **Run again** after the last fix push.

**Success criteria:** **Zero unresolved review threads**; every thread considered.

Follow `references/conversations.md` in full:

1. List all unresolved threads (GraphQL query in reference).
2. Scan top-level issue comments for actionable human requests.
3. For **each** thread: consider → act (fix or reply) → resolve when addressed or
   explicitly declined with a posted reply.
4. Do not resolve human threads without a reply.

Report: threads considered, resolved, deferred (with issue/ADR cite).

---

## Phase 4 — Final audit (subagent)

**Skip when:** `--ci-only`.

**Success criteria:** Subagent returns **PASS**; CI green on `HEAD_SHA`; max **3** loops.

Spawn a read-only reviewer subagent:

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

On **FAIL**: fix, push, refresh `HEAD_SHA`, Phase 1 if needed, Phase 3.5, re-audit.
On **PASS**: run Step 0.6 and Phase 3.5 once more, then final output.

---

## Final output

Report must include:

- PR URL and number
- `HEAD_SHA` at completion
- `REQUIRED_JOBS` and per-job CI conclusion (skipped jobs explicit)
- Step 0.6 template gate: pass or blockers
- **Phase 2:** `PHASE2_STATUS` and skip/fallback reasons
- **Phase 3:** `COPILOT_STATUS` (`completed` or `skipped` + reason)
- **Phase 3.5:** threads considered / resolved / open (open must be 0 for merge-ready)
- Draft state (`false` for merge-ready)
- `mergeable` from `gh pr view`
- Subagent verdict (Phase 4) or `N/A` for `--ci-only`
- Mode flags used
- Fix loop counts (Phase 1 / Phase 4)
- `git status --short`

**Merge-ready when:** all `REQUIRED_JOBS` green, Step 0.6 pass, not draft,
**zero unresolved review threads**, subagent **PASS** (unless `--ci-only`),
`mergeable` not `CONFLICTING`.

Skipped Gemini/Copilot/fallback reviews are not merge blockers when documented;
Phase 4 subagent audit remains required unless `--ci-only`.

---

## Worktree policy

Never commit from the protected main clone (`~/Documents/Projects/frtb-capital`).
Use `~/Documents/Projects/frtb-capital-worktrees/<agent>/<task>` on branch
`<agent>/<task>`. See `docs/AGENT_WORKTREE_POLICY.md`.
