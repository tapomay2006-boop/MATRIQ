/**
 * TypeScript definitions for AI Service (Phase 1 Extraction & Standardized Boundary)
 * Mirrors backend/ai-service/app/schemas/extraction.py & standardized.py
 */

export interface CanonicalAttributes {
  company?: string | null;
  item_description_raw?: string | null;
  item_code_legacy_ref?: string | null;
  quantity?: number | string | null;
  uom?: string | null;
  part_number_oem_number?: string | null;
  make_brand?: string | null;
  specifications_dimensions?: string | null;
  category?: string | null;
  [key: string]: unknown;
}

export interface ExtractedRecordItem {
  id?: string;
  row_id?: string;
  row_index?: number;
  raw_text?: string;
  input_text?: string;
  predicted?: CanonicalAttributes;
  current?: CanonicalAttributes;
  attributes?: CanonicalAttributes;
  confidence?: number;
  status?: "pending" | "reviewed" | "flagged";
}

export interface ExtractionJobOut {
  job_id: string;
  status: "processing" | "completed" | "failed" | "cancelled" | string;
  processed_rows: number;
  total_rows: number;
  session_id?: string | null;
  source_file?: string | null;
  result?: {
    session_id?: string;
    source_file?: string;
    text_column_used?: string;
    total_records?: number;
    records?: ExtractedRecordItem[];
    [key: string]: unknown;
  } | null;
  error?: string | null;
  error_status?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SessionSummaryOut {
  session_id: string;
  created_at?: string | null;
  source_type: string;
  total_records: number;
  original_filename?: string | null;
  status: "PENDING_REVIEW" | "REVIEWED" | "CHECKED" | string;
  adapter?: string | null;
  job_id?: string | null;
  requested_by?: string | null;
}

export interface SessionOut extends SessionSummaryOut {
  records: ExtractedRecordItem[];
}

export interface AiServiceHealth {
  status: string;
  service: string;
  version?: string;
  environment?: string;
  model?: string;
  device?: string;
  device_name?: string;
  vram_gb?: number;
  extraction_enabled?: boolean;
}

export interface NeighbourOut {
  material_id: string;
  score: number;
}

export interface CheckedRowOut {
  row_number: number;
  status: "NEW" | "ALREADY_EXISTS" | "DUPLICATE_IN_BATCH" | "INVALID" | string;
  description: string;
  material_id?: string | null;
  category?: string;
  embedded_text?: string | null;
  canonical_text?: string | null;
  matched_material_id?: string | null;
  matched_by?: "MATERIAL_ID" | "CANONICAL_HASH" | "VECTOR_SIMILARITY" | string | null;
  similarity?: number | null;
  duplicate_of_row?: number | null;
  reason?: string;
  neighbours?: NeighbourOut[];
  error?: string | null;
}

export interface StandardizedCheckResponse {
  batch_id: string;
  has_new_data: boolean;
  message: string;
  total_rows: number;
  new_rows: number;
  existing_rows: number;
  duplicate_rows_in_batch: number;
  invalid_rows: number;
  new_material: Array<{
    company?: string;
    description?: string;
    legacy_code?: string;
    quantity?: string | number;
    uom?: string;
    part_number?: string;
    make?: string;
    specifications?: string;
    row_number?: number;
    material_id?: string;
    [key: string]: unknown;
  }>;
  rows: CheckedRowOut[];
  existence_threshold: number;
  vector_store: string;
  embedding_provider: string;
  indexed_total?: number | null;

  // Backwards compatibility properties:
  total_checked?: number;
  new_count?: number;
  duplicate_count?: number;
  candidates?: Array<{
    source_item: string;
    matched_id?: string;
    similarity: number;
    decision: "NEW" | "DUPLICATE" | "NEEDS_REVIEW";
  }>;
}

export interface AddedMaterialOut {
  national_id: string;
  material_id: string;
  row_number: number;
  description: string;
  cpse_code: string;
}

export interface StandardizedAddResponse {
  batch_id: string;
  added: number;
  requested: number;
  skipped_existing: number;
  skipped_invalid: number;
  indexed: number;
  materials: AddedMaterialOut[];
  material_ids: string[];
  national_ids: string[];
  message: string;
}

export interface BatchOut {
  id: string;
  status: "CHECKED" | "ADDED" | string;
  source?: string | null;
  source_session_id?: string | null;
  total_rows: number;
  new_rows: number;
  existing_rows: number;
  duplicate_rows: number;
  invalid_rows: number;
  added_rows: number;
  requested_by?: string | null;
  cpse_code?: string | null;
  created_at?: string | null;
}

export interface BatchDetail extends BatchOut {
  new_material: Array<Record<string, unknown>>;
  material_ids: string[];
  rows: CheckedRowOut[];
}

export interface RetrievalStatusOut {
  materials: number;
  indexed: number;
  awaiting_indexing: number;
  store: string;
  store_reachable: boolean;
  store_error?: string | null;
  provider: {
    model_name?: string;
    model_version?: string;
    dimension?: number;
    is_fallback?: boolean;
    detail?: string;
    [key: string]: unknown;
  } | string;
  ann_enabled: boolean;
}
