# Result-store backend acceptance criteria

Use this checklist before enabling a new durable backend mode in non-test
environments—for example, a real S3/MinIO object store instead of the local
`s3_mock_root` adapter.

These criteria extend the storage contract in
[STORAGE_CONTRACT.md](STORAGE_CONTRACT.md). All items must pass in CI and in a
pilot environment against representative run bundles.

## Preconditions

- An ADR documents the backend mode, dependency additions, and any change to
  manifest fields or path layout.
- IO dependencies remain inside `frtb-result-store` storage modules only.
- No imports from capital or orchestration packages enter the backend runtime.

## Manifest and publish semantics

- [ ] Runs become visible only after `run_manifest.json` is durably published.
- [ ] Manifest is written after all referenced Parquet and artifact objects are
  reachable at their recorded paths/URIs.
- [ ] Duplicate `run_id` commits fail without overwriting prior evidence.
- [ ] Failed writes leave no reader-visible run (no manifest, no orphaned reads).
- [ ] Crash injection between publish steps leaves only cleanable orphans.

## Schema and checksum enforcement

- [ ] Missing required artifacts fail before manifest commit.
- [ ] Artifact schema fingerprint mismatch fails before manifest commit.
- [ ] Manifest records base, artifact, and mart schema fingerprints.
- [ ] Readers fail closed on schema version or fingerprint mismatch.
- [ ] Identity payloads in the manifest match stored run rows.

## Identity and immutability

- [ ] `run_id`, graph node ids, artifact ids, and status event ids remain
  deterministic for unchanged inputs.
- [ ] Append-only status history preserves ordering and prior events.
- [ ] No backend path rewrites committed Parquet for lifecycle changes.

## Orphan and cleanup behavior

- [ ] Parquet or artifact objects without manifests are ignored by list/query
  paths.
- [ ] Retries for the same `run_id` remove prior orphaned objects safely.
- [ ] Admin validation surfaces orphan/manifest mismatches explicitly.

## Read surfaces

- [ ] Domain query methods return identical payloads for local and backend mode
  given the same bundle (modulo URI scheme).
- [ ] FastAPI routes remain read-only and do not expose unauthenticated writes.
- [ ] Derived catalog refresh failure does not roll back committed runs.

## Performance and operations

- [ ] Pilot workload completes `write_bundle` within agreed latency bounds.
- [ ] Query p95 for primary dashboard marts meets agreed bounds on pilot data.
- [ ] Export/validate admin commands work against the backend root.
- [ ] Observability spans cover write, artifact staging, manifest commit, and
  catalog refresh without logging raw capital rows.

## Evidence preserved vs correctness scope

- [ ] Documentation states clearly that the backend preserves evidence integrity,
  not regulatory capital correctness.
- [ ] Run approval / officialization workflow remains outside the store.

## Test evidence required in PR

- Integration tests using the backend adapter (mock or real pilot endpoint).
- Failure-injection tests for manifest-last publish and orphan invisibility.
- Compatibility tests proving unchanged fingerprints for golden fixtures.
- `make quality-control` clean for `packages/frtb-result-store`.

Do not enable production traffic until every box is checked and linked to test
names or runbook steps in the PR description.
