export type AssertionStatus = "attested" | "reported" | "inferred" | "unknown";
export type ReviewStatus = "candidate" | "reviewed" | "rejected" | "todo";
export type PublicationState = "production_ready" | "preview_ready" | "blocked";
export type ResolutionStatus = "resolved" | "candidate_for_review" | "unresolved";
export type ResolutionTargetKind = "production_person" | "identity_candidate";

export interface ResolutionTarget {
  target_kind: ResolutionTargetKind;
  person_id?: string;
  candidate_id?: string;
  canonical_name: string;
}

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
  life_glimpse: PersonSketchLifeGlimpse[];
}

export interface PersonSketchLifeGlimpse {
  text: ReadingPair;
  assertion_status: AssertionStatus;
  review_status: "candidate" | "reviewed";
  evidence_ids: string[];
  story_ids: string[];
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
  period_id?: string;
  period_label?: ReadingPair;
  temporal_anchor_id?: string;
  temporal_orientation?: ReadingPair;
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
    resolution_status?: ResolutionStatus;
    target_kind?: ResolutionTargetKind;
    canonical_name?: ReadingPair;
    candidate_names?: ReadingPair[];
  }>;
  source_display: Record<string, { work: ReadingPair; edition: ReadingPair }>;
  relation_display: Record<string, {
    label: ReadingPair;
    role_a: ReadingPair | null;
    role_b: ReadingPair | null;
    scope?: ReadingPair | null;
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
      annotation_ownership_basis?: string;
    }
  | {
      type: "identity_mention";
      mention_id: string;
      resolution_status: "resolved" | "candidate_for_review";
      target_kind: "identity_candidate";
      canonical_name: ReadingPair | null;
      candidate_names: ReadingPair[];
      display: ReadingPair;
      annotation_id?: string;
      annotation_ownership_basis?: string;
    }
  | {
      type: "ruler_mention";
      mention_id: string;
      ruler_id: string;
      era_card_id: string;
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
  resolution_status?: ResolutionStatus;
  resolution_target?: ResolutionTarget | null;
  resolution_candidates?: ResolutionTarget[];
  resolution_review_status?: ReviewStatus;
  resolution_decision_source?: "automatic" | "human_review";
  resolution_evidence_ids?: string[];
  resolution_note?: string;
  display_span?: {
    offset: number;
    end_offset_exclusive: number;
    text: string;
    basis: string;
    status: "safe" | "review_required";
    evidence_ids: string[];
  };
  derived_only?: boolean;
  resolution_method?: string;
  span_decision_id?: string;
  coreference_antecedent_mention_id?: string;
}

export interface Relation {
  id: string;
  subject_id: string;
  object_id: string;
  relation_type: string;
  relation_basis: "direct" | "derived";
  relation_subtype?: "parent_child" | "uncle_niece" | "collateral_kinship" | "spouse" | "friendship" | "service_under" | "political_opposition";
  relation_scope?: "long_term_social" | "institutional_tenure" | "event_bounded" | string;
  scope_event?: string | null;
  source_candidate_id?: string;
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
  person_sketch_life_glimpse: ReadingPair;
  story_people_heading: ReadingPair;
  primary_story_label: ReadingPair;
  annotation_story_label: ReadingPair;
  read_story: ReadingPair;
  reviewed_punctuation: ReadingPair;
  preview_punctuation: ReadingPair;
  random_story: ReadingPair;
  random_person: ReadingPair;
  scene_heading: ReadingPair;
  scene_people_heading: ReadingPair;
  scene_position_heading: ReadingPair;
  scene_background_heading: ReadingPair;
  scene_focus_heading: ReadingPair;
  scene_off_frame_heading: ReadingPair;
  scene_ground_heading: ReadingPair;
  scene_resonance_heading: ReadingPair;
  scene_evidence_heading: ReadingPair;
  scene_unknown: ReadingPair;
  scene_not_materialized: ReadingPair;
}

export type SceneRole = "present" | "discussed" | "referenced_in_context" | "unknown";

export interface SceneDateOrAge {
  status: "exact" | "range" | "approximate" | "unknown";
  label: ReadingPair | null;
  start_year: number | null;
  end_year: number | null;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  evidence_ids: string[];
}

export interface SceneClaim {
  text: ReadingPair;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  evidence_ids: string[];
}

export interface StoryScenePerson {
  person_id: string;
  surface: ReadingPair;
  scene_role: SceneRole;
  scene_role_label: ReadingPair;
  source_layers: Array<"main_text" | "liu_annotation">;
  age: SceneDateOrAge;
  status: SceneClaim | null;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  evidence_ids: string[];
}

export interface StorySceneUnmaterializedPerson {
  surface: ReadingPair;
  scene_role: SceneRole;
  scene_role_label: ReadingPair;
  source_layers: Array<"main_text" | "liu_annotation">;
  reason: ReadingPair;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  evidence_ids: string[];
}

export interface StoryScenePosition {
  person_ids: string[];
  classification: string;
  classification_label: ReadingPair;
  text: ReadingPair;
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  evidence_ids: string[];
}

export interface StorySceneContext {
  story_id: string;
  review_status: ReviewStatus;
  date: SceneDateOrAge;
  places: Array<{
    name: ReadingPair;
    assertion_status: AssertionStatus;
    review_status: ReviewStatus;
    evidence_ids: string[];
  }>;
  people_at_scene: StoryScenePerson[];
  unmaterialized_people: StorySceneUnmaterializedPerson[];
  positional_context: StoryScenePosition[];
  event_background: SceneClaim[];
  narrative_layers: {
    scene_focus: SceneClaim[];
    off_frame_context: SceneClaim[];
    historical_ground: SceneClaim[];
    resonance: SceneClaim[];
  };
  evidence_ids: string[];
  notes: ReadingPair[];
}

export interface RulerIdentity {
  ruler_id: string;
  canonical_title: ReadingPair;
  personal_name: ReadingPair | null;
  polity: string;
  reign_start_year: number | null;
  reign_end_year: number | null;
  reign_period_ids: string[];
  era_year_ids: string[];
  aliases: ReadingPair[];
  evidence_ids: string[];
  source_evidence_ids: string[];
  assertion_status: AssertionStatus;
  review_status: ReviewStatus;
  resolution_basis: string;
}

export interface RulerMention {
  mention_id: string;
  story_id: string;
  section: "main_text" | "liu_annotation";
  annotation_id?: string | null;
  surface: string;
  anchor: { text: string; section: "main_text" | "liu_annotation"; offset: number };
  source_span: Record<string, unknown>;
  candidate_ruler_ids: string[];
  ruler_id: string;
  era_card_id: string;
  resolution_basis: string;
  resolution_status: "resolved";
  story_role_candidate: "appears" | "referenced";
  evidence_ids: string[];
  temporal_evidence_ids: string[];
  era_card_exists: true;
}

export interface HistoricalEventProjection {
  id: string;
  canonical_name: ReadingPair;
  aliases: ReadingPair[];
  start_year_ce: number | null;
  end_year_ce: number | null;
  date_precision: string;
  phase_ids: string[];
  evidence_ids: string[];
  source_evidence_ids: string[];
  review_status: ReviewStatus;
}

export interface EraCardStoryLink {
  story_id: string;
  link_type: "appears" | "referenced" | "reign_context";
  mention_ids: string[];
  evidence_ids: string[];
  source_evidence_ids: string[];
  derivation_basis: string;
}

export interface EraCardPersonIntersection {
  person_id: string;
  story_ids: string[];
  story_count: number;
  derivation_basis: string;
  evidence_ids: string[];
}

export interface EraCard {
  era_card_id: string;
  ruler_id: string;
  title: ReadingPair;
  personal_name: ReadingPair | null;
  polity: string;
  reign_label: ReadingPair;
  reign_start_year: number | null;
  reign_end_year: number | null;
  era_names: Array<{
    name: ReadingPair;
    reign_period_id: string;
    start_year_ce: number | null;
    end_year_ce: number | null;
  }>;
  era_context: {
    text: ReadingPair;
    evidence_ids: string[];
    assertion_status: AssertionStatus;
    review_status: ReviewStatus;
  };
  ruler_story_links: EraCardStoryLink[];
  person_intersections: EraCardPersonIntersection[];
  historical_event_ids: string[];
  evidence_ids: string[];
  source_evidence_ids: string[];
  review_status: ReviewStatus;
  selection_note: string;
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
  ruler_identities: RulerIdentity[];
  era_cards: EraCard[];
  ruler_mentions: RulerMention[];
  historical_events: HistoricalEventProjection[];
  person_sketches: Record<string, PersonSketch>;
  scene_contexts: Record<string, StorySceneContext>;
  story_chain?: StoryChainIndex;
  ui?: ReadingUiLabels;
}
