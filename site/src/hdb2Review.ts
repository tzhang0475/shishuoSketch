export type HDB2ReviewType = "identity" | "candidate_person" | "compositional_kinship" | "office_or_title_holder";
export type HDB2ReviewPriority = "P1" | "P2" | "P3";

export interface HDB2ReviewIndexItem {
  review_id: string;
  priority: HDB2ReviewPriority;
  review_type: HDB2ReviewType;
  story_id: string;
  target_surface: string;
  status: string;
  proposed_label: string | null;
  item_path: string;
}

export interface HDB2ReviewIndex {
  schema: string;
  run_id: string;
  candidate_only: boolean;
  canonical_write_back: boolean;
  item_count: number;
  counts_by_type: Record<string, number>;
  counts_by_priority: Record<string, number>;
  items: HDB2ReviewIndexItem[];
}

export interface HDB2CandidatePerson {
  rank?: number;
  candidate_key: string | null;
  display_name: string;
  person_id: string | null;
  semantic_type?: string | null;
  source?: string | null;
}

export interface HDB2DecisionOption {
  key: string;
  label: string;
  description: string;
}

export interface HDB2MaterializationImpactEntry {
  kind: string;
  count: number;
  label: string;
}

export interface HDB2MaterializationImpact {
  summary: HDB2MaterializationImpactEntry[];
  affected_fact_ids: Record<string, string[]>;
}

export interface HDB2EvidenceItem {
  evidence_ref: string;
  source_work: string | null;
  source_layer: string | null;
  locator: Record<string, unknown>;
  exact_spans: string[];
  excerpt: string;
}

export interface HDB2StructuralEndpoint {
  surface?: string | null;
  label?: string | null;
  person_id?: string | null;
  candidate_key?: string | null;
}

export interface HDB2ReferenceStructure {
  reference_type?: string | null;
  surface_structure?: string | null;
  referent_type?: string | null;
  anchor_person?: HDB2StructuralEndpoint | string | null;
  holder?: HDB2StructuralEndpoint | string | null;
  patron_or_possessor?: HDB2StructuralEndpoint | string | null;
  referent_candidate?: HDB2StructuralEndpoint | string | null;
}

export interface HDB2AffectedFact {
  candidate_id?: string;
  relation_surface?: string;
  relation_class?: string;
  state?: string;
  before_state?: string;
  primary_blocker?: string | null;
  newly_unblocked_candidate_fact?: boolean;
  evidence_ref?: string;
  exact_span?: string;
}

export interface HDB2ReviewItem {
  schema: string;
  review_id: string;
  priority: HDB2ReviewPriority;
  priority_score: number;
  review_type: HDB2ReviewType;
  review_question: string;
  system_summary: string;
  why_review_needed: string;
  decision_options: HDB2DecisionOption[];
  materialization_impact: HDB2MaterializationImpact;
  compositional_context: {
    base_person: {
      surface: string;
      label: string;
      person_id: string | null;
    } | null;
    relation_type: string | null;
    relation_label: string | null;
    relation_surface: string | null;
    referent_candidates: HDB2CandidatePerson[];
  } | null;
  occurrence_id: string;
  identity_observation_id: string;
  story_id: string;
  target_surface: string;
  occurrence_type: string;
  story_context: string;
  relevant_annotation_context: string[];
  reference_structure: HDB2ReferenceStructure | null;
  proposed_identity: {
    status: string;
    label: string | null;
    person_id: string | null;
    candidate_person_id: string | null;
    candidate_key: string | null;
    basis: string | null;
  };
  reviewer_verdict?: string | null;
  reviewer_rejected_top_candidate?: boolean;
  candidate_people: HDB2CandidatePerson[];
  selected_evidence: HDB2EvidenceItem[];
  support_families: string[];
  affected_facts: {
    relations: HDB2AffectedFact[];
    kinship: HDB2AffectedFact[];
    marriage: HDB2AffectedFact[];
    office: HDB2AffectedFact[];
    person_story: Array<Record<string, unknown>>;
  };
  current_state: {
    status: string;
    original_hdb1_status?: string;
    identity_resolution_basis?: string | null;
    cascade_stage?: string | null;
    candidate_set: string[];
    hard_constraint_rejections: string[];
    rescue_attempted: boolean;
    rescue_useful: boolean;
    compositional_referent: Record<string, unknown> | null;
    candidate_only: boolean;
    canonical_write_back: boolean;
  };
}

export interface HDB2HumanDecision {
  review_id: string;
  occurrence_id: string;
  action: "accept_proposed" | "choose_candidate" | "new_person_candidate" | "keep_unresolved" | "evidence_problem";
  candidate_key: string | null;
  note: string;
  updated_at?: string;
}

let indexPromise: Promise<HDB2ReviewIndex> | null = null;
const itemPromises = new Map<string, Promise<HDB2ReviewItem>>();

function artifactUrl(relativePath: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/review/hdb2/${relativePath}`;
}

async function loadJson<T>(relativePath: string): Promise<T> {
  const response = await fetch(artifactUrl(relativePath), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`HDB2 review artifact request failed: ${response.status}`);
  return await response.json() as T;
}

export function loadHDB2ReviewIndex(): Promise<HDB2ReviewIndex> {
  if (!indexPromise) indexPromise = loadJson<HDB2ReviewIndex>("index.json");
  return indexPromise;
}

export function loadHDB2ReviewItem(reviewId: string): Promise<HDB2ReviewItem> {
  const existing = itemPromises.get(reviewId);
  if (existing) return existing;
  const next = loadJson<HDB2ReviewItem>(`items/${encodeURIComponent(reviewId)}.json`);
  itemPromises.set(reviewId, next);
  return next;
}
