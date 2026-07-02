export type RunSummary = {
  run_id: string;
  label: string;
  calculation_date: string;
  profile_id: string;
  base_currency: string;
  source: string;
  jurisdiction_family?: string | null;
  components: string[];
  prototype: boolean;
  input_hash?: string | null;
};

export type CapitalNode = {
  node_id: string;
  parent_id: string | null;
  label: string;
  node_type: string;
  component: string;
  amount: number | null;
  currency: string;
  child_ids: string[];
};

export type RunOverview = {
  run: RunSummary;
  ima_total: number | null;
  sa_total: number | null;
  cva_total: number | null;
  output_floor_total: number | null;
  binding_total: number | null;
  binding_side: string | null;
  suite_total: number | null;
  currency: string;
  nodes: CapitalNode[];
};

export type AttributionRow = {
  contribution_id: string;
  component: string;
  category: string;
  source_level: string;
  source_id: string;
  method: string;
  amount: number | null;
  contribution: number | null;
  reconciliation_status: string;
  reason: string;
};

export type Measure = { name: string; value: unknown; unit?: string | null };

export type NodeDetail = {
  node: CapitalNode;
  measures: Measure[];
  attributions: AttributionRow[];
};

export type ImaDeskView = {
  desk_id: string;
  regime: string;
  eligibility: string;
  summary: Record<string, unknown>;
  imcc: Record<string, unknown>;
  ses_nmrf: Record<string, unknown>;
  pla: Record<string, unknown>;
  backtesting: Record<string, unknown>;
  attributions: AttributionRow[];
};

export type SaComponentView = {
  component: string;
  total_capital: number;
  profile_id: string;
  input_hash?: string | null;
  line_count?: number | null;
  breakdown: Record<string, unknown>;
  top_attribution: AttributionRow[];
};

export type SaOverview = {
  total_capital: number;
  jurisdiction_family: string;
  components: SaComponentView[];
};

export type DimensionNode = {
  node_id: string;
  parent_id: string | null;
  label: string;
  dimension: string;
  level: number;
  filter: Record<string, string>;
  components: string[];
  child_ids: string[];
};

export type MetadataView = {
  run_id: string;
  source: string;
  data_state: string;
  dimensions: DimensionNode[];
  reporting_dates: string[];
  baseline_dates: string[];
  currencies: string[];
};

export type GridColumn = {
  key: string;
  label: string;
  kind: "number" | "percent" | "signed" | "decimal" | "text" | string;
};

export type GridRow = {
  row_id: string;
  parent_id: string | null;
  label: string;
  framework: "SA" | "IMA" | "CVA" | string;
  component: string;
  row_type: string;
  level: number;
  group_path: string[];
  currency: string;
  capital: number | null;
  delta: number | null;
  vega: number | null;
  curvature: number | null;
  base_rho: number | null;
  high_rho: number | null;
  low_rho: number | null;
  selected_scenario: string | null;
  net_jtd: number | null;
  gross_jtd: number | null;
  lgd: number | null;
  imcc: number | null;
  ses: number | null;
  multiplier: number | null;
  pla_zone: string | null;
  backtest_zone: string | null;
  pct_parent: number | null;
  delta_vs_baseline: number | null;
  status: string;
  no_data_reason: string | null;
  filter: Record<string, string>;
};

export type GridView = {
  run_id: string;
  source: string;
  framework: string;
  grouping: string;
  scenario: string;
  columns: GridColumn[];
  rows: GridRow[];
  row_count: number;
  data_state: string;
};

export type AuditRow = {
  row_id: string;
  source_system: string;
  source_id: string;
  desk_id: string | null;
  book_id: string | null;
  legal_entity: string | null;
  risk_class: string | null;
  bucket: string | null;
  metric: string;
  value: number | null;
  currency: string | null;
  calculation_timestamp: string | null;
  status: string;
  provenance: string;
};

export type InspectorTab = {
  key: string;
  label: string;
  enabled: boolean;
  badge?: string | null;
};

export type Diagnostic = {
  code: string;
  severity: string;
  message: string;
};

export type InspectorView = {
  row_id: string;
  label: string;
  framework: string;
  component: string;
  reconciliation: {
    coverage: number;
    rows_needing_review: number;
    status: string;
  };
  tabs: InspectorTab[];
  attribution: AttributionRow[];
  audit_rows: AuditRow[];
  diagnostics: Diagnostic[];
  extras: Record<string, unknown>;
};
