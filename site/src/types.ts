export type AssertionStatus = "attested" | "reported" | "inferred" | "unknown";
export type ReviewStatus = "candidate" | "reviewed" | "rejected" | "todo";
export type PublicationState = "production_ready" | "preview_ready" | "blocked";

export interface Person {
  id: string;
  scope_role?: "primary" | "supporting";
  scope?: "primary" | "supporting";
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

export type PersonSketchSemanticStatus = "exact" | "contextual" | "ambiguous";

export interface PersonSketchAlias {
  alias_id: string;
  surface: ReadingPair;
  alias_type: string;
  label: ReadingPair;
  resolution_mode: "exact" | "contextual" | "ambiguous" | string;
  semantic_status: PersonSketchSemanticStatus;
  semantic_label: ReadingPair;
  status: string;
  observed_in_shishuo: {
    main_text: boolean;
    liu_annotation: boolean;
  };
  source_layers: Array<"main_text" | "liu_annotation">;
  occurrence_count: number;
  mention_ids: string[];
  evidence_ids: string[];
  display_order: number;
}

export interface PersonSketch {
  person_id: string;
  scope_role: "primary" | "supporting";
  review_status: "candidate" | "reviewed";
  identity: {
    canonical_name: ReadingPair;
    courtesy_name: ReadingPair | null;
    clan: ReadingPair | null;
    identity_roles: ReadingPair[];
    brief_intro: ReadingPair | null;
    evidence_ids: string[];
  };
  profile_evidence_ids: string[];
  aliases: PersonSketchAlias[];
  story_counts: {
    total: number;
    main_text: number;
    liu_annotation_only: number;
    reader_ready: number;
  };
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
  reading: StoryReading;
  chapter_heading?: string;
  chapter_display?: ReadingPair;
  ordinal?: number;
  global_ordinal?: number;
  publication_state: PublicationState;
  publication_note?: string;
  notes?: string;
}

export interface StoryReading {
  entry_id: string;
  status: "reviewed" | "aligned" | "candidate" | "disputed";
  punctuation_record_id: string;
  base_canonical_entry_sha256: string;
  conversion: {
    library: string;
    config: string;
  };
  main_text: {
    original: string;
    simplified: string;
    segments: ReadingSegment[];
  };
  annotations: ReadingAnnotation[];
  mention_projection: {
    suppressed: Array<{
      mention_id?: string;
      kind?: "annotation_marker";
      annotation_id?: string | null;
      reason: string;
      section: "main_text" | "liu_annotation";
    }>;
  };
  labels: Record<
    | "people_section"
    | "resolved_mentions_heading"
    | "alias_hint"
    | "resolved_alias_label"
    | "annotation_label"
    | "evidence_heading"
    | "evidence_intro"
    | "empty_alias"
    | "relation_section"
    | "direct_relation_label"
    | "derived_relation_label"
    | "derived_relation_note"
    | "relation_evidence_toggle"
    | "relation_evidence_heading"
    | "no_direct_relations"
    | "focused_person_label"
    | "back_label",
    ReadingPair
  >;
  person_display: Record<string, {
    name: ReadingPair;
    aliases: Array<{ surface: ReadingPair; alias_type: string }>;
  }>;
  mention_display: Record<string, {
    surface: ReadingPair;
    explanation: ReadingPair;
    alias_type: string;
    resolution_mode: "exact" | "contextual" | "ambiguous" | string;
  }>;
  source_display: Record<string, { work: ReadingPair; edition: ReadingPair }>;
  relation_display: Record<string, {
    label: ReadingPair;
    role_a: ReadingPair | null;
    role_b: ReadingPair | null;
  }>;
  evidence_display: Record<string, ReadingPair>;
  display_overrides: string[];
}

export interface ReadingPair {
  original: string;
  simplified: string;
}

export interface ReadingAnnotation {
  id: string;
  original: string;
  simplified: string;
  segments: ReadingSegment[];
  display_source: "punctuation_record" | "canonical_source";
  punctuation_status: "available" | "unavailable";
  insertion: {
    status: "safe" | "unavailable";
    main_text_offset: number | null;
    source: "processed_entry_structure" | null;
    reason: string;
    label: string;
  };
  evidence_ids?: string[];
}

export type ReadingSegment =
  | {
      type: "text";
      display: ReadingPair;
    }
  | {
      type: "person_mention";
      mention_id: string;
      person_id: string;
      display: ReadingPair;
      annotation_id?: string;
    }
  | {
      type: "annotation_marker";
      annotation_id: string;
      label: ReadingPair;
      display: ReadingPair;
    };

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
  relation_basis: "direct" | "derived";
  relation_subtype?: "parent_child" | "uncle_niece" | "collateral_kinship" | "spouse";
  role_a?: string;
  role_b?: string;
  label: string;
  story_ids: string[];
  source_entry_ids?: string[];
  source_unit_ids?: string[];
  derived_from_relation_ids?: string[];
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

export interface StoryChainPersonReference {
  person_id: string;
  story_ids: string[];
  main_text_story_ids: string[];
  liu_annotation_only_story_ids: string[];
}

export interface StoryChainStoryReference {
  entry_id: string;
  linked_person_ids: string[];
  main_text_person_ids: string[];
  liu_annotation_only_person_ids: string[];
  publication_state: PublicationState;
}

export interface StoryChainIndex {
  schema: 1;
  stage: "sc1-story-chain-frontend";
  generated_from: string[];
  story_ids: string[];
  person_story_refs: StoryChainPersonReference[];
  story_person_refs: StoryChainStoryReference[];
}

export interface ReadingUiLabels {
  person_stories_heading: ReadingPair;
  person_sketch_identity: ReadingPair;
  person_sketch_aliases: ReadingPair;
  person_sketch_stories: ReadingPair;
  person_sketch_relations: ReadingPair;
  person_sketch_courtesy_name: ReadingPair;
  person_sketch_clan: ReadingPair;
  person_sketch_roles: ReadingPair;
  person_sketch_intro: ReadingPair;
  person_sketch_evidence: ReadingPair;
  person_sketch_candidate: ReadingPair;
  person_sketch_reviewed: ReadingPair;
  person_sketch_main_story_count: ReadingPair;
  person_sketch_annotation_story_count: ReadingPair;
  story_people_heading: ReadingPair;
  primary_story_label: ReadingPair;
  annotation_story_label: ReadingPair;
  read_story: ReadingPair;
  reviewed_punctuation: ReadingPair;
  preview_punctuation: ReadingPair;
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
  person_sketches: Record<string, PersonSketch>;
  story_chain?: StoryChainIndex;
  ui?: ReadingUiLabels;
}
