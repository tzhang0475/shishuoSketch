import type {
  IRREvidence,
  IRRInferenceInput,
  IRRModelOutput,
} from "./irrReview";

export interface IRR03AffectedSpan {
  span: string;
  before_interpretation: string;
  after_interpretation: string;
  historical_depth: number;
  aesthetic_depth: number;
  unsupported_interpretation: boolean | 0 | 1 | 2;
}

export interface IRR03Transition {
  evidence_ids: string[];
  affected_spans: IRR03AffectedSpan[];
}

export interface IRR03ModelRound {
  round: number;
  evidence_added: IRREvidence[];
  inference_input: IRRInferenceInput;
  input_hash: string;
  model_metadata: Record<string, unknown>;
  output: IRRModelOutput;
  transition: IRR03Transition | null;
}

export interface IRR03ModelRecord {
  story_id: string;
  condition: string;
  inference_input?: IRRInferenceInput;
  input_hash?: string;
  model_metadata?: Record<string, unknown>;
  output?: IRRModelOutput;
  rounds?: IRR03ModelRound[];
}

export interface IRR03Manifest {
  execution: {
    run_type: "fixture" | "real_model";
    real_model_run: boolean;
    provider: string;
    model: string;
    run_id: string;
    created_at: string;
    parameters: Record<string, unknown>;
  };
  scope: { story_count: number; story_ids: string[] };
}

export interface IRR03Bundle {
  manifest: IRR03Manifest;
  textOnly: { records: IRR03ModelRecord[] };
  allAtOnce: { records: IRR03ModelRecord[] };
  iterative: { records: IRR03ModelRecord[] };
  comparison: Record<string, unknown>;
  spanGainReport: Record<string, unknown>;
  questionGainReport: Record<string, unknown>;
}

let bundlePromise: Promise<IRR03Bundle> | null = null;

function artifactUrl(name: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : import.meta.env.BASE_URL + "/";
  return base + "generated/irr0-3/" + name;
}

async function loadJson<T>(name: string): Promise<T> {
  const response = await fetch(artifactUrl(name), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("IRR0.3 review artifact request failed: " + response.status);
  return await response.json() as T;
}

export function loadIRR03ReviewBundle(): Promise<IRR03Bundle> {
  if (!bundlePromise) {
    bundlePromise = Promise.all([
      loadJson<IRR03Manifest>("manifest.json"),
      loadJson<{ records: IRR03ModelRecord[] }>("text-only.json"),
      loadJson<{ records: IRR03ModelRecord[] }>("all-at-once.json"),
      loadJson<{ records: IRR03ModelRecord[] }>("iterative.json"),
      loadJson<Record<string, unknown>>("comparison.json"),
      loadJson<Record<string, unknown>>("span-gain-report.json"),
      loadJson<Record<string, unknown>>("question-gain-report.json"),
    ]).then(([manifest, textOnly, allAtOnce, iterative, comparison, spanGainReport, questionGainReport]) => ({
      manifest,
      textOnly,
      allAtOnce,
      iterative,
      comparison,
      spanGainReport,
      questionGainReport,
    }));
  }
  return bundlePromise;
}
