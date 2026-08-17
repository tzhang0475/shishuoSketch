export type IRRReviewMode = "text_only" | "all_at_once" | "iterative" | "gold";

export interface IRREvidence {
  evidence_ref: string;
  source: string;
  source_layer: string;
  quote: string;
  locator?: Record<string, unknown>;
  quoted_source?: string;
  modality?: string;
}

export interface IRRStoryInput {
  story_id: string;
  chapter: string;
  ordinal: number;
  text: { original: string; simplified: string };
}

export interface IRRInferenceInput {
  story: IRRStoryInput;
  evidence: IRREvidence[];
  previous_reading?: IRRModelOutput;
}

export interface IRRClaim {
  text: string;
  evidence_refs: string[];
  status?: string;
}

export interface IRRModelOutput {
  historical_reading: {
    era: string | null;
    participant_states: IRRClaim[];
    relationship_states: IRRClaim[];
    prior_events: IRRClaim[];
    later_events: IRRClaim[];
    scene_pressure: IRRClaim[];
    uncertainties: IRRClaim[];
  };
  text_reading: {
    salient_spans: Array<{
      span: string;
      literal_meaning: string;
      contextual_meaning: string | null;
      depth_self_assessment: number;
      evidence_refs: string[];
    }>;
  };
  aesthetic_reading: Array<{
    span: string;
    operations: string[];
    omitted_context: string[];
    interpretation: string | null;
    evidence_refs: string[];
  }>;
  open_questions: Array<{ question: string; evidence_refs: string[] }>;
  new_questions: Array<{ question: string; evidence_refs: string[] }>;
  reading_delta: IRRReadingDelta | null;
}

export interface IRRReadingDelta {
  historical_changes: IRRDeltaItem[];
  newly_salient_spans: IRRDeltaItem[];
  reinterpretations: IRRDeltaItem[];
  newly_understood_omissions: IRRDeltaItem[];
  new_connections: IRRDeltaItem[];
  resolved_questions: IRRDeltaItem[];
  new_questions: IRRDeltaItem[];
}

export interface IRRDeltaItem {
  text: string;
  evidence_refs: string[];
}

export interface IRRModelRecord {
  story_id: string;
  condition: string;
  inference_input?: IRRInferenceInput;
  input_hash?: string;
  output?: IRRModelOutput;
  rounds?: Array<{
    round: number;
    evidence_added: IRREvidence[];
    inference_input: IRRInferenceInput;
    input_hash: string;
    output: IRRModelOutput;
    model_metadata: Record<string, unknown>;
  }>;
}

export interface IRRGainVector {
  G_H: number;
  G_L: number;
  G_A: number;
  G_C: number;
  G_U: number;
  G_D: number;
  MRG: number;
}

export interface IRRScoredRound {
  round: number;
  metrics: Record<string, number>;
  predicted_reading_depth: number;
  gold_reading_depth: number;
  model_gain_vector: IRRGainVector;
  gold_gain_vector: IRRGainVector;
}

export interface IRRComparison {
  scientific_status: string;
  condition_summary: Record<string, Record<string, number>>;
  pairwise: Record<string, { deltas: Record<string, number> }>;
  iterative_analysis: {
    stories: Record<string, {
      predicted_depths: number[];
      gold_depths: number[];
      monotonic_non_decreasing: boolean;
      strict_progression: boolean;
    }>;
    monotonic_stories: string[];
    hard_negative_cases: Array<{
      story_id: string;
      round: number;
      recognized: boolean;
      model_depth_before: number;
      model_depth_after: number;
    }>;
    degradation_cases: Array<Record<string, unknown>>;
  };
  questions: {
    context_improves_over_text_only: boolean;
    iterative_outperforms_all_at_once: boolean;
    hard_negative_recognized: boolean;
    any_degradation: boolean;
    [key: string]: boolean;
  };
}

export interface IRRGoldRound {
  round: number;
  evidence_added: Array<{ evidence_ref: string; expected_role?: string }>;
  historical_reading: Record<string, unknown>;
  text_reading: {
    salient_spans: Array<{
      span: string;
      literal_meaning: string;
      contextual_meaning: string | null;
      depth: number;
      critical?: boolean;
    }>;
  };
  aesthetic_reading: Array<{
    span: string;
    operations: string[];
    omitted_context: string[];
    interpretation: string | null;
  }>;
  open_questions: Array<Record<string, unknown>>;
  gain_vector: IRRGainVector;
}

export interface IRRGoldRecord {
  story_id: string;
  critical_spans: string[];
  rounds: IRRGoldRound[];
}

export interface IRRManifest {
  execution: {
    execution_kind: string;
    real_model_run: boolean;
    provider: string;
    model: string;
    created_at: string;
  };
  scope: { story_count: number; story_ids: string[] };
}

export interface IRRReviewBundle {
  manifest: IRRManifest;
  textOnly: { records: IRRModelRecord[] };
  allAtOnce: { records: IRRModelRecord[] };
  iterative: { records: IRRModelRecord[] };
  comparison: IRRComparison;
  report: { records: Array<Record<string, unknown>> };
}

let bundlePromise: Promise<IRRReviewBundle> | null = null;
let goldPromise: Promise<{ records: IRRGoldRecord[] }> | null = null;

function artifactUrl(name: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/irr0-2/${name}`;
}

async function loadJson<T>(name: string): Promise<T> {
  const response = await fetch(artifactUrl(name), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`IRR0.2 review artifact request failed: ${response.status}`);
  return await response.json() as T;
}

export function loadIRRReviewBundle(): Promise<IRRReviewBundle> {
  if (!bundlePromise) {
    bundlePromise = Promise.all([
      loadJson<IRRManifest>("manifest.json"),
      loadJson<{ records: IRRModelRecord[] }>("text-only.json"),
      loadJson<{ records: IRRModelRecord[] }>("all-at-once.json"),
      loadJson<{ records: IRRModelRecord[] }>("iterative.json"),
      loadJson<IRRComparison>("comparison.json"),
      loadJson<{ records: Array<Record<string, unknown>> }>("per-story-report.json"),
    ]).then(([manifest, textOnly, allAtOnce, iterative, comparison, report]) => ({
      manifest,
      textOnly,
      allAtOnce,
      iterative,
      comparison,
      report,
    }));
  }
  return bundlePromise;
}

export function loadIRRGold(): Promise<{ records: IRRGoldRecord[] }> {
  if (!goldPromise) goldPromise = loadJson<{ records: IRRGoldRecord[] }>("gold.json");
  return goldPromise;
}
