import type { IRREvidence, IRRStoryInput } from "./irrReview";

export type IRR04Condition = "memory" | "fresh";
export type IRR04Branch = "main" | "negative_control";

export interface IRR04SpanReading {
  span: string;
  literal_reading: string;
  current_interpretation: string;
  changed_from_previous: boolean;
  change_type: "historical" | "relational" | "aesthetic" | "none";
  supporting_evidence_ids: string[];
  unsupported_inference: boolean;
  scene_historical_depth: number;
  relational_depth: number;
  retrospective_depth: number;
  aesthetic_depth: number;
}

export interface IRR04ModelOutput {
  span_readings: IRR04SpanReading[];
  historical_situation_delta: Array<{ text: string; evidence_ids: string[] }>;
  new_questions: Array<{ text: string; evidence_ids: string[] }>;
  aesthetic_observations: Array<{
    span: string;
    operations: string[];
    observation: string;
    evidence_ids: string[];
  }>;
}

export interface IRR04InferenceInput {
  story: IRRStoryInput;
  evidence: IRREvidence[];
  semantic_stage: string;
  driving_question: string;
  round: string;
  branch: IRR04Branch;
  condition: IRR04Condition;
  previous_reading?: IRR04ModelOutput;
}

export interface IRR04ReadingEnvelope {
  inference_input: IRR04InferenceInput;
  input_hash: string;
  model_metadata: Record<string, unknown>;
  output: IRR04ModelOutput;
}

export interface IRR04Round {
  round: number;
  round_label: string;
  semantic_stage: string;
  driving_question: string;
  evidence_bundle: string[];
  evidence_refs: string[];
  gold?: { expected_effect: string; target_spans: string[] };
  memory_reading: IRR04ReadingEnvelope;
  fresh_reading: IRR04ReadingEnvelope;
}

export interface IRR04NegativeControl extends Omit<IRR04Round, "round"> {
  round: string;
  base_round: number;
  branch_role: string;
}

export interface IRR04StoryRecord {
  story_id: string;
  critical_spans: string[];
  rounds: IRR04Round[];
  negative_control: IRR04NegativeControl;
}

export interface IRR04Manifest {
  execution: {
    run_type: "fixture" | "real_model";
    execution_kind: string;
    real_model_run: boolean;
    provider: string;
    model: string;
    run_id: string;
    created_at: string;
    parameters: Record<string, unknown>;
  };
  scope: { story_count: number; story_ids: string[] };
}

export interface IRR04Bundle {
  manifest: IRR04Manifest;
  semanticLadders: {
    records: IRR04StoryRecord[];
  };
  memoryFresh: Record<string, unknown>;
  negativeControls: Record<string, unknown>;
  spanTrajectories: Record<string, unknown>;
  humanReviewTemplate: Record<string, unknown>;
}

let bundlePromise: Promise<IRR04Bundle> | null = null;

function artifactUrl(name: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return `${base}generated/irr0-4/${name}`;
}

async function loadJson<T>(name: string): Promise<T> {
  const response = await fetch(artifactUrl(name), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`IRR0.4 review artifact request failed: ${response.status}`);
  return await response.json() as T;
}

export function loadIRR04ReviewBundle(): Promise<IRR04Bundle> {
  if (!bundlePromise) {
    bundlePromise = Promise.all([
      loadJson<IRR04Manifest>("manifest.json"),
      loadJson<{ records: IRR04StoryRecord[] }>("semantic-ladders.json"),
      loadJson<Record<string, unknown>>("memory-vs-fresh.json"),
      loadJson<Record<string, unknown>>("negative-controls.json"),
      loadJson<Record<string, unknown>>("span-trajectories.json"),
      loadJson<Record<string, unknown>>("human-review-template.json"),
    ]).then(([manifest, semanticLadders, memoryFresh, negativeControls, spanTrajectories, humanReviewTemplate]) => ({
      manifest,
      semanticLadders,
      memoryFresh,
      negativeControls,
      spanTrajectories,
      humanReviewTemplate,
    }));
  }
  return bundlePromise;
}
