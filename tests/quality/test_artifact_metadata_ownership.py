from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_DOC = ROOT / "docs" / "ARTIFACT_METADATA_OWNERSHIP.md"

RUNTIME_BOUNDARY_ROOTS = (
    ROOT / "packages" / "frtb-ima" / "src",
    ROOT / "packages" / "frtb-sbm" / "src",
    ROOT / "packages" / "frtb-drc" / "src",
    ROOT / "packages" / "frtb-rrao" / "src",
    ROOT / "packages" / "frtb-cva" / "src",
    ROOT / "packages" / "frtb-orchestration" / "src",
)

AGENT_BRIEFS_WITH_ARTIFACT_OWNERSHIP = (
    ROOT / "AGENTS.md",
    ROOT / "packages" / "frtb-common" / "AGENTS.md",
    ROOT / "packages" / "frtb-result-store" / "AGENTS.md",
    ROOT / "packages" / "frtb-orchestration" / "AGENTS.md",
    ROOT / "packages" / "frtb-navigator" / "AGENTS.md",
)


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_artifact_metadata_ownership_doc_covers_required_layers() -> None:
    doc = OWNERSHIP_DOC.read_text(encoding="utf-8")

    for required in (
        "`frtb-common`",
        "Component packages (`frtb-ima`, `frtb-sbm`, `frtb-drc`, `frtb-rrao`, `frtb-cva`)",
        "`frtb-result-store`",
        "`frtb-orchestration`",
        "Navigator/backend adapter",
        "Market-data lookup",
        "fetching stored artifacts",
        "Browser direct Parquet/S3 reads",
        "client-side RFET/PLA/backtesting/shock/surface classification",
        "component packages and orchestration do not import `frtb_result_store`",
    ):
        assert required in doc


def test_artifact_metadata_ownership_is_linked_from_agent_briefs_and_docs_index() -> None:
    for path in AGENT_BRIEFS_WITH_ARTIFACT_OWNERSHIP:
        assert "ARTIFACT_METADATA_OWNERSHIP.md" in path.read_text(encoding="utf-8")

    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")

    assert "ARTIFACT_METADATA_OWNERSHIP.md" in docs_index
    assert "ARTIFACT_METADATA_OWNERSHIP.md" in architecture


def test_result_store_contract_forbids_browser_artifact_inference() -> None:
    contract = (
        ROOT / "docs" / "modules" / "frtb-navigator" / "RESULT_STORE_DATA_CONTRACT.md"
    ).read_text(encoding="utf-8")

    for required in (
        "Browser direct Parquet/S3 reads are forbidden",
        "must not construct object-store URLs or local file paths",
        "infer missing attribution, RFET/SES, PLA, backtesting, or eligibility status",
    ):
        assert required in contract


def test_components_and_orchestration_do_not_import_result_store_runtime() -> None:
    offenders: list[str] = []
    for root in RUNTIME_BOUNDARY_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "frtb_result_store" in _imported_roots(path):
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
