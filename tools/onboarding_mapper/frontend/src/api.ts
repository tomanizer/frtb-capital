import type {
  ColumnMappingState,
  ExportMappingResponse,
  InputTableDetail,
  InputTableSummary,
  SourcePreview,
  ValidationResult,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function listTables(component?: string): Promise<InputTableSummary[]> {
  const query = component ? `?component=${encodeURIComponent(component)}` : "";
  return request(`/api/tables${query}`);
}

export function getTable(packageName: string, tableId: string): Promise<InputTableDetail> {
  return request(`/api/tables/${packageName}/${tableId}`);
}

export async function uploadSource(file: File): Promise<SourcePreview> {
  const query = new URLSearchParams({ filename: file.name });
  return request(`/api/source/upload?${query.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });
}

export function loadSourcePath(path: string): Promise<SourcePreview> {
  return request("/api/source/path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export function loadSourceDuckDb(payload: {
  database_path?: string;
  query: string;
  attach_files?: Record<string, string>;
}): Promise<SourcePreview> {
  return request("/api/source/duckdb", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function suggestMapping(payload: {
  session_id: string;
  target_package: string;
  target_table_id: string;
}): Promise<ColumnMappingState> {
  return request("/api/mapping/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function validateMapping(payload: ColumnMappingState): Promise<ValidationResult> {
  return request("/api/mapping/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function exportMapping(
  payload: ColumnMappingState & {
    format: "yaml" | "toml" | "json";
    source_connector?: "file" | "duckdb" | "path";
    source_format?: "parquet" | "csv" | "arrow";
    source_path?: string;
    lineage_source_system?: string;
    lineage_source_file?: string;
  },
): Promise<ExportMappingResponse> {
  return request("/api/mapping/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
