from __future__ import annotations

from pathlib import Path

import frtb_sbm
import frtb_sbm.adapters.arrow as adapter_arrow
import frtb_sbm.adapters.crif_arrow as adapter_crif_arrow
import frtb_sbm.adapters.crif_models as adapter_crif_models
import frtb_sbm.adapters.crif_rows as adapter_crif_rows
import frtb_sbm.adapters.sensitivities as adapter_sensitivities
import frtb_sbm.aggregation as aggregation
import frtb_sbm.arrow_batch as arrow_batch
import frtb_sbm.assembly.hashes as assembly_hashes
import frtb_sbm.audit as audit
import frtb_sbm.batch as batch
import frtb_sbm.capital as capital
import frtb_sbm.crif as crif
import frtb_sbm.curvature as curvature
import frtb_sbm.curvature_correlations as curvature_correlations
import frtb_sbm.curvature_factors as curvature_factors
import frtb_sbm.curvature_reference_data as curvature_reference_data
import frtb_sbm.fx_reference_data as fx_reference_data
import frtb_sbm.girr_reference_data as girr_reference_data
import frtb_sbm.kernel.aggregation as kernel_aggregation
import frtb_sbm.kernel.correlation_scenarios as kernel_correlation_scenarios
import frtb_sbm.kernel.pairwise_evidence as kernel_pairwise_evidence
import frtb_sbm.kernel.portfolio as portfolio
import frtb_sbm.kernel.scenario_alignment as kernel_scenario_alignment
import frtb_sbm.kernel.weighting as kernel_weighting
import frtb_sbm.reference_data as reference_data
import frtb_sbm.reference_payload as reference_payload
import frtb_sbm.reference_profiles as reference_profiles
import frtb_sbm.reference_types as reference_types
import frtb_sbm.risk_classes.commodity_weighting as commodity_weighting
import frtb_sbm.risk_classes.equity_weighting as equity_weighting
import frtb_sbm.risk_classes.fx_weighting as fx_weighting
import frtb_sbm.risk_classes.girr as girr
import frtb_sbm.risk_classes.girr_weighting as girr_weighting
import frtb_sbm.risk_classes.vega as vega
import frtb_sbm.risk_classes.vega_correlations as vega_correlations
import frtb_sbm.risk_classes.vega_validation as vega_validation
import frtb_sbm.risk_classes.vega_weighting as vega_weighting
import frtb_sbm.validation as validation
import frtb_sbm.validation.batch as validation_batch
import frtb_sbm.validation.batch_arrays as validation_batch_arrays
import frtb_sbm.validation.batch_lineage as validation_batch_lineage
import frtb_sbm.validation.coercion as validation_coercion
import frtb_sbm.validation.context as validation_context
import frtb_sbm.validation.sensitivity as validation_sensitivity
import frtb_sbm.vega_reference_data as vega_reference_data
import frtb_sbm.weighted_sensitivity as weighted_sensitivity

HANDOFF_SPECS = (
    "GIRR_DELTA_ARROW_COLUMN_SPECS",
    "GIRR_VEGA_ARROW_COLUMN_SPECS",
    "GIRR_CURVATURE_ARROW_COLUMN_SPECS",
    "FX_DELTA_ARROW_COLUMN_SPECS",
    "FX_VEGA_ARROW_COLUMN_SPECS",
    "FX_CURVATURE_ARROW_COLUMN_SPECS",
    "EQUITY_DELTA_ARROW_COLUMN_SPECS",
    "EQUITY_VEGA_ARROW_COLUMN_SPECS",
    "EQUITY_CURVATURE_ARROW_COLUMN_SPECS",
    "COMMODITY_DELTA_ARROW_COLUMN_SPECS",
    "COMMODITY_VEGA_ARROW_COLUMN_SPECS",
    "COMMODITY_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS",
)

ATTRIBUTION_AND_IMPACT = (
    "calculate_sbm_attribution",
    "calculate_sbm_capital_impact",
)

REGISTRY_SURFACE = (
    "SBM_BATCH_SPECS",
    "SBM_BATCH_PATH_ORDER",
    "SbmBatchSpec",
    "build_sbm_batch",
    "build_sbm_batch_from_arrow",
    "calculate_sbm_capital_from_arrow",
    "calculate_sbm_capital_from_batch",
    "input_hash_for_batch",
    "normalize_sbm_arrow_table",
)

ARROW_ADAPTER_SURFACE = (
    *HANDOFF_SPECS,
    "build_sbm_batch_from_arrow",
    "calculate_sbm_capital_from_arrow",
    "calculate_sbm_portfolio_capital_from_arrow_tables",
    "normalize_sbm_arrow_table",
)

BATCH_INGRESS_SURFACE = (
    "build_sbm_batch",
    "build_sbm_batch_from_columns",
)


REMOVED_PATH_BATCH_BUILDERS = (
    "build_girr_delta_batch_from_sensitivities",
    "build_girr_vega_batch_from_sensitivities",
    "build_fx_delta_batch_from_sensitivities",
    "build_equity_delta_batch_from_sensitivities",
    "build_commodity_delta_batch_from_sensitivities",
    "build_csr_nonsec_delta_batch_from_sensitivities",
    "build_csr_sec_nonctp_delta_batch_from_sensitivities",
    "build_csr_sec_ctp_delta_batch_from_sensitivities",
    "build_girr_delta_batch_from_columns",
    "build_girr_vega_batch_from_columns",
    "build_girr_curvature_batch_from_columns",
    "build_fx_delta_batch_from_columns",
    "build_equity_delta_batch_from_columns",
    "build_commodity_delta_batch_from_columns",
    "build_csr_nonsec_delta_batch_from_columns",
    "build_csr_sec_nonctp_delta_batch_from_columns",
    "build_csr_sec_ctp_delta_batch_from_columns",
)

VALIDATION_SURFACE = (
    "coerce_risk_class",
    "coerce_risk_measure",
    "coerce_sign_convention",
    "ensure_sbm_run_supported",
    "normalise_currency_code",
    "phase1_capital_supported_paths",
    "validate_sbm_calculation_context",
    "validate_sbm_sensitivities",
)


def test_documented_handoff_surface_is_top_level_importable() -> None:
    exported = set(frtb_sbm.__all__)
    documented = _public_api_doc()
    for name in (*HANDOFF_SPECS, *ATTRIBUTION_AND_IMPACT, *REGISTRY_SURFACE):
        assert name in exported
        assert hasattr(frtb_sbm, name)
        assert f"`{name}`" in documented


def test_top_level_public_api_surface_remains_bounded() -> None:
    assert len(frtb_sbm.__all__) < 400


def test_arrow_batch_shim_reexports_adapter_surface() -> None:
    for name in ARROW_ADAPTER_SURFACE:
        assert name in adapter_arrow.__all__
        assert name in arrow_batch.__all__
        assert getattr(arrow_batch, name) is getattr(adapter_arrow, name)


def test_batch_module_reexports_sensitivity_adapter_surface() -> None:
    for name in BATCH_INGRESS_SURFACE:
        assert name in adapter_sensitivities.__all__
        assert name in batch.__all__
        assert getattr(batch, name) is getattr(adapter_sensitivities, name)


def test_path_specific_batch_builder_wrappers_are_not_exported() -> None:
    for name in REMOVED_PATH_BATCH_BUILDERS:
        assert name not in frtb_sbm.__all__
        assert name not in batch.__all__
        assert not hasattr(frtb_sbm, name)
        assert not hasattr(batch, name)


def test_validation_package_reexports_stage_surface() -> None:
    for name in VALIDATION_SURFACE:
        assert name in validation.__all__

    assert validation.coerce_risk_class is validation_coercion.coerce_risk_class
    assert validation.validate_sbm_calculation_context is (
        validation_context.validate_sbm_calculation_context
    )
    assert (
        validation.validate_sbm_sensitivities is validation_sensitivity.validate_sbm_sensitivities
    )


def test_batch_validation_stage_modules_are_importable() -> None:
    assert callable(validation_batch.validate_homogeneous_batch_arrays)
    assert callable(validation_batch_arrays.object_array)
    assert callable(validation_batch_lineage.validate_source_column_maps)


def test_capital_module_reexports_portfolio_kernel_surface() -> None:
    assert (
        capital.calculate_sbm_portfolio_capital_from_batches
        is portfolio.calculate_sbm_portfolio_capital_from_batches
    )


def test_aggregation_module_reexports_kernel_surface() -> None:
    assert weighted_sensitivity.sort_weighted_sensitivities_deterministic is (
        kernel_weighting.sort_weighted_sensitivities_deterministic
    )
    assert frtb_sbm.aggregate_intra_bucket is kernel_aggregation.aggregate_intra_bucket
    assert frtb_sbm.aggregate_inter_bucket is kernel_aggregation.aggregate_inter_bucket

    assert frtb_sbm.adjust_correlation_matrix_for_scenario is (
        kernel_correlation_scenarios.adjust_correlation_matrix_for_scenario
    )
    assert aggregation.pairwise_correlation_audit_from_matrix is (
        kernel_pairwise_evidence.pairwise_correlation_audit_from_matrix
    )
    assert aggregation.select_portfolio_correlation_scenario is (
        kernel_scenario_alignment.select_portfolio_correlation_scenario
    )


def test_girr_risk_class_kernel_stage_is_importable() -> None:
    assert callable(girr.calculate_girr_delta_risk_class_capital_from_batch)
    assert callable(girr.calculate_girr_vega_risk_class_capital_from_batch)
    assert "calculate_girr_delta_risk_class_capital_from_batch" in girr.__all__
    assert "calculate_girr_vega_risk_class_capital_from_batch" in girr.__all__


def test_weighting_stage_modules_back_compatibility_surface() -> None:
    for name in (
        "weight_girr_delta_sensitivities",
        "weight_girr_vega_sensitivities",
        "weight_girr_vega_sensitivity_batch",
    ):
        assert name in girr_weighting.__all__
        assert getattr(weighted_sensitivity, name) is getattr(girr_weighting, name)

    for module, names in (
        (fx_weighting, ("weight_fx_delta_sensitivities", "weight_fx_delta_sensitivity_batch")),
        (
            equity_weighting,
            ("weight_equity_delta_sensitivities", "weight_equity_delta_sensitivity_batch"),
        ),
        (
            commodity_weighting,
            ("weight_commodity_delta_sensitivities", "weight_commodity_delta_sensitivity_batch"),
        ),
        (
            vega_weighting,
            ("weight_non_girr_vega_sensitivities", "weight_non_girr_vega_sensitivity_batch"),
        ),
    ):
        for name in names:
            assert name in module.__all__
            assert getattr(weighted_sensitivity, name) is getattr(module, name)

    assert callable(vega_validation._validate_non_girr_vega_sensitivity)
    assert callable(vega_validation._validate_non_girr_vega_batch_row)
    assert (
        weighted_sensitivity.sort_weighted_sensitivities_deterministic
        is kernel_weighting.sort_weighted_sensitivities_deterministic
    )
    assert (
        weighted_sensitivity.weighted_sensitivity_sort_key
        is kernel_weighting.weighted_sensitivity_sort_key
    )


def test_vega_module_reexports_correlation_stage_surface() -> None:
    for name in (
        "build_non_girr_vega_inter_bucket_correlation_map",
        "build_non_girr_vega_intra_bucket_correlation_matrix",
        "non_girr_vega_intra_bucket_correlation",
    ):
        assert name in vega.__all__
        assert name in vega_correlations.__all__
        assert getattr(vega, name) is getattr(vega_correlations, name)


def test_curvature_module_reexports_correlation_stage_helpers() -> None:
    for name in (
        "_build_curvature_inter_bucket_correlation_map",
        "_build_curvature_intra_bucket_correlation_matrix",
        "_build_vectorized_curvature_intra_bucket_correlation_matrix",
        "_curvature_inter_citation_ids",
        "_curvature_intra_bucket_correlation",
        "_curvature_intra_citation_ids",
    ):
        assert name in curvature_correlations.__all__
        assert getattr(curvature, name) is getattr(curvature_correlations, name)


def test_curvature_module_reexports_factor_stage_helpers() -> None:
    for name in (
        "FX_CURVATURE_SCALAR_1_5_FLAG",
        "_CurvatureFactor",
        "_curvature_factor_key",
        "_curvature_factor_risk_factor",
        "_curvature_factor_qualifier",
        "_required_curvature_shock",
        "_scaled_curvature_shock",
    ):
        assert name in curvature_factors.__all__
        assert getattr(curvature, name) is getattr(curvature_factors, name)


def test_crif_module_reexports_adapter_stage_surface() -> None:
    assert crif.SbmAdapterResult is adapter_crif_models.SbmAdapterResult
    assert crif.SbmAdapterWarning is adapter_crif_models.SbmAdapterWarning
    assert crif.SbmRejectedRow is adapter_crif_models.SbmRejectedRow
    assert crif.adapt_crif_records is adapter_crif_rows.adapt_crif_records
    assert (
        crif.normalize_girr_delta_crif_arrow_table
        is adapter_crif_arrow.normalize_girr_delta_crif_arrow_table
    )
    assert (
        crif.normalize_girr_delta_crif_records
        is adapter_crif_arrow.normalize_girr_delta_crif_records
    )


def test_reference_data_module_reexports_split_stage_surface() -> None:
    assert reference_data.SbmGirrBucketDefinition is reference_types.SbmGirrBucketDefinition
    assert reference_data.SbmFxBucketDefinition is reference_types.SbmFxBucketDefinition
    assert (
        reference_data.SbmCorrelationScenarioDefinition
        is reference_types.SbmCorrelationScenarioDefinition
    )
    assert reference_data.citations_for_profile is reference_profiles.citations_for_profile
    assert reference_data.girr_bucket_definition is girr_reference_data.girr_bucket_definition
    assert reference_data.girr_delta_risk_weight is girr_reference_data.girr_delta_risk_weight
    assert reference_data.fx_delta_risk_weight is fx_reference_data.fx_delta_risk_weight
    assert (
        reference_data.normalise_fx_delta_currency_code
        is fx_reference_data.normalise_fx_delta_currency_code
    )
    assert reference_data.vega_risk_weight is vega_reference_data.vega_risk_weight
    assert reference_data.curvature_risk_weight is curvature_reference_data.curvature_risk_weight
    assert reference_data.profile_reference_payload is reference_payload.profile_reference_payload


def test_hash_assembly_module_backs_compatibility_paths() -> None:
    assert (
        audit._input_hash_for_validated_sensitivities
        is assembly_hashes.input_hash_for_validated_sensitivities
    )
    assert batch.input_hash_for_batch.__module__ == "frtb_sbm.batch"
    assert batch.input_hash_for_sbm_batches.__module__ == "frtb_sbm.batch"
    assert "input_hash_for_sbm_batch" not in batch.__all__
    for name in (
        "input_hash_for_sbm_batch",
        "input_hash_for_sbm_batches",
        "input_hash_for_validated_sensitivities",
        "profile_content_hash_from_parts",
    ):
        assert name in assembly_hashes.__all__


def _public_api_doc() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs/modules/frtb-sbm/PUBLIC_API.md").read_text()
