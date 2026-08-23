import generatedHng02 from "./generated/hng0-2-site.json";

export type Hng02ReviewStatus = "candidate" | "accepted" | "rejected" | "uncertain" | "needs_more_evidence";

export interface Hng02Evidence {
  evidence_ref: string;
  source_work: string;
  source_layer: string;
  original_text: string;
  model_snippet?: string;
  locator: Record<string, unknown>;
  source_path: string | null;
  source_sha256: string | null;
  source_form?: string;
}

export interface Hng02Relation {
  relation_id: string;
  person_a: string | null;
  person_b: string | null;
  person_a_name: string | null;
  person_b_name: string | null;
  counterpart_surface: string;
  provisional_neighbor_id: string | null;
  provisional_neighbor_label: string | null;
  resolution_status: string;
  relation_type: string;
  normalized_relation_type: string;
  original_relation_type: string;
  semantic_level: "hard_relation" | "documented_interaction" | "interpreted_relation";
  direction: { kind: string; from: string | null; to: string | null };
  temporal_scope: Record<string, unknown>;
  certainty: string;
  ambiguity: string;
  historical_verification_open: boolean;
  claim: string;
  evidence_refs: string[];
  evidence_quotes: Array<{ ref: string; quote: string }>;
  source_works: string[];
  source_forms: string[];
  normalization_reason: string;
  review_status: Hng02ReviewStatus;
  temporal_warnings: string[];
}

export interface Hng02TemporalItem {
  temporal_id: string;
  person_id: string | null;
  provisional_subject_id: string | null;
  subject_label: string | null;
  subject_surface: string;
  subject_resolution_status: string;
  temporal_type: string;
  claim: string;
  temporal_scope: Record<string, unknown>;
  precision: string;
  certainty: string;
  ambiguity: string;
  historical_verification_open: boolean;
  evidence_refs: string[];
  evidence_quotes: Array<{ ref: string; quote: string }>;
  source_works: string[];
  source_forms: string[];
  review_status: Hng02ReviewStatus;
  temporal_warnings: string[];
}

export interface Hng02PersonNeighborhood {
  person_id: string;
  canonical_name: string;
  normalized_relations: Hng02Relation[];
  normalized_temporal_items: Hng02TemporalItem[];
  nearby_person_ids: string[];
}

export interface Hng02SiteBundle {
  schema: number;
  stage: "hng0-2-frontend-review";
  canonical_write_back: false;
  execution_kind: string;
  source_label: string;
  people: Record<string, Hng02PersonNeighborhood>;
  relations: Hng02Relation[];
  temporal_items: Hng02TemporalItem[];
  evidence: Record<string, Hng02Evidence>;
  metrics: Record<string, unknown>;
  review_storage: string;
}

export interface Hng02ReviewOverlay {
  schema: number;
  stage: "hng0-2-local-review";
  canonical_write_back: false;
  relation_decisions: Record<string, { review_status: Hng02ReviewStatus; reviewer_note?: string }>;
  temporal_decisions: Record<string, { review_status: Hng02ReviewStatus; reviewer_note?: string }>;
  identity_decisions: Record<string, { review_status: Hng02ReviewStatus; reviewer_note?: string }>;
}

export const HNG02_REVIEW_STORAGE_KEY = "shishuoSketch.hng0-2-review";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function validBundle(value: unknown): value is Hng02SiteBundle {
  return isRecord(value)
    && value.schema === 1
    && value.stage === "hng0-2-frontend-review"
    && value.canonical_write_back === false
    && typeof value.execution_kind === "string"
    && isRecord(value.people)
    && Array.isArray(value.relations)
    && Array.isArray(value.temporal_items)
    && isRecord(value.evidence);
}

export function loadHng02Site(): Hng02SiteBundle {
  if (!validBundle(generatedHng02)) throw new Error("HNG0.2 frontend bundle is invalid");
  return generatedHng02 as unknown as Hng02SiteBundle;
}

export function readHng02Review(): Hng02ReviewOverlay | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(HNG02_REVIEW_STORAGE_KEY) ?? "null");
    if (!isRecord(parsed) || parsed.schema !== 1 || parsed.canonical_write_back !== false) return null;
    return parsed as unknown as Hng02ReviewOverlay;
  } catch {
    return null;
  }
}

export function writeHng02Review(review: Hng02ReviewOverlay): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(HNG02_REVIEW_STORAGE_KEY, JSON.stringify(review));
}
