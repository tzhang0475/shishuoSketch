import generatedHng01 from "./generated/hng0-1-site.json";

export type Hng01ReviewStatus = "candidate" | "accepted" | "rejected" | "uncertain" | "needs_more_evidence";

export interface Hng01Evidence {
  evidence_ref: string;
  source_work: string;
  source_layer: string;
  original_text: string;
  model_snippet?: string;
  locator: Record<string, unknown>;
  source_path: string | null;
  source_sha256: string | null;
}

export interface Hng01Relation {
  relation_id: string;
  person_a: string | null;
  person_b: string | null;
  person_a_name: string | null;
  person_b_name: string | null;
  counterpart_surface: string;
  provisional_neighbor_id: string | null;
  resolution_status: "resolved_existing_person" | "unresolved_identity" | "ambiguous_identity";
  resolution_matches: string[];
  relation_type: string;
  direction: { kind: string; from: string | null; to: string | null };
  temporal_scope: Record<string, unknown>;
  certainty: string;
  ambiguity: string;
  historical_verification_open: boolean;
  claim: string;
  claim_variants?: string[];
  conflicts?: Array<{ claim: string; evidence_refs: string[] }>;
  evidence_refs: string[];
  evidence_quotes: Array<{ ref: string; quote: string }>;
  source_works: string[];
  extraction_method: string;
  review_status: Hng01ReviewStatus;
  source_review_status: string;
  origin: "newly_extracted";
  one_hop_only: true;
  temporal_warnings: string[];
}

export interface Hng01TemporalItem {
  temporal_id: string;
  person_id: string;
  subject_surface: string;
  subject_resolution_status: string;
  subject_matches: string[];
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
  extraction_method: string;
  review_status: Hng01ReviewStatus;
  source_review_status: string;
  origin: "newly_extracted";
  temporal_warnings: string[];
}

export interface Hng01SiteBundle {
  schema: number;
  stage: string;
  canonical_write_back: false;
  execution_kind: string;
  run_id: string | null;
  people: Record<string, { new_neighbor_ids?: string[]; newly_extracted_relations: Hng01Relation[]; newly_extracted_temporal_items: Hng01TemporalItem[] }>;
  profiles: Record<string, Record<string, unknown>>;
  relations: Hng01Relation[];
  temporal_items: Hng01TemporalItem[];
  evidence: Record<string, Hng01Evidence>;
  metrics: Record<string, unknown>;
  review_storage: string;
  source_label: string;
}

export interface Hng01ReviewOverlay {
  schema: number;
  stage: string;
  canonical_write_back: false;
  relation_decisions: Record<string, { review_status: Hng01ReviewStatus; reviewer_note?: string }>;
  temporal_decisions: Record<string, { review_status: Hng01ReviewStatus; reviewer_note?: string }>;
}

export const HNG01_REVIEW_STORAGE_KEY = "shishuoSketch.hng0-1-review";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function validBundle(value: unknown): value is Hng01SiteBundle {
  return isRecord(value)
    && value.schema === 1
    && value.stage === "hng0-1-frontend-review"
    && value.canonical_write_back === false
    && typeof value.execution_kind === "string"
    && isRecord(value.people)
    && Array.isArray(value.relations)
    && Array.isArray(value.temporal_items)
    && isRecord(value.evidence);
}

export function loadHng01Site(): Hng01SiteBundle {
  if (!validBundle(generatedHng01)) throw new Error("HNG0.1 frontend bundle is invalid");
  return generatedHng01 as unknown as Hng01SiteBundle;
}

export function readHng01Review(): Hng01ReviewOverlay | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(HNG01_REVIEW_STORAGE_KEY) ?? "null");
    if (!isRecord(parsed) || parsed.schema !== 1 || parsed.canonical_write_back !== false) return null;
    return parsed as unknown as Hng01ReviewOverlay;
  } catch {
    return null;
  }
}

export function writeHng01Review(review: Hng01ReviewOverlay): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(HNG01_REVIEW_STORAGE_KEY, JSON.stringify(review));
}
