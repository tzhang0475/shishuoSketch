export type AssertionStatus = "attested" | "reported" | "inferred" | "unknown";
export type ReviewStatus = "candidate" | "reviewed" | "rejected" | "todo";

export interface Person {
  id: string;
  canonical_name: string;
  aliases: Array<{
    surface: string;
    alias_type: string;
    resolution_mode: "exact" | "contextual" | "ambiguous";
    evidence_ids: string[];
    review_status: ReviewStatus;
  }>;
  story_ids: string[];
  evidence_ids: string[];
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  notes?: string;
}

export interface Story {
  id: string;
  title: string;
  title_source: "source_heading" | "project_label" | "candidate";
  text: string;
  source_entry_id: string;
  source_ids: string[];
  evidence_ids: string[];
  person_ids: string[];
  mention_ids: string[];
  relation_ids: string[];
  era_ids: string[];
  annotations: Array<{ id: string; text: string; source_location: string }>;
  summary: string | null;
  time: TimeRange;
  places: Array<{
    name: string;
    assertion_status: AssertionStatus;
    review_status: ReviewStatus;
    evidence_ids: string[];
  }>;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  notes?: string;
}

export interface Mention {
  id: string;
  story_id: string;
  surface: string;
  section: "main_text" | "liu_annotation";
  person_id: string | null;
  candidate_person_ids: string[];
  alias_type: string;
  resolution_mode: "exact" | "contextual" | "ambiguous";
  confidence: "high" | "medium" | "low" | "unresolved";
  anchor: { text: string; section: "main_text" | "liu_annotation"; offset: number };
  evidence_ids: string[];
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  notes?: string;
}

export interface Relation {
  id: string;
  subject_id: string;
  object_id: string;
  relation_type: string;
  label: string;
  story_ids: string[];
  evidence_ids: string[];
  time: TimeRange;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  notes?: string;
}

export interface Era {
  id: string;
  title: string;
  theme: string;
  period: TimeRange;
  description: string | null;
  story_ids: string[];
  person_ids: string[];
  evidence_ids: string[];
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  notes?: string;
}

export interface Evidence {
  id: string;
  source_id: string;
  evidence_type: "primary_text" | "annotation" | "secondary_reference" | "editorial";
  quote: string;
  locator: {
    artifact_type: "shishuo_entry" | "jinshu_unit";
    entry_id?: string;
    unit_id?: string;
    chapter_id?: string | null;
    artifact_path: string;
    artifact_sha256: string;
    source_normalized_filename?: string | null;
    normalized_line_start?: number | null;
    normalized_line_end?: number | null;
    page_marker_start?: string | null;
    page_marker_end?: string | null;
    annotation_id?: string | null;
    source_provenance: {
      witness_id: string;
      source_path: string;
      source_sha256: string;
    };
  };
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  notes?: string;
}

export interface Source {
  id: string;
  work: string;
  witness_id: string;
  edition: string;
  source_type: string;
  local_path: string | null;
  remote_record: string | null;
  provenance_status: "resolved" | "unresolved" | "external" | "unknown";
  text_authority: string;
  structure_authority: string;
  review_status: ReviewStatus;
  notes?: string;
}

export interface TimeRange {
  status: "exact" | "range" | "approximate" | "unknown";
  label: string | null;
  start_year: number | null;
  end_year: number | null;
}

export interface SiteBundle {
  schema: 1;
  generated_from: string;
  stories: Story[];
  people: Person[];
  mentions: Mention[];
  relations: Relation[];
  eras: Era[];
  evidence: Evidence[];
  sources: Source[];
}
