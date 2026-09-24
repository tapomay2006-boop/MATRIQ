/**
 * Domain types for SIH 2026 Unified Material Intelligence Platform (Phase 1).
 * Domain types for SIH 2026 Unified Material Intelligence Platform.
 */

export interface IngestionErrorItem {
  row: number;
  legacy_code?: string | null;
  reason: string;
}

export interface MaterialIngestionResponse {
  ingestion_id: string;
  filename: string;
  total_records: number;
  accepted_records: number;
  rejected_records: number;
  duplicate_records: number;
  errors: IngestionErrorItem[];
}

export interface MaterialRecord {
  id: string;
  organization: string;
  legacy_code: string;
  description: string;
  uom?: string | null;
  item_name?: string | null;
  part_number?: string | null;
  manufacturer?: string | null;
  equipment_compatibility?: string | null;
  material_type?: string | null;
  category?: string | null;
  specification?: string | null;
  national_id?: string | null;
  status?: string | null;
  source_file?: string | null;
  source_row?: number | null;
  probability_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedMaterialsResponse {
  items: MaterialRecord[];
  total: number;
  limit: number;
  offset: number;
  total_pages?: number;
  page?: number;
  page_size?: number;
}

export interface MaterialAttribute {
  name: string;
  value: string | number | boolean;
  unit?: string | null;
  confidence?: number | null;
}

export interface MaterialItem {
  id: string;
  itemCode: string;
  description: string;
  organizationId?: string | null;
  organizationName?: string | null;
  category?: string | null;
  attributes: MaterialAttribute[];
  createdAt?: string;
  updatedAt?: string;
}

export interface EquivalentMatch {
  id: string;
  sourceItemId: string;
  targetItemId: string;
  sourceItem?: MaterialItem;
  targetItem?: MaterialItem;
  similarityScore: number;
  matchStatus: "pending" | "verified" | "rejected";
  matchedAttributes: string[];
  rationale?: string | null;
  confidence: number;
}

export interface VerificationReview {
  id: string;
  matchId: string;
  reviewerId: string;
  reviewerName?: string;
  decision: "approved" | "rejected" | "modified";
  comments?: string | null;
  timestamp: string;
}

export interface CPSEOrganization {
  id: string;
  name: string;
  code: string;
  sector?: string;
  catalogCount?: number;
}

export interface MaterialQualityStats {
  total_materials: number;
  organizations: number;
  missing_uom: number;
  missing_manufacturer: number;
  missing_part_number: number;
  missing_category: number;
  assigned_count?: number;
  unassigned_count?: number;
}

