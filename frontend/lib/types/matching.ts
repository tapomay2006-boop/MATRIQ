export type ComparisonStatus = "MATCH" | "CONFLICT" | "MISSING" | "SIMILAR";

export interface ComparisonAttribute {
  field: string;
  label: string;
  sourceValue: string;
  candidateValue: string;
  status: ComparisonStatus;
  notes?: string;
}

export interface ReasoningFactor {
  type: "positive" | "neutral" | "warning";
  title: string;
  detail: string;
  scoreImpact?: string;
}

export type ConfidenceTier = "high" | "medium" | "low";

export interface CandidateMatch {
  id: string;
  nationalCode: string;
  itemName: string;
  description: string;
  manufacturer: string;
  partNumber: string;
  category: string;
  uom: string;
  specification: string;
  equipmentCompatibility: string;
  materialType?: string;
  confidence: number; // 0.0 - 1.0 (e.g. 0.964)
  confidenceTier: ConfidenceTier;
  semanticScore: number;
  syntacticScore: number;
  attributeScore: number;
  reasoning: ReasoningFactor[];
  comparisons: ComparisonAttribute[];
  isRecommended?: boolean;
  status: "pending" | "sent_for_review" | "rejected" | "approved";
}

export interface SourceMaterial {
  id: string;
  organization: string;
  organizationName: string;
  legacyCode: string;
  description: string;
  itemName: string;
  partNumber: string;
  manufacturer: string;
  uom: string;
  equipmentCompatibility: string;
  materialType: string;
  category: string;
  specification: string;
  candidates: CandidateMatch[];
}
