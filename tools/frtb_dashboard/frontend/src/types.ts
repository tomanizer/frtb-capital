export type RunSummary = {
  run_id: string;
  label: string;
  calculation_date: string;
  profile_id: string;
  base_currency: string;
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
  breakdown: Record<string, unknown>;
  top_attribution: AttributionRow[];
};

export type SaOverview = {
  total_capital: number;
  jurisdiction_family: string;
  components: SaComponentView[];
};
