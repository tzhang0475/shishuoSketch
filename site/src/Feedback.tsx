import { useEffect, useState, type FormEvent } from "react";
import {
  FEEDBACK_CATEGORIES,
  FEEDBACK_CATEGORY_LABELS,
  FEEDBACK_REASON_CODES,
  FEEDBACK_REASON_LABELS,
  FEEDBACK_STATUSES,
  feedbackRepository,
  feedbackReviewEnabled,
  makeFeedbackDraft,
  type FeedbackCategory,
  type FeedbackRecord,
  type FeedbackStatus,
  type FeedbackTargetType,
} from "./feedback";
import type { SiteBundle } from "./types";

const STATUS_LABELS: Record<FeedbackStatus, string> = {
  new: "新提交",
  triaged: "已分流",
  duplicate: "重复",
  accepted: "已接受",
  rejected: "已拒绝",
  needs_review: "待复核",
  resolved: "已解决",
};

export function FeedbackButton({
  data,
  storyId,
  targetType,
  targetId,
  targetTextSnapshot,
  label = "反馈此页",
}: {
  data: SiteBundle;
  storyId: string;
  targetType: FeedbackTargetType;
  targetId?: string;
  targetTextSnapshot?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("other");
  const [reasonCode, setReasonCode] = useState("other");
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function chooseCategory(next: FeedbackCategory): void {
    setCategory(next);
    setReasonCode(FEEDBACK_REASON_CODES[next][0] ?? "other");
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const draft = makeFeedbackDraft(data, {
        story_id: storyId,
        target_type: targetType,
        target_id: targetId,
        category,
        reason_code: reasonCode,
        comment,
        target_text_snapshot: targetTextSnapshot,
      });
      await feedbackRepository().submit(draft);
      setSubmitted(true);
      setComment("");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "反馈暂时无法保存。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="f0-feedback-control">
      <button type="button" className="f0-feedback-trigger" onClick={() => { setOpen((value) => !value); setSubmitted(false); setError(""); }} aria-expanded={open}>
        {label}
      </button>
      {open && (
        <form className="f0-feedback-form" onSubmit={(event) => void submit(event)}>
          <p className="f0-feedback-heading">告诉我们哪里需要看一看</p>
          <label>
            <span>类别</span>
            <select value={category} onChange={(event) => chooseCategory(event.target.value as FeedbackCategory)}>
              {FEEDBACK_CATEGORIES.map((value) => <option value={value} key={value}>{FEEDBACK_CATEGORY_LABELS[value]}</option>)}
            </select>
          </label>
          <label>
            <span>原因</span>
            <select value={reasonCode} onChange={(event) => setReasonCode(event.target.value)}>
              {FEEDBACK_REASON_CODES[category].map((value) => <option value={value} key={value}>{FEEDBACK_REASON_LABELS[value] ?? value}</option>)}
            </select>
          </label>
          <label>
            <span>补充说明（可选）</span>
            <textarea value={comment} maxLength={2000} onChange={(event) => setComment(event.target.value)} rows={3} />
          </label>
          {targetType !== "story" && <p className="f0-feedback-target">反馈对象：{targetType} · {targetId}</p>}
          {error && <p className="f0-feedback-error" role="alert">{error}</p>}
          {submitted && <p className="f0-feedback-success" role="status">已收到，谢谢。</p>}
          <div className="f0-feedback-actions">
            <button type="submit" disabled={saving}>{saving ? "提交中…" : "提交反馈"}</button>
            <button type="button" onClick={() => setOpen(false)}>关闭</button>
          </div>
        </form>
      )}
    </div>
  );
}

export function FeedbackReviewPanel({
  storyId,
  targetType,
  targetId,
}: {
  storyId: string;
  targetType?: FeedbackTargetType;
  targetId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [records, setRecords] = useState<FeedbackRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statuses, setStatuses] = useState<Record<string, FeedbackStatus>>({});
  const [duplicates, setDuplicates] = useState<Record<string, string>>({});

  async function refresh(): Promise<void> {
    setLoading(true);
    setError("");
    try {
      const next = await feedbackRepository().listForTarget(storyId, targetType, targetId);
      setRecords(next);
      setStatuses(Object.fromEntries(next.map((record) => [record.feedback_id, record.status])));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "反馈暂时无法载入。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (open) void refresh();
  }, [open, storyId, targetType, targetId]);

  if (!feedbackReviewEnabled()) return null;

  async function update(record: FeedbackRecord, status: FeedbackStatus, duplicateOf?: string): Promise<void> {
    setError("");
    try {
      await feedbackRepository().updateReview(record.feedback_id, {
        status,
        duplicate_of: duplicateOf || undefined,
      });
      await refresh();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "反馈状态无法更新。");
    }
  }

  return (
    <section className="f0-feedback-review" aria-label="反馈审阅">
      <button type="button" className="f0-feedback-review-toggle" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        反馈审阅{records.length > 0 ? ` · ${records.length}` : ""}
      </button>
      {open && (
        <div className="f0-feedback-review-body">
          {loading && <p className="f0-feedback-muted">反馈载入中…</p>}
          {error && <p className="f0-feedback-error" role="alert">{error}</p>}
          {!loading && records.length === 0 && <p className="f0-feedback-muted">当前故事暂无反馈。</p>}
          {records.map((record) => {
            const otherRecords = records.filter((candidate) => candidate.feedback_id !== record.feedback_id);
            return (
              <article className="f0-feedback-review-item" key={record.feedback_id}>
                <div className="f0-feedback-review-meta">
                  <span>{FEEDBACK_CATEGORY_LABELS[record.category]} · {FEEDBACK_REASON_LABELS[record.reason_code] ?? record.reason_code}</span>
                  <code>{record.feedback_id}</code>
                </div>
                <p>{record.comment || "（未补充说明）"}</p>
                <small>{record.target_type}{record.target_id ? ` · ${record.target_id}` : ""} · {record.created_at}</small>
                {record.target_text_snapshot && <blockquote>{record.target_text_snapshot}</blockquote>}
                <div className="f0-feedback-review-actions">
                  <select
                    value={statuses[record.feedback_id] ?? record.status}
                    onChange={(event) => setStatuses((current) => ({ ...current, [record.feedback_id]: event.target.value as FeedbackStatus }))}
                    aria-label={`反馈状态 ${record.feedback_id}`}
                  >
                    {FEEDBACK_STATUSES.map((status) => <option value={status} key={status}>{STATUS_LABELS[status]}</option>)}
                  </select>
                  <button type="button" onClick={() => void update(record, statuses[record.feedback_id] ?? record.status)}>保存状态</button>
                  {otherRecords.length > 0 && (
                    <>
                      <select
                        value={duplicates[record.feedback_id] ?? ""}
                        onChange={(event) => setDuplicates((current) => ({ ...current, [record.feedback_id]: event.target.value }))}
                        aria-label={`重复对象 ${record.feedback_id}`}
                      >
                        <option value="">选择重复对象</option>
                        {otherRecords.map((candidate) => <option value={candidate.feedback_id} key={candidate.feedback_id}>{candidate.feedback_id}</option>)}
                      </select>
                      <button type="button" onClick={() => void update(record, "duplicate", duplicates[record.feedback_id])} disabled={!duplicates[record.feedback_id]}>标为重复</button>
                    </>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
