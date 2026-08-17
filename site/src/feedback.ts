import type { SiteBundle } from "./types";

export const FEEDBACK_CATEGORIES = ["text", "historical_fact", "narrative", "bug", "other"] as const;
export type FeedbackCategory = (typeof FEEDBACK_CATEGORIES)[number];

export const FEEDBACK_STATUSES = ["new", "triaged", "duplicate", "accepted", "rejected", "needs_review", "resolved"] as const;
export type FeedbackStatus = (typeof FEEDBACK_STATUSES)[number];

export type FeedbackTargetType = "story" | "evidence" | "narrative" | "person" | "relation";

export const FEEDBACK_REASON_CODES: Record<FeedbackCategory, readonly string[]> = {
  text: ["incorrect_text", "punctuation", "missing_text", "other"],
  historical_fact: ["inaccurate", "insufficient_evidence", "missing_context", "other"],
  narrative: ["inaccurate", "unnecessary", "overinterpreted", "insufficient_evidence", "missing_context", "other"],
  bug: ["layout", "interaction", "data_loading", "other"],
  other: ["other"],
};

export const FEEDBACK_CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  text: "文字",
  historical_fact: "史实",
  narrative: "叙述",
  bug: "功能问题",
  other: "其他",
};

export const FEEDBACK_REASON_LABELS: Record<string, string> = {
  incorrect_text: "文字不准确",
  punctuation: "句读问题",
  missing_text: "文字缺失",
  inaccurate: "不准确",
  unnecessary: "不必要",
  overinterpreted: "解释过度",
  insufficient_evidence: "依据不足",
  missing_context: "缺少背景",
  layout: "排版问题",
  interaction: "交互问题",
  data_loading: "资料载入问题",
  other: "其他",
};

export interface FeedbackDraft {
  story_id: string;
  target_type: FeedbackTargetType;
  target_id?: string;
  category: FeedbackCategory;
  reason_code: string;
  comment?: string;
  page_url: string;
  frontend_version: string;
  data_version: string;
  target_text_snapshot?: string;
}

export interface FeedbackRecord extends FeedbackDraft {
  schema: "f0-raw-feedback";
  feedback_id: string;
  fingerprint: string;
  status: FeedbackStatus;
  duplicate_of?: string;
  review_note?: string;
  created_at: string;
  reviewed_at?: string;
}

export interface FeedbackReviewUpdate {
  status: FeedbackStatus;
  review_note?: string;
  duplicate_of?: string;
}

export type FeedbackRateLimitHook = (draft: FeedbackDraft) => boolean | Promise<boolean>;

export interface FeedbackRepository {
  submit(draft: FeedbackDraft): Promise<FeedbackRecord>;
  listForTarget(storyId: string, targetType?: FeedbackTargetType, targetId?: string): Promise<FeedbackRecord[]>;
  updateReview(feedbackId: string, update: FeedbackReviewUpdate): Promise<FeedbackRecord>;
}

export const MAX_COMMENT_LENGTH = 2000;

function plainText(value: unknown, limit: number): string {
  return String(value ?? "")
    .replace(/<[^>]*>/gu, " ")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/gu, "")
    .trim()
    .slice(0, limit);
}

function endpointUrl(endpoint: string, suffix = ""): string {
  return `${endpoint.replace(/\/+$/u, "")}${suffix}`;
}

function responseError(response: Response): Error {
  return new Error(`feedback request failed: ${response.status}`);
}

export function feedbackRuntimeMetadata(data: Pick<SiteBundle, "schema" | "generated_from">): {
  frontend_version: string;
  data_version: string;
} {
  return {
    frontend_version: import.meta.env.VITE_FRONTEND_VERSION || import.meta.env.MODE || "unknown",
    data_version: `sc1-schema-${data.schema}:${data.generated_from}`,
  };
}

export function makeFeedbackDraft(
  data: Pick<SiteBundle, "schema" | "generated_from">,
  input: Omit<FeedbackDraft, "page_url" | "frontend_version" | "data_version">,
): FeedbackDraft {
  const metadata = feedbackRuntimeMetadata(data);
  return {
    ...input,
    story_id: plainText(input.story_id, 240),
    target_type: input.target_type,
    target_id: plainText(input.target_id, 240) || undefined,
    category: input.category,
    reason_code: plainText(input.reason_code, 80),
    comment: plainText(input.comment, MAX_COMMENT_LENGTH) || undefined,
    target_text_snapshot: plainText(input.target_text_snapshot, 500) || undefined,
    page_url: typeof window === "undefined" ? "" : window.location.href.slice(0, 2048),
    ...metadata,
  };
}

export class ApiFeedbackRepository implements FeedbackRepository {
  constructor(private readonly endpoint: string) {}

  async submit(draft: FeedbackDraft): Promise<FeedbackRecord> {
    const response = await fetch(endpointUrl(this.endpoint, "/feedback"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(draft),
    });
    if (!response.ok) throw responseError(response);
    return await response.json() as FeedbackRecord;
  }

  async listForTarget(storyId: string, targetType?: FeedbackTargetType, targetId?: string): Promise<FeedbackRecord[]> {
    const params = new URLSearchParams({ story_id: storyId });
    if (targetType) params.set("target_type", targetType);
    if (targetId) params.set("target_id", targetId);
    const response = await fetch(`${endpointUrl(this.endpoint, "/feedback")}?${params.toString()}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw responseError(response);
    return await response.json() as FeedbackRecord[];
  }

  async updateReview(feedbackId: string, update: FeedbackReviewUpdate): Promise<FeedbackRecord> {
    const response = await fetch(endpointUrl(this.endpoint, `/feedback/${encodeURIComponent(feedbackId)}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(update),
    });
    if (!response.ok) throw responseError(response);
    return await response.json() as FeedbackRecord;
  }
}

class MemoryFeedbackRepository implements FeedbackRepository {
  private records: FeedbackRecord[] = [];

  async submit(draft: FeedbackDraft): Promise<FeedbackRecord> {
    const record = createLocalRecord(draft, this.records);
    this.records = [...this.records, record];
    return record;
  }

  async listForTarget(storyId: string, targetType?: FeedbackTargetType, targetId?: string): Promise<FeedbackRecord[]> {
    return this.records.filter((record) => record.story_id === storyId
      && (!targetType || record.target_type === targetType)
      && (!targetId || record.target_id === targetId));
  }

  async updateReview(feedbackId: string, update: FeedbackReviewUpdate): Promise<FeedbackRecord> {
    const index = this.records.findIndex((record) => record.feedback_id === feedbackId);
    if (index < 0) throw new Error("feedback record not found");
    const next = { ...this.records[index], ...update, reviewed_at: new Date().toISOString() };
    this.records = this.records.map((record, rowIndex) => rowIndex === index ? next : record);
    return next;
  }
}

const LOCAL_STORAGE_KEY = "shishuoSketch.feedback.raw.v1";

function localFingerprint(draft: FeedbackDraft): string {
  const basis = [draft.story_id, draft.target_type, draft.target_id ?? "", draft.category, draft.reason_code, draft.comment ?? "", draft.target_text_snapshot ?? ""].join("\u001f");
  let hash = 2166136261;
  for (let index = 0; index < basis.length; index += 1) {
    hash ^= basis.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `fnv1a-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function createLocalRecord(draft: FeedbackDraft, existing: FeedbackRecord[]): FeedbackRecord {
  const fingerprint = localFingerprint(draft);
  const duplicate = existing.find((record) => record.fingerprint === fingerprint && !["rejected", "duplicate"].includes(record.status));
  const cryptoId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return {
    schema: "f0-raw-feedback",
    feedback_id: `feedback-${cryptoId}`,
    ...draft,
    fingerprint,
    status: duplicate ? "duplicate" : "new",
    ...(duplicate ? { duplicate_of: duplicate.feedback_id } : {}),
    created_at: new Date().toISOString(),
  };
}

class LocalStorageFeedbackRepository implements FeedbackRepository {
  constructor(
    private readonly storage: Storage,
    private readonly rateLimitHook: FeedbackRateLimitHook = () => true,
  ) {}

  private load(): FeedbackRecord[] {
    const raw = this.storage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) return [];
    try {
      const value = JSON.parse(raw) as unknown;
      return Array.isArray(value) ? value as FeedbackRecord[] : [];
    } catch {
      return [];
    }
  }

  private save(records: FeedbackRecord[]): void {
    this.storage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(records));
  }

  async submit(draft: FeedbackDraft): Promise<FeedbackRecord> {
    if (!(await this.rateLimitHook(draft))) throw new Error("feedback rate limit reached");
    const records = this.load();
    const record = createLocalRecord(draft, records);
    this.save([...records, record]);
    return record;
  }

  async listForTarget(storyId: string, targetType?: FeedbackTargetType, targetId?: string): Promise<FeedbackRecord[]> {
    return this.load().filter((record) => record.story_id === storyId
      && (!targetType || record.target_type === targetType)
      && (!targetId || record.target_id === targetId));
  }

  async updateReview(feedbackId: string, update: FeedbackReviewUpdate): Promise<FeedbackRecord> {
    const records = this.load();
    const index = records.findIndex((record) => record.feedback_id === feedbackId);
    if (index < 0) throw new Error("feedback record not found");
    if (update.duplicate_of === feedbackId) throw new Error("feedback cannot duplicate itself");
    if (update.duplicate_of && !records.some((record) => record.feedback_id === update.duplicate_of)) {
      throw new Error("duplicate target not found");
    }
    const next = { ...records[index], ...update, reviewed_at: new Date().toISOString() };
    const updated = records.map((record, rowIndex) => rowIndex === index ? next : record);
    this.save(updated);
    return next;
  }
}

let defaultRepository: FeedbackRepository | null = null;

export function createFeedbackRepository(): FeedbackRepository {
  const endpoint = import.meta.env.VITE_FEEDBACK_ENDPOINT;
  if (endpoint) return new ApiFeedbackRepository(endpoint);
  if (typeof window !== "undefined" && window.localStorage) return new LocalStorageFeedbackRepository(window.localStorage);
  return new MemoryFeedbackRepository();
}

export function feedbackRepository(): FeedbackRepository {
  defaultRepository ??= createFeedbackRepository();
  return defaultRepository;
}

export function feedbackReviewEnabled(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_FEEDBACK_REVIEW === "1";
}
