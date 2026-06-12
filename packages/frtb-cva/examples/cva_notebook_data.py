"""Synthetic CVA notebook inputs and Arrow batch helpers."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from types import ModuleType

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import NormalizedArrowTable, source_content_hash
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.adapters.arrow import (
    build_cva_counterparty_batch_from_arrow,
    build_cva_hedge_batch_from_arrow,
    build_cva_netting_set_batch_from_arrow,
    build_sa_cva_sensitivity_batch_from_arrow,
    normalize_cva_counterparty_arrow_table,
    normalize_cva_hedge_arrow_table,
    normalize_cva_netting_set_arrow_table,
    normalize_sa_cva_sensitivity_arrow_table,
)
from frtb_cva.batch import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva.sa_cva_reference_data import GIRR_VEGA_RATE_FACTOR

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PACKAGE_ROOT / "tests" / "fixtures"
NOTEBOOK_CALCULATION_DATE = date(2026, 5, 31)


@dataclass(frozen=True)
class LoadedBaFixture:
    """BA-CVA fixture data exposed for notebook walkthroughs."""

    fixture_name: str
    context: CvaCalculationContext
    cases: tuple[tuple[str, tuple[CvaCounterparty, ...], tuple[CvaNettingSet, ...]], ...]
    invalid_cases: tuple[
        tuple[str, str, tuple[CvaCounterparty, ...], tuple[CvaNettingSet, ...]], ...
    ]


@dataclass(frozen=True)
class LoadedSaFixture:
    """SA-CVA fixture data exposed for notebook walkthroughs."""

    fixture_name: str
    context: CvaCalculationContext
    cases: tuple[tuple[str, tuple[SaCvaSensitivity, ...], tuple[CvaHedge, ...]], ...]
    invalid_cases: tuple[tuple[str, str, tuple[SaCvaSensitivity, ...], tuple[CvaHedge, ...]], ...]
    expected_outputs: dict[str, object]


@dataclass(frozen=True)
class BaArrowBatchPack:
    """Arrow batches and package-owned batches for BA-CVA inputs."""

    counterparty_handoff: NormalizedArrowTable
    netting_set_handoff: NormalizedArrowTable
    hedge_handoff: NormalizedArrowTable | None
    counterparty_batch: CvaCounterpartyBatch
    netting_set_batch: CvaNettingSetBatch
    hedge_batch: CvaHedgeBatch | None


@dataclass(frozen=True)
class SaArrowBatchPack:
    """Arrow batches and package-owned batches for SA-CVA inputs."""

    sensitivity_handoff: NormalizedArrowTable
    hedge_handoff: NormalizedArrowTable | None
    sensitivity_batch: SaCvaSensitivityBatch
    hedge_batch: CvaHedgeBatch | None


def notebook_context(
    *,
    method: CvaMethod = CvaMethod.BA_CVA_REDUCED,
    run_id: str = "cva-notebook-demo",
    sa_cva_approved: bool = False,
    carve_out_netting_set_ids: tuple[str, ...] = (),
    sa_cva_sensitivity_scope_evidence_id: str | None = None,
) -> CvaCalculationContext:
    """Return a deterministic Basel MAR50 context for notebook examples."""

    return CvaCalculationContext(
        run_id=run_id,
        calculation_date=NOTEBOOK_CALCULATION_DATE,
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=method,
        sa_cva_approved=sa_cva_approved,
        carve_out_netting_set_ids=carve_out_netting_set_ids,
        sa_cva_sensitivity_scope_evidence_id=sa_cva_sensitivity_scope_evidence_id,
        desk_id="desk-cva",
        legal_entity="LE-CVA",
    )


def sample_lineage(
    source_row_id: str,
    *,
    source_file: str = "cva_notebook_inputs.csv",
    source_column_map: tuple[tuple[str, str], ...] = (),
) -> CvaSourceLineage:
    """Return deterministic source lineage for synthetic notebook inputs."""

    return CvaSourceLineage(
        source_system="synthetic-cva-notebook",
        source_file=source_file,
        source_row_id=source_row_id,
        source_column_map=source_column_map,
    )


def sample_counterparties() -> tuple[CvaCounterparty, ...]:
    """Return counterparties spanning BA-CVA sector and credit-quality buckets."""

    rows = (
        (
            "ctp-sovereign-ig",
            "desk-cva",
            "LE-CVA",
            CvaSector.SOVEREIGN,
            CreditQuality.INVESTMENT_GRADE,
            "EMEA",
        ),
        (
            "ctp-financial-hy",
            "desk-cva",
            "LE-CVA",
            CvaSector.FINANCIALS,
            CreditQuality.HIGH_YIELD,
            "AMER",
        ),
        (
            "ctp-technology-ig",
            "desk-cva",
            "LE-CVA",
            CvaSector.TECHNOLOGY_TELECOM,
            CreditQuality.INVESTMENT_GRADE,
            "APAC",
        ),
    )
    return tuple(
        CvaCounterparty(
            counterparty_id=counterparty_id,
            desk_id=desk_id,
            legal_entity=legal_entity,
            sector=sector,
            credit_quality=credit_quality,
            region=region,
            source_row_id=f"row-{counterparty_id}",
            lineage=sample_lineage(
                f"row-{counterparty_id}",
                source_column_map=(("counterparty", "counterparty_id"),),
            ),
        )
        for counterparty_id, desk_id, legal_entity, sector, credit_quality, region in rows
    )


def sample_netting_sets(
    counterparties: tuple[CvaCounterparty, ...] | None = None,
) -> tuple[CvaNettingSet, ...]:
    """Return synthetic BA-CVA netting-set exposures for the sample counterparties."""

    selected = sample_counterparties() if counterparties is None else counterparties
    counterparty_ids = {item.counterparty_id for item in selected}
    rows = (
        ("ns-sovereign-rates", "ctp-sovereign-ig", 1_000_000.0, 2.5, 0.9400247793),
        ("ns-sovereign-fx", "ctp-sovereign-ig", 350_000.0, 1.2, 0.9801986733),
        ("ns-financial-credit", "ctp-financial-hy", 750_000.0, 3.0, 0.9139311853),
        ("ns-technology-equity", "ctp-technology-ig", 500_000.0, 2.0, 0.9607894392),
    )
    return tuple(
        CvaNettingSet(
            netting_set_id=netting_set_id,
            counterparty_id=counterparty_id,
            ead=ead,
            effective_maturity=effective_maturity,
            discount_factor=discount_factor,
            currency="USD",
            sign_convention="non_negative",
            uses_imm_ead=False,
            source_row_id=f"row-{netting_set_id}",
            lineage=sample_lineage(
                f"row-{netting_set_id}",
                source_column_map=(("EAD", "ead"), ("M", "effective_maturity")),
            ),
        )
        for netting_set_id, counterparty_id, ead, effective_maturity, discount_factor in rows
        if counterparty_id in counterparty_ids
    )


def sample_direct_hedge(
    counterparty_id: str = "ctp-sovereign-ig",
) -> CvaHedge:
    """Return an eligible direct single-name CDS hedge for BA-CVA full."""

    return CvaHedge(
        hedge_id="hedge-sovereign-direct-cds",
        source_row_id="row-hedge-sovereign-direct-cds",
        counterparty_id=counterparty_id,
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=400_000.0,
        remaining_maturity=2.0,
        discount_factor=0.9607894392,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="eligibility-evidence-cds-001",
        lineage=sample_lineage("row-hedge-sovereign-direct-cds"),
    )


def sample_ineligible_hedge(
    counterparty_id: str = "ctp-financial-hy",
) -> CvaHedge:
    """Return an ineligible hedge to show the audit rejection path."""

    return CvaHedge(
        hedge_id="hedge-ineligible-internal",
        source_row_id="row-hedge-ineligible-internal",
        counterparty_id=counterparty_id,
        hedge_type=BaCvaHedgeType.INDEX_CDS,
        notional=250_000.0,
        remaining_maturity=1.5,
        discount_factor=0.9704455335,
        reference_sector=CvaSector.FINANCIALS,
        reference_credit_quality=CreditQuality.HIGH_YIELD,
        reference_region="AMER",
        reference_relation=HedgeReferenceRelation.SAME_SECTOR_AND_REGION,
        eligibility=HedgeEligibility.INELIGIBLE,
        is_internal=True,
        rejection_reason="internal hedge is not externally eligible",
        lineage=sample_lineage("row-hedge-ineligible-internal"),
    )


def sample_sa_sensitivities() -> tuple[SaCvaSensitivity, ...]:
    """Return SA-CVA sensitivities across supported delta and vega classes."""

    return (
        _sa_sensitivity(
            "sens-girr-usd-5y",
            SaCvaRiskClass.GIRR,
            SaCvaRiskMeasure.DELTA,
            "USD",
            "5y",
            1_000_000.0,
            tenor="5y",
        ),
        _sa_sensitivity(
            "sens-girr-vega-ir",
            SaCvaRiskClass.GIRR,
            SaCvaRiskMeasure.VEGA,
            "USD",
            GIRR_VEGA_RATE_FACTOR,
            300_000.0,
            volatility_input=0.2,
        ),
        _sa_sensitivity(
            "sens-fx-eur", SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA, "EUR", "SPOT", 750_000.0
        ),
        _sa_sensitivity(
            "sens-fx-gbp-vega",
            SaCvaRiskClass.FX,
            SaCvaRiskMeasure.VEGA,
            "GBP",
            "GBPUSD_VOL",
            200_000.0,
            volatility_input=0.18,
        ),
        _sa_sensitivity(
            "sens-ccs-cp1-5y",
            SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            SaCvaRiskMeasure.DELTA,
            "2",
            "CP1|INVESTMENT_GRADE",
            450_000.0,
            tenor="5y",
        ),
        _sa_sensitivity(
            "sens-rcs-ref-a",
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            SaCvaRiskMeasure.DELTA,
            "3",
            "REF_A",
            300_000.0,
        ),
        _sa_sensitivity(
            "sens-rcs-ref-a-vega",
            SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
            SaCvaRiskMeasure.VEGA,
            "3",
            "REF_A",
            120_000.0,
            volatility_input=0.25,
        ),
        _sa_sensitivity(
            "sens-equity-eq-a",
            SaCvaRiskClass.EQUITY,
            SaCvaRiskMeasure.DELTA,
            "5",
            "EQ_A",
            220_000.0,
        ),
        _sa_sensitivity(
            "sens-equity-eq-a-vega",
            SaCvaRiskClass.EQUITY,
            SaCvaRiskMeasure.VEGA,
            "5",
            "EQ_A",
            80_000.0,
            volatility_input=0.2,
        ),
        _sa_sensitivity(
            "sens-commodity-oil",
            SaCvaRiskClass.COMMODITY,
            SaCvaRiskMeasure.DELTA,
            "1",
            "OIL",
            180_000.0,
        ),
        _sa_sensitivity(
            "sens-commodity-oil-vega",
            SaCvaRiskClass.COMMODITY,
            SaCvaRiskMeasure.VEGA,
            "1",
            "OIL",
            90_000.0,
            volatility_input=0.3,
        ),
    )


def sample_mixed_inputs() -> tuple[
    tuple[CvaCounterparty, ...],
    tuple[CvaNettingSet, ...],
    tuple[SaCvaSensitivity, ...],
    CvaCalculationContext,
]:
    """Return a minimal mixed SA-CVA plus BA-CVA carve-out data set."""

    counterparties = sample_counterparties()[:2]
    netting_sets = sample_netting_sets(counterparties)
    carved = replace(netting_sets[0], carved_out_to_ba_cva=True)
    non_carved = netting_sets[1]
    sensitivities = (sample_sa_sensitivities()[0], sample_sa_sensitivities()[2])
    context = notebook_context(
        method=CvaMethod.MIXED_CARVE_OUT,
        run_id="cva-notebook-mixed",
        sa_cva_approved=True,
        carve_out_netting_set_ids=(carved.netting_set_id,),
        sa_cva_sensitivity_scope_evidence_id="notebook-sa-slice-non-carved",
    )
    return counterparties, (carved, non_carved), sensitivities, context


def load_ba_fixture(fixture_name: str = "ba_cva_reduced_v1") -> LoadedBaFixture:
    """Load a package-local BA-CVA validation fixture without importing tests."""

    loader = _load_fixture_module(fixture_name)
    return LoadedBaFixture(
        fixture_name=fixture_name,
        context=loader.load_fixture_context(),
        cases=loader.load_fixture_cases(),
        invalid_cases=loader.load_invalid_cases(),
    )


def load_sa_fixture(fixture_name: str = "sa_cva_girr_delta_v1") -> LoadedSaFixture:
    """Load a package-local SA-CVA validation fixture without importing tests."""

    loader = _load_fixture_module(fixture_name)
    return LoadedSaFixture(
        fixture_name=fixture_name,
        context=loader.load_fixture_context(),
        cases=loader.load_fixture_cases(),
        invalid_cases=loader.load_invalid_cases(),
        expected_outputs=loader.load_expected_outputs(),
    )


def counterparty_arrow_table(counterparties: tuple[CvaCounterparty, ...]) -> pa.Table:
    """Return the canonical Arrow counterparty table accepted by the CVA handoff."""

    return pa.table(
        {
            "counterparty_id": [item.counterparty_id for item in counterparties],
            "desk_id": [item.desk_id for item in counterparties],
            "legal_entity": [item.legal_entity for item in counterparties],
            "sector": [_enum_value(item.sector) for item in counterparties],
            "credit_quality": [_enum_value(item.credit_quality) for item in counterparties],
            "region": [item.region for item in counterparties],
            "source_row_id": [item.source_row_id for item in counterparties],
            "lineage_source_system": [_lineage_system(item.lineage) for item in counterparties],
            "lineage_source_file": [_lineage_file(item.lineage) for item in counterparties],
            "lineage_source_row_id": [
                _lineage_row(item.lineage, item.source_row_id) for item in counterparties
            ],
        },
        schema=pa.schema(
            [
                ("counterparty_id", pa.string()),
                ("desk_id", pa.string()),
                ("legal_entity", pa.string()),
                ("sector", pa.string()),
                ("credit_quality", pa.string()),
                ("region", pa.string()),
                ("source_row_id", pa.string()),
                ("lineage_source_system", pa.string()),
                ("lineage_source_file", pa.string()),
                ("lineage_source_row_id", pa.string()),
            ]
        ),
    )


def netting_set_arrow_table(netting_sets: tuple[CvaNettingSet, ...]) -> pa.Table:
    """Return the canonical Arrow netting-set table accepted by the CVA handoff."""

    return pa.table(
        {
            "netting_set_id": [item.netting_set_id for item in netting_sets],
            "counterparty_id": [item.counterparty_id for item in netting_sets],
            "ead": [item.ead for item in netting_sets],
            "effective_maturity": [item.effective_maturity for item in netting_sets],
            "discount_factor": [item.discount_factor for item in netting_sets],
            "currency": [item.currency for item in netting_sets],
            "sign_convention": [item.sign_convention for item in netting_sets],
            "uses_imm_ead": [item.uses_imm_ead for item in netting_sets],
            "source_row_id": [item.source_row_id for item in netting_sets],
            "carved_out_to_ba_cva": [item.carved_out_to_ba_cva for item in netting_sets],
            "discount_factor_explicit": [item.discount_factor_explicit for item in netting_sets],
            "lineage_source_system": [_lineage_system(item.lineage) for item in netting_sets],
            "lineage_source_file": [_lineage_file(item.lineage) for item in netting_sets],
            "lineage_source_row_id": [
                _lineage_row(item.lineage, item.source_row_id) for item in netting_sets
            ],
        },
        schema=pa.schema(
            [
                ("netting_set_id", pa.string()),
                ("counterparty_id", pa.string()),
                ("ead", pa.float64()),
                ("effective_maturity", pa.float64()),
                ("discount_factor", pa.float64()),
                ("currency", pa.string()),
                ("sign_convention", pa.string()),
                ("uses_imm_ead", pa.bool_()),
                ("source_row_id", pa.string()),
                ("carved_out_to_ba_cva", pa.bool_()),
                ("discount_factor_explicit", pa.bool_()),
                ("lineage_source_system", pa.string()),
                ("lineage_source_file", pa.string()),
                ("lineage_source_row_id", pa.string()),
            ]
        ),
    )


def hedge_arrow_table(hedges: tuple[CvaHedge, ...]) -> pa.Table:
    """Return the canonical Arrow hedge table accepted by the CVA handoff."""

    return pa.table(
        {
            "hedge_id": [item.hedge_id for item in hedges],
            "source_row_id": [item.source_row_id for item in hedges],
            "counterparty_id": [item.counterparty_id for item in hedges],
            "hedge_type": [_enum_value(item.hedge_type) for item in hedges],
            "notional": [item.notional for item in hedges],
            "remaining_maturity": [item.remaining_maturity for item in hedges],
            "discount_factor": [item.discount_factor for item in hedges],
            "reference_sector": [_enum_value(item.reference_sector) for item in hedges],
            "reference_credit_quality": [
                _enum_value(item.reference_credit_quality) for item in hedges
            ],
            "reference_region": [item.reference_region for item in hedges],
            "reference_relation": [_enum_value(item.reference_relation) for item in hedges],
            "eligibility": [_enum_value(item.eligibility) for item in hedges],
            "is_internal": [item.is_internal for item in hedges],
            "discount_factor_explicit": [item.discount_factor_explicit for item in hedges],
            "internal_desk_counterparty_id": [
                item.internal_desk_counterparty_id for item in hedges
            ],
            "sa_cva_risk_class": [
                _enum_value(item.sa_cva_risk_class) if item.sa_cva_risk_class else None
                for item in hedges
            ],
            "eligibility_evidence_id": [item.eligibility_evidence_id for item in hedges],
            "rejection_reason": [item.rejection_reason for item in hedges],
            "lineage_source_system": [_lineage_system(item.lineage) for item in hedges],
            "lineage_source_file": [_lineage_file(item.lineage) for item in hedges],
            "lineage_source_row_id": [
                _lineage_row(item.lineage, item.source_row_id) for item in hedges
            ],
        },
        schema=pa.schema(
            [
                ("hedge_id", pa.string()),
                ("source_row_id", pa.string()),
                ("counterparty_id", pa.string()),
                ("hedge_type", pa.string()),
                ("notional", pa.float64()),
                ("remaining_maturity", pa.float64()),
                ("discount_factor", pa.float64()),
                ("reference_sector", pa.string()),
                ("reference_credit_quality", pa.string()),
                ("reference_region", pa.string()),
                ("reference_relation", pa.string()),
                ("eligibility", pa.string()),
                ("is_internal", pa.bool_()),
                ("discount_factor_explicit", pa.bool_()),
                ("internal_desk_counterparty_id", pa.string()),
                ("sa_cva_risk_class", pa.string()),
                ("eligibility_evidence_id", pa.string()),
                ("rejection_reason", pa.string()),
                ("lineage_source_system", pa.string()),
                ("lineage_source_file", pa.string()),
                ("lineage_source_row_id", pa.string()),
            ]
        ),
    )


def sensitivity_arrow_table(sensitivities: tuple[SaCvaSensitivity, ...]) -> pa.Table:
    """Return the canonical Arrow SA-CVA sensitivity table accepted by the handoff."""

    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "risk_class": [_enum_value(item.risk_class) for item in sensitivities],
            "risk_measure": [_enum_value(item.risk_measure) for item in sensitivities],
            "sensitivity_tag": [_enum_value(item.sensitivity_tag) for item in sensitivities],
            "bucket_id": [item.bucket_id for item in sensitivities],
            "risk_factor_key": [item.risk_factor_key for item in sensitivities],
            "amount": [item.amount for item in sensitivities],
            "amount_currency": [item.amount_currency for item in sensitivities],
            "sign_convention": [item.sign_convention for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "tenor": [item.tenor for item in sensitivities],
            "volatility_input": [item.volatility_input for item in sensitivities],
            "hedge_id": [item.hedge_id for item in sensitivities],
            "index_treatment": [
                _enum_value(item.index_treatment) if item.index_treatment else None
                for item in sensitivities
            ],
            "index_max_sector_weight": [item.index_max_sector_weight for item in sensitivities],
            "index_homogeneous_sector_quality": [
                item.index_homogeneous_sector_quality for item in sensitivities
            ],
            "index_dominant_sector": [
                _enum_value(item.index_dominant_sector) if item.index_dominant_sector else None
                for item in sensitivities
            ],
            "index_remap_bucket_id": [item.index_remap_bucket_id for item in sensitivities],
            "lineage_source_system": [_lineage_system(item.lineage) for item in sensitivities],
            "lineage_source_file": [_lineage_file(item.lineage) for item in sensitivities],
            "lineage_source_row_id": [
                _lineage_row(item.lineage, item.source_row_id) for item in sensitivities
            ],
        },
        schema=pa.schema(
            [
                ("sensitivity_id", pa.string()),
                ("risk_class", pa.string()),
                ("risk_measure", pa.string()),
                ("sensitivity_tag", pa.string()),
                ("bucket_id", pa.string()),
                ("risk_factor_key", pa.string()),
                ("amount", pa.float64()),
                ("amount_currency", pa.string()),
                ("sign_convention", pa.string()),
                ("source_row_id", pa.string()),
                ("tenor", pa.string()),
                ("volatility_input", pa.float64()),
                ("hedge_id", pa.string()),
                ("index_treatment", pa.string()),
                ("index_max_sector_weight", pa.float64()),
                ("index_homogeneous_sector_quality", pa.bool_()),
                ("index_dominant_sector", pa.string()),
                ("index_remap_bucket_id", pa.string()),
                ("lineage_source_system", pa.string()),
                ("lineage_source_file", pa.string()),
                ("lineage_source_row_id", pa.string()),
            ]
        ),
    )


def build_ba_arrow_batches(
    counterparties: tuple[CvaCounterparty, ...],
    netting_sets: tuple[CvaNettingSet, ...],
    hedges: tuple[CvaHedge, ...] = (),
    *,
    source_label: str = "cva-ba-notebook-handoff",
) -> BaArrowBatchPack:
    """Normalize Arrow BA-CVA tables and build package-owned columnar batches."""

    counterparty_handoff = normalize_cva_counterparty_arrow_table(
        counterparty_arrow_table(counterparties),
        source_hash=source_content_hash(f"{source_label}:counterparties"),
    )
    netting_set_handoff = normalize_cva_netting_set_arrow_table(
        netting_set_arrow_table(netting_sets),
        source_hash=source_content_hash(f"{source_label}:netting-sets"),
    )
    hedge_handoff = (
        normalize_cva_hedge_arrow_table(
            hedge_arrow_table(hedges),
            source_hash=source_content_hash(f"{source_label}:hedges"),
        )
        if hedges
        else None
    )
    return BaArrowBatchPack(
        counterparty_handoff=counterparty_handoff,
        netting_set_handoff=netting_set_handoff,
        hedge_handoff=hedge_handoff,
        counterparty_batch=build_cva_counterparty_batch_from_arrow(counterparty_handoff),
        netting_set_batch=build_cva_netting_set_batch_from_arrow(netting_set_handoff),
        hedge_batch=build_cva_hedge_batch_from_arrow(hedge_handoff)
        if hedge_handoff is not None
        else None,
    )


def build_sa_arrow_batches(
    sensitivities: tuple[SaCvaSensitivity, ...],
    hedges: tuple[CvaHedge, ...] = (),
    *,
    source_label: str = "cva-sa-notebook-handoff",
) -> SaArrowBatchPack:
    """Normalize Arrow SA-CVA tables and build package-owned columnar batches."""

    sensitivity_handoff = normalize_sa_cva_sensitivity_arrow_table(
        sensitivity_arrow_table(sensitivities),
        source_hash=source_content_hash(f"{source_label}:sensitivities"),
    )
    hedge_handoff = (
        normalize_cva_hedge_arrow_table(
            hedge_arrow_table(hedges),
            source_hash=source_content_hash(f"{source_label}:hedges"),
        )
        if hedges
        else None
    )
    return SaArrowBatchPack(
        sensitivity_handoff=sensitivity_handoff,
        hedge_handoff=hedge_handoff,
        sensitivity_batch=build_sa_cva_sensitivity_batch_from_arrow(sensitivity_handoff),
        hedge_batch=build_cva_hedge_batch_from_arrow(hedge_handoff)
        if hedge_handoff is not None
        else None,
    )


def markdown_table(headers: tuple[str, ...], rows: tuple[tuple[object, ...], ...]) -> str:
    """Render a compact Markdown table from notebook result rows."""

    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = tuple("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join((header, separator, *body))


def _sa_sensitivity(
    sensitivity_id: str,
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    bucket_id: str,
    risk_factor_key: str,
    amount: float,
    *,
    tenor: str | None = None,
    volatility_input: float | None = None,
    index_treatment: SaCvaIndexTreatment | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=risk_class,
        risk_measure=risk_measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket_id,
        risk_factor_key=risk_factor_key,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-{sensitivity_id}",
        tenor=tenor,
        volatility_input=volatility_input,
        index_treatment=index_treatment,
        lineage=sample_lineage(
            f"row-{sensitivity_id}",
            source_column_map=(("amount", "amount"),),
        ),
    )


def _load_fixture_module(fixture_name: str) -> ModuleType:
    path = FIXTURE_ROOT / fixture_name / "loader.py"
    spec = importlib.util.spec_from_file_location(f"frtb_cva_notebook_{fixture_name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load fixture loader: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def _lineage_system(lineage: CvaSourceLineage | None) -> str:
    return lineage.source_system if lineage is not None else "synthetic-cva-notebook"


def _lineage_file(lineage: CvaSourceLineage | None) -> str:
    return lineage.source_file if lineage is not None else "cva_notebook_inputs.csv"


def _lineage_row(lineage: CvaSourceLineage | None, fallback: str) -> str:
    return lineage.source_row_id if lineage is not None else fallback
