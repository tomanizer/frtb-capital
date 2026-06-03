# frtb-capital documentation audit checklist

Use during Step 3 of `frtb-doc-audit`. Mark each item pass / fail / N/A per package.

## Package front door

- [ ] `packages/<pkg>/README.md` exists and states correct maturity
- [ ] README links to `docs/modules/<pkg>/` and key package-local docs
- [ ] `AGENTS.md` current status matches code (no false "scaffold only")
- [ ] `CLAUDE.md` exists for packages with agent guidance (all capital + common + result-store)
- [ ] Install/test commands present where integrators need them (IMA, SBM yes; common N/A)

## Module and API docs

- [ ] `docs/modules/<pkg>/README.md` present (capital components)
- [ ] `docs/modules/<pkg>/PUBLIC_API.md` present for capital packages with client integration
- [ ] PUBLIC_API stable surface matches `__init__.py` `__all__` and public API tests
- [ ] Tiered client integration table (Arrow / adapter / dataclass) where applicable
- [ ] `to_component_summary` documented for SBM, DRC, RRAO when exported

## Regulatory and model evidence

- [ ] Package `docs/REGULATORY_TRACEABILITY.md` or module equivalent exists for capital pkgs
- [ ] Model documentation pack under `docs/modules/<pkg>/model_documentation/` aligned with maturity plan
- [ ] Requirements YAML under `docs/modules/<pkg>/requirements/` when package has registry entry

## Code alignment

- [ ] `calculation_entrypoint` in maturity registry resolves and matches docs
- [ ] `PACKAGE_METADATA.implementation_status` consistent with README prose
- [ ] Unsupported paths described as fail-closed, not missing silently
- [ ] No doc claim that sibling packages are "scaffolded" when they have partial/implemented runtime

## Cross-repo consistency

- [ ] `docs/ARCHITECTURE.md` package section matches package README
- [ ] `docs/modules/README.md` summary row matches package README
- [ ] ADRs cited in docs not contradicted by current code (grep `calculate_suite_capital`, SA composition)
- [ ] Root `CLAUDE.md` workspace tree lists all packages with accurate labels

## Stale-language grep (repo-wide)

Run from workspace root:

```bash
rg -n "scaffolded sibling|does not calculate suite|remains explicitly unimplemented|row-wise curvature capital remain" \
  packages docs CLAUDE.md AGENTS.md --glob '*.md'
```

Investigate every hit; fix or justify in ADR/historical note.

## Fix priority

| Priority | Examples |
| --- | --- |
| P0 | Orchestration README vs `calculate_suite_capital` implementation |
| P0 | ARCHITECTURE contradicts batch/Arrow paths |
| P1 | Missing PUBLIC_API; ADR missing for implemented behaviour |
| P1 | IMA/RRAO profile list incomplete in PUBLIC_API |
| P2 | Thin DRC README; DOCUMENTATION_AUDIT date; missing CLAUDE.md |