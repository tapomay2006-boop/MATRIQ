export type MatchLevel = "high" | "possible" | "low" | "none";
export type MatchSource = "exact_identifier" | "siamese" | "retrieval_only" | "none";

export interface SearchHit {
  national_id: string | null;
  material_id: string;
  cpse_code: string;
  company: string;
  legacy_code: string;
  description: string;
  uom: string;
  part_number: string;
  make: string;
  specifications: string;
  category: string;
  qdrant_score: number | null;
  siamese_score: number | null;
  final_score: number;
  match: boolean;
  match_level: MatchLevel;
  match_source: MatchSource;
  matched_by: string[];
  identifier_match: boolean;
  identifier_match_type: string | null;
  identifier_matched_field: string | null;
  identifier_token: string | null;
}

export interface SearchPipelineInfo {
  normalized_query: string;
  identifiers: string[];
  identifier_only: boolean;
  vector_search_ran: boolean;
  embedding_model: string | null;
  embedding_version: string | null;
  embedding_is_fallback: boolean | null;
  embedding_error: string | null;
  vector_store: string;
  store_error: string | null;
  top_k: number;
  final_k: number;
  candidates_retrieved: number;
  identifier_hits: number;
  reranker_applied: boolean;
  reranker_model: string | null;
  reranker_detail: string;
  qdrant_weight: number;
  siamese_weight: number;
  match_threshold: number;
  possible_threshold: number;
  degraded: boolean;
  warnings: string[];
}

export interface SearchResponse {
  query: string;
  results: SearchHit[];
  total_candidates: number;
  best_match_level: MatchLevel;
  message: string;
  pipeline: SearchPipelineInfo;
}
