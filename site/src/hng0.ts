import generatedHng0 from "./generated/hng0-site.json";

export type HngReviewStatus = "candidate" | "accepted" | "rejected" | "uncertain" | "needs_more_evidence";

export interface Hng0Evidence {
  evidence_ref: string;
  source_work: string;
  source_layer: string;
  original_text: string | null;
  normalized_search_text: string;
  locator: Record<string, unknown>;
  source_path: string | null;
  source_sha256: string | null;
  assertion_status: string;
  source_review_status: string;
  provenance_kind: string;
}

export interface Hng0StoryPreview {
  story_id: string;
  chapter_id: string;
  chapter_heading: string;
  story_ordinal: number | null;
  global_ordinal: number | null;
  source_presence: "main_text" | "liu_annotation_only" | "both";
  person_story_link_id: string | null;
  resolution_status: string | null;
  confidence: string | null;
  review_status: string | null;
  research_scope: "published" | "research_only";
  short_excerpt: string;
  evidence_refs: string[];
}

export interface Hng0Relation {
  relation_id: string;
  person_a: string;
  person_b: string;
  person_a_name: string | null;
  person_b_name: string | null;
  relation_type: string;
  direction: { kind: string; from: string; to: string };
  temporal_scope: Record<string, unknown> | null;
  certainty: string;
  evidence_refs: string[];
  extraction_method: string;
  review_status: HngReviewStatus;
  source_review_status: string;
  source_record_id: string;
  source_story_ids: string[];
  label: string | null;
  notes: string | null;
}

export interface Hng0TemporalItem {
  temporal_id: string;
  person_id: string;
  kind: string;
  label: string;
  start_year: number | null;
  end_year: number | null;
  precision: "exact" | "circa" | "before" | "after" | "between" | "reign_period" | "unknown";
  temporal_scope: Record<string, unknown>;
  certainty: string;
  evidence_refs: string[];
  extraction_method: string;
  review_status: HngReviewStatus;
  source_review_status: string;
  source_record_id: string;
  source_story_ids: string[];
  location_role?: string | null;
  story_id?: string;
  anchor_id?: string | null;
}

export interface Hng0PersonNeighborhood {
  person_id: string;
  person: {
    name: { original: string; simplified: string } | null;
    courtesy_name: { original: string; simplified: string } | null;
    aliases: Array<{ surface: { original: string; simplified: string } | null; alias_type: string; status: string | null; evidence_refs: string[] }>;
    title_office_appellations: Array<{ original: string; simplified: string } | null>;
    clan: { clan_id: string | null; name: { original: string; simplified: string } | null; locality: { original: string; simplified: string } | null; review_status: string | null; evidence_refs: string[] } | null;
    native_place: unknown;
    review_status: string | null;
    evidence_refs: string[];
  };
  stories: Hng0StoryPreview[];
  relations: Hng0Relation[];
  temporal_spine: Hng0TemporalItem[];
  nearby_person_ids: string[];
  approximate_temporal_window: { start_year: number | null; end_year: number | null; precision: string };
}

export interface Hng0ReviewOverlay {
  schema: number;
  stage: string;
  canonical_write_back: false;
  relation_decisions: Record<string, { review_status: HngReviewStatus; reviewer_note?: string }>;
  temporal_decisions: Record<string, { review_status: HngReviewStatus; reviewer_note?: string }>;
}

export interface Hng0SiteBundle {
  schema: number;
  stage: string;
  canonical_write_back: false;
  person_labels: Record<string, string>;
  people: Record<string, Hng0PersonNeighborhood>;
  relations: Hng0Relation[];
  temporal_items: Hng0TemporalItem[];
  evidence: Record<string, Hng0Evidence>;
  metrics: Record<string, unknown>;
  review_storage: string;
}

export const HNG0_REVIEW_STORAGE_KEY = "shishuoSketch.hng0-review";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function validBundle(value: unknown): value is Hng0SiteBundle {
  return isRecord(value)
    && value.schema === 1
    && value.stage === "hng0-frontend-review"
    && value.canonical_write_back === false
    && isRecord(value.people)
    && Array.isArray(value.relations)
    && Array.isArray(value.temporal_items)
    && isRecord(value.evidence);
}

export function loadHng0Site(): Hng0SiteBundle {
  if (!validBundle(generatedHng0)) throw new Error("HNG0 frontend bundle is invalid");
  return generatedHng0 as unknown as Hng0SiteBundle;
}

export function readHng0Review(): Hng0ReviewOverlay | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(HNG0_REVIEW_STORAGE_KEY) ?? "null");
    if (!isRecord(parsed) || parsed.schema !== 1 || parsed.canonical_write_back !== false) return null;
    return parsed as unknown as Hng0ReviewOverlay;
  } catch {
    return null;
  }
}

export function writeHng0Review(review: Hng0ReviewOverlay): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(HNG0_REVIEW_STORAGE_KEY, JSON.stringify(review));
}
