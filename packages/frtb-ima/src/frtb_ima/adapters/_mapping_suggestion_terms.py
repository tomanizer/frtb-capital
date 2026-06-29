"""Static vocabulary for IMA mapping-suggestion heuristics."""

from __future__ import annotations

from collections.abc import Mapping

from frtb_common import TabularLogicalType

FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "apl": ("actual_pnl", "actual_pnl_vector", "actual", "full_reval_pnl"),
    "bucket": ("bucket", "reg_bucket", "risk_bucket"),
    "business_date": ("cob_date", "cob", "as_of_date", "valuation_date", "date"),
    "data_pool_id": ("data_pool", "pool_id"),
    "date_normalization_evidence": ("date_evidence", "normalization_evidence"),
    "desk_id": ("desk", "desk_code", "trading_desk", "trading_desk_id"),
    "effective_date": ("effective_from", "as_of_date", "valid_from"),
    "feed": ("feed", "market_data_feed"),
    "hpl": ("hypothetical_pnl", "hyp_pnl", "hypothetical"),
    "liquidity_horizon": ("lh", "lh_days", "liquidity_horizon_days"),
    "observation_date": ("obs_date", "price_date", "quote_date", "date"),
    "observation_timestamp": ("obs_timestamp", "quote_timestamp", "timestamp"),
    "pnl": ("pnl", "scenario_pnl", "p_l", "profit_loss"),
    "position_id": ("position", "trade_id", "deal_id", "book_position_id"),
    "risk_class": ("risk_class", "risk_type", "asset_class"),
    "risk_factor_name": ("risk_factor", "risk_factor_id", "rf", "rf_name", "factor_name"),
    "rtpl": ("risk_theoretical_pnl", "risk_theoretical", "rt_pnl"),
    "scenario_date": ("scenario_date", "scenario_cob", "as_of_date"),
    "scenario_id": ("scenario", "scenario_name", "scenario_key"),
    "scenario_set": ("set", "set_type", "scenario_type"),
    "source": ("source", "source_system", "vendor"),
    "source_row_id": ("row_id", "source_id", "record_id", "line_id", "source_row"),
    "var_975": ("var97_5", "var_97_5", "var_975", "var_97p5"),
    "var_99": ("var99", "var_99", "var_990"),
    "vendor_audit_evidence_id": ("audit_evidence_id", "evidence_id"),
    "vendor_id": ("vendor", "vendor_code", "vendor_source"),
    "venue": ("venue", "trading_venue"),
    "verifiability_reason": ("verifiable_reason", "reason"),
    "verifiable": ("verifiable", "is_verifiable", "modellable"),
}

GENERIC_MATCH_TOKENS = frozenset({"date", "id", "name", "row", "set", "source", "type"})

SUPPORTED_SOURCE_TYPES: Mapping[TabularLogicalType, frozenset[str]] = {
    TabularLogicalType.BOOLEAN: frozenset({"boolean"}),
    TabularLogicalType.DATE: frozenset({"date", "timestamp"}),
    TabularLogicalType.FLOAT: frozenset({"float", "integer"}),
    TabularLogicalType.INTEGER: frozenset({"integer"}),
    TabularLogicalType.STRING: frozenset({"string", "integer", "float", "boolean", "date"}),
    TabularLogicalType.TIMESTAMP: frozenset({"timestamp", "date"}),
}
