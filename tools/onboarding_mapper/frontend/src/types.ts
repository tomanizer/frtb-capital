export type ColumnSpecView = {
  name: string;
  aliases: string[];
  logical_type: string;
  required: boolean;
  null_policy: string;
};

export type InputTableSummary = {
  id: string;
  package: string;
  component: string;
  label: string;
  description: string;
  column_count: number;
  required_column_count: number;
  sbm_risk_class?: string | null;
  sbm_risk_measure?: string | null;
};

export type InputTableDetail = InputTableSummary & {
  columns: ColumnSpecView[];
};

export type SourceColumnPreview = {
  name: string;
  arrow_type: string;
  sample_values: unknown[];
  null_count: number;
  distinct_count?: number | null;
};

export type SourcePreview = {
  session_id: string;
  row_count: number;
  columns: SourceColumnPreview[];
  preview_rows: Record<string, unknown>[];
};

export type ColumnMappingState = {
  session_id: string;
  target_package: string;
  target_table_id: string;
  mapping: Record<string, string | null>;
};

export type MappingDiagnostic = {
  code: string;
  message: string;
  severity: string;
  row_id?: string | null;
  column_name?: string | null;
};

export type ValidationResult = {
  accepted_rows: number;
  rejected_rows: number;
  batch_built: boolean;
  input_table_hash?: string | null;
  diagnostics: MappingDiagnostic[];
  preview_rows: Record<string, unknown>[];
  preview_columns: string[];
};

export type ExportMappingResponse = {
  format: string;
  filename: string;
  content: string;
};

export type ImportMappingResult = {
  target_package: string;
  target_table_id: string;
  mapping: Record<string, string | null>;
  unknown_columns: string[];
};

export type WizardStep = "dataset" | "source" | "mapping" | "validate";
