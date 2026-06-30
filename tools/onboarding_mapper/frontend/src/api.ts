import type {
  ColumnMappingState,
  ExportMappingResponse,
  ImportMappingResult,
  InputTableDetail,
  InputTableSummary,
  SourcePreview,
  ValidationResult,
} from "./types";

const DEFAULT_TIMEOUT_MS = 60_000;

async function request<T>(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { ...init, signal: controller.signal });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Request failed: ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s: ${path}`);
    }
    throw exc;
  } finally {
    clearTimeout(timer);
  }
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

export function suggestMapping(
  payload: Pick<ColumnMappingState, "session_id" | "target_package" | "target_table_id">,
): Promise<ColumnMappingState> {
  const { session_id, target_package, target_table_id } = payload;
  return request("/api/mapping/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id, target_package, target_table_id }),
  });
}

export function importMapping(payload: {
  content: string;
  format?: "yaml" | "toml" | "json" | null;
}): Promise<ImportMappingResult> {
  return request("/api/mapping/import", {
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
