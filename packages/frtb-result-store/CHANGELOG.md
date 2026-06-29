# Changelog

All notable changes to `frtb-result-store` will be documented here.

## [Unreleased]

## [0.1.1a1] - 2026-06-29

### Added

- Added canonical run identity generation, run-group identity generation, and append-only run status lifecycle events. (#445)
- Added configurable hierarchy node generation and canonical FRTB capital graph ID helpers. (#446)
- Added strict artifact schema registry, streaming ZSTD Parquet artifact writes, and first-pass measure/attribution vocabularies. (#447)
- Added required-artifact validation, persisted artifact expectation rows, and manifest-led commit staging. (#448)
- Added per-run schema compatibility checks, compact input manifests, result events, telemetry rows, and optional OpenTelemetry spans. (#449)
- Added persisted Parquet marts for capital summary, capital tree, and component breakdown dashboard queries. (#450)
- Added explicit attribution target projection, official movement-result storage, and a persisted movement summary mart. (#451)
- Added S3-layout Parquet result-store mode with manifest-gated local mock writes, logical `s3://` artifact paths, DuckDB configuration hooks, and orphaned staging cleanup. (#452)
- Added optional read-only FastAPI service endpoints for committed runs, run groups, capital trees, measures, artifacts, attribution, lineage, events, movements, and regime comparison. (#453)
- Added read-only artifact drillthrough API endpoints for paged Parquet rows,
  column selection, equality filters, local downloads, and S3 URI handoff. (#454)
- Added result-store admin helpers and CLI commands for inspection, run listing,
  derived catalog refresh, store validation, read-only SQL access, and one-way
  single-run export with checksums that excludes `catalog.duckdb`. (#455)
- Expanded persisted result-store reporting marts to the full first-pass set and
  added representative dashboard and artifact first-page latency fixtures. (#456)
- Added the initial DuckDB/Parquet FRTB result-store package, contracts, backend slice, and design documentation. (#459)
- Add persisted attribution explain marts and API projections for residual and unsupported records. (#603)

### Changed

- Split result-store IO and entity dataclasses into focused internal modules while preserving public imports. (#542)
- Extract capital-summary and regime-comparison mart row builders into `mart_summary_rows.py`. (#800)

### Documentation

- Document result-store storage contracts and split io/model modules for maintainability.

  Closes #509 (#509)
- Document NumPy-style docstrings (issue #648). (#648)
- Document NumPy-style docstrings (issue #649). (#649)

### Added

- Added first DuckDB/Parquet result-store contracts and local append-only
  backend.
