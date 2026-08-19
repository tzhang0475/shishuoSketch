import { useEffect, useMemo, useState } from "react";
import {
  loadIRRGold,
  loadIRRReviewBundle,
  type IRRClaim,
  type IRRComparison,
  type IRRDeltaItem,
  type IRREvidence,
  type IRRGoldRecord,
  type IRRGoldRound,
  type IRRGainVector,
  type IRRModelOutput,
  type IRRModelRecord,
  type IRRReviewBundle,
  type IRRReviewMode,
  type IRRReadingDelta,
  type IRRScoredRound,
} from "./irrReview";
import {
  loadIRR03ReviewBundle,
  type IRR03AffectedSpan,
  type IRR03Bundle,
  type IRR03ModelRound,
} from "./irr03Review";
import { IRR04SemanticLadder } from "./IRR04SemanticLadder";

const PILOT_STORIES = [
  "27-jiajue-008",
  "06-yaliang-017",
  "09-pinzao-017",
  "19-xianyuan-026",
  "05-fangzheng-032",
];
const IRR04_PILOT_STORIES = ["27-jiajue-008", "09-pinzao-017", "06-yaliang-017"];
const REVIEW_STORAGE_KEY = "shishuoSketch.irr0-2-blind-review";
const REVIEW_OPTIONS = ["明显深化", "轻微深化", "无明显变化", "变差"] as const;
type ReviewChoice = typeof REVIEW_OPTIONS[number];

type SpanContinueChoice = "yes" | "no" | null;
type SpanStopReason =
  | "unresolved_high_value_question"
  | "more_context_may_change_span"
  | "saturated"
  | "new_evidence_low_value"
  | "unsupported_drift"
  | null;

interface IRR03HumanSpanReview {
  span: string;
  before_interpretation: string;
  after_interpretation: string;
  interpretation_depth: number;
  unsupported_interpretation: number;
  aesthetic_dimensions: {
    salience: number;
    compression: number;
    omission: number;
    selection: number;
  };
  evidence_refs: string[];
  notes?: string;
}

interface IRR03LocalReviewRecord {
  story_id: string;
  round: number;
  evidence_ids: string[];
  selected_spans: string[];
  no_effect: boolean;
  custom_span?: string;
  span_reviews: IRR03HumanSpanReview[];
  continue_reading: SpanContinueChoice;
  stop_reason: SpanStopReason;
}

function recordFor(records: IRRModelRecord[], storyId: string): IRRModelRecord | undefined {
  return records.find((record) => record.story_id === storyId);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function asClaims(value: unknown): IRRClaim[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const current = row as Record<string, unknown>;
    const text = current.text ?? current.state ?? current.description ?? current.question;
    if (typeof text !== "string" || !text) return [];
    return [{
      text,
      evidence_refs: Array.isArray(current.evidence_refs) ? current.evidence_refs.map(String) : [],
      status: typeof current.status === "string" ? current.status : undefined,
    }];
  });
}

function claimText(claim: IRRClaim): string {
  return claim.text;
}

function evidenceLabel(refs: string[]): string {
  return refs.length > 0 ? `依据 ${refs.join("、")}` : "原文输入";
}

function ModelReading({ output }: { output: IRRModelOutput }) {
  const history = output.historical_reading;
  const groups: Array<[string, IRRClaim[]]> = [
    ["在场与人物", history.participant_states],
    ["关系", history.relationship_states],
    ["前情", history.prior_events],
    ["后续", history.later_events],
    ["场景压力", history.scene_pressure],
    ["不确定", history.uncertainties],
  ];
  return (
    <div className="irr0-model-reading">
      <section className="irr0-reading-block">
        <p className="irr0-label">历史理解</p>
        {history.era && <p className="irr0-era-line">{history.era}</p>}
        {groups.map(([label, claims]) => claims.length > 0 && (
          <div className="irr0-claim-group" key={label}>
            <p className="irr0-sublabel">{label}</p>
            <ul>
              {claims.map((claim, index) => (
                <li key={`${label}-${index}`}>
                  {claimText(claim)} <small>{evidenceLabel(claim.evidence_refs)}</small>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="irr0-reading-block">
        <p className="irr0-label">语言焦点</p>
        <div className="irr0-span-list">
          {output.text_reading.salient_spans.map((span, index) => (
            <article className="irr0-span-card" key={`${span.span}-${index}`}>
              <p className="irr0-span-text">{span.span}</p>
              <p>{span.literal_meaning}</p>
              {span.contextual_meaning && <p className="irr0-muted">{span.contextual_meaning}</p>}
              <small>自评深度 {span.depth_self_assessment} · {evidenceLabel(span.evidence_refs)}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="irr0-reading-block">
        <p className="irr0-label">审美阅读</p>
        {output.aesthetic_reading.map((item, index) => (
          <article className="irr0-aesthetic-item" key={`${item.span}-${index}`}>
            <p><strong>{item.span}</strong> · {item.operations.join("、") || "未指定操作"}</p>
            {item.omitted_context.length > 0 && <p className="irr0-muted">省略：{item.omitted_context.join("；")}</p>}
            {item.interpretation && <p>{item.interpretation}</p>}
            <small>{evidenceLabel(item.evidence_refs)}</small>
          </article>
        ))}
      </section>

      <section className="irr0-reading-block">
        <p className="irr0-label">开放问题</p>
        <ul>
          {output.open_questions.map((item, index) => (
            <li key={`${item.question}-${index}`}>{item.question} <small>{evidenceLabel(item.evidence_refs)}</small></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function GoldReading({ round }: { round: IRRGoldRound }) {
  const historical = asRecord(round.historical_reading);
  const era = asRecord(historical.era);
  const groups: Array<[string, IRRClaim[]]> = [
    ["人物", asClaims(historical.participant_states)],
    ["关系", asClaims(historical.relationship_states)],
    ["前情", asClaims(historical.prior_events)],
    ["后续", asClaims(historical.later_events)],
    ["场景压力", asClaims(historical.scene_pressure)],
    ["不确定", asClaims(historical.uncertainties)],
  ];
  return (
    <div className="irr0-gold-reading">
      <section className="irr0-reading-block">
        <p className="irr0-label">Gold 历史理解</p>
        {typeof era.label === "string" && <p className="irr0-era-line">{era.label}</p>}
        {groups.map(([label, claims]) => claims.length > 0 && (
          <div className="irr0-claim-group" key={label}>
            <p className="irr0-sublabel">{label}</p>
            <ul>{claims.map((claim, index) => <li key={`${label}-${index}`}>{claimText(claim)} <small>{evidenceLabel(claim.evidence_refs)}</small></li>)}</ul>
          </div>
        ))}
      </section>
      <section className="irr0-reading-block">
        <p className="irr0-label">Gold 关键跨度</p>
        <div className="irr0-span-list">
          {round.text_reading.salient_spans.map((span, index) => (
            <article className="irr0-span-card" key={`${span.span}-${index}`}>
              <p className="irr0-span-text">{span.span}</p>
              <p>{span.literal_meaning}</p>
              {span.contextual_meaning && <p className="irr0-muted">{span.contextual_meaning}</p>}
              <small>目标深度 {span.depth} · {span.critical ? "关键" : "补充"}</small>
            </article>
          ))}
        </div>
      </section>
      <section className="irr0-reading-block">
        <p className="irr0-label">Gold 审美操作</p>
        {round.aesthetic_reading.map((item, index) => <p key={`${item.span}-${index}`}><strong>{item.span}</strong> · {item.operations.join("、")}</p>)}
      </section>
    </div>
  );
}

function EvidenceList({ evidence, title = "本轮新增史料" }: { evidence: IRREvidence[]; title?: string }) {
  if (evidence.length === 0) return <p className="irr0-muted">本轮没有新增史料。</p>;
  return (
    <section className="irr0-evidence-section">
      <p className="irr0-label">{title}</p>
      {evidence.map((item) => (
        <details className="irr0-evidence" key={item.evidence_ref}>
          <summary>{item.source_layer} · {item.source} · {item.evidence_ref}</summary>
          <blockquote>{item.quote}</blockquote>
          {item.quoted_source && <p className="irr0-muted">引自：{item.quoted_source}</p>}
          {item.locator && <small>{Object.entries(item.locator).map(([key, value]) => `${key}=${String(value)}`).join(" · ")}</small>}
        </details>
      ))}
    </section>
  );
}

function GainVector({
  vector,
  label,
  hidden,
}: {
  vector: IRRGainVector | undefined;
  label: string;
  hidden?: boolean;
}) {
  if (!vector || hidden) return null;
  const keys: Array<keyof IRRGainVector> = ["G_H", "G_L", "G_A", "G_C", "G_U", "G_D"];
  return (
    <div className="irr0-gain-vector">
      <p className="irr0-sublabel">{label}</p>
      <div className="irr0-gain-grid">
        {keys.map((key) => (
          <div className="irr0-gain-row" key={key}>
            <span>{key}</span>
            <span className="irr0-gain-track"><span style={{ width: `${Math.min(1, Math.max(0, vector[key])) * 100}%` }} /></span>
            <strong>{vector[key].toFixed(3)}</strong>
          </div>
        ))}
      </div>
      <p className="irr0-mrg">MRG = {vector.MRG.toFixed(3)} <small>实验诊断值</small></p>
    </div>
  );
}

function Delta({ output }: { output: IRRModelOutput }) {
  if (!output.reading_delta) return null;
  const delta = output.reading_delta;
  const groups: Array<[keyof IRRReadingDelta, IRRDeltaItem[]]> = [
    ["historical_changes", delta.historical_changes],
    ["newly_salient_spans", delta.newly_salient_spans],
    ["reinterpretations", delta.reinterpretations],
    ["newly_understood_omissions", delta.newly_understood_omissions],
    ["new_connections", delta.new_connections],
    ["resolved_questions", delta.resolved_questions],
    ["new_questions", delta.new_questions],
  ];
  const rows = groups.flatMap(([key, items]) => items.map((item) => ({ key, item })));
  return (
    <section className="irr0-delta">
      <p className="irr0-label">Reading delta</p>
      {rows.length === 0 && <p className="irr0-muted">本轮没有结构化变化。</p>}
      {rows.map(({ key, item }, index) => <p key={`${key}-${index}`}><strong>{key}</strong>：{item.text} <small>{evidenceLabel(item.evidence_refs)}</small></p>)}
    </section>
  );
}

function scoredIterativeRound(bundle: IRRReviewBundle, storyId: string, round: number): IRRScoredRound | undefined {
  const row = bundle.report.records.find((candidate) => candidate.story_id === storyId);
  if (!row) return undefined;
  const conditions = asRecord(row.conditions);
  const iterative = asRecord(conditions.iterative);
  const rounds = iterative.rounds;
  if (!Array.isArray(rounds)) return undefined;
  return rounds.find((candidate): candidate is IRRScoredRound => asRecord(candidate).round === round) as IRRScoredRound | undefined;
}

function IterativeRounds({
  bundle,
  storyId,
  record,
  blind,
}: {
  bundle: IRRReviewBundle;
  storyId: string;
  record: IRRModelRecord;
  blind: boolean;
}) {
  const rounds = record.rounds ?? [];
  return (
    <div className="irr0-rounds">
      {rounds.map((round, index) => {
        const scored = scoredIterativeRound(bundle, storyId, round.round);
        const modelGain = scored?.model_gain_vector;
        const goldGain = scored?.gold_gain_vector;
        return (
          <section className="irr0-round" key={round.round}>
            <div className="irr0-round-heading">
              <h3>Round {round.round}</h3>
              {index > 0 && <span>↓ 证据加入后重读</span>}
            </div>
            {round.round > 0 && <EvidenceList evidence={round.evidence_added} />}
            <div className="irr0-model-tag">模型理解</div>
            <ModelReading output={round.output} />
            <Delta output={round.output} />
            <div className="irr0-depth-line">
              Depth: {scored?.predicted_reading_depth ?? "—"}{scored ? ` → Gold ${scored.gold_reading_depth}` : ""}
            </div>
            <GainVector vector={modelGain} label="模型 gain" />
            <GainVector vector={goldGain} label="Gold gain" hidden={blind} />
          </section>
        );
      })}
    </div>
  );
}

function GoldRounds({ record }: { record: IRRGoldRecord }) {
  return (
    <div className="irr0-rounds irr0-gold-rounds">
      {record.rounds.map((round) => (
        <section className="irr0-round" key={round.round}>
          <div className="irr0-round-heading"><h3>Gold Round {round.round}</h3></div>
          <GoldReading round={round} />
        </section>
      ))}
    </div>
  );
}

function spanReviewKey(storyId: string, round: number): string {
  return storyId + ":R" + String(round);
}

function emptySpanReview(round: IRR03ModelRound, storyId: string): IRR03LocalReviewRecord {
  return {
    story_id: storyId,
    round: round.round,
    evidence_ids: round.transition?.evidence_ids ?? [],
    selected_spans: [],
    no_effect: false,
    span_reviews: [],
    continue_reading: null,
    stop_reason: null,
  };
}

function spanOptions(round: IRR03ModelRound, storyText: string): string[] {
  const modelSpans = [
    ...(round.transition?.affected_spans ?? []).map((item) => item.span),
    ...round.output.text_reading.salient_spans.map((item) => item.span),
  ];
  const storyClauses = storyText
    .split(/[。！？；]/u)
    .map((item) => item.trim())
    .filter(Boolean);
  return [...new Set([...modelSpans, ...storyClauses])].slice(0, 12);
}

function modelInterpretation(output: IRRModelOutput, span: string): string {
  const row = output.text_reading.salient_spans.find((item) => item.span === span)
    ?? output.text_reading.salient_spans.find((item) => item.span.includes(span) || span.includes(item.span));
  return row?.contextual_meaning || row?.literal_meaning || "";
}

function reportForRound(bundle: IRR03Bundle, storyId: string, round: number): Record<string, unknown> | undefined {
  const records = Array.isArray(bundle.spanGainReport.records) ? bundle.spanGainReport.records : [];
  return records.find((item) => {
    const row = asRecord(item);
    return row.story_id === storyId && row.round === round;
  }) as Record<string, unknown> | undefined;
}

function numericValue(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

function SpanReviewSurface({
  bundle,
  storyId,
  blind,
  reviews,
  onReviewChange,
}: {
  bundle: IRR03Bundle;
  storyId: string;
  blind: boolean;
  reviews: Record<string, IRR03LocalReviewRecord>;
  onReviewChange: (review: IRR03LocalReviewRecord) => void;
}) {
  const record = bundle.iterative.records.find((item) => item.story_id === storyId);
  const rounds = record?.rounds ?? [];
  const storyText = rounds[0]?.inference_input.story.text.simplified ?? "";
  if (!record || rounds.length === 0) {
    return <p className="irr0-muted">没有可用的迭代模型输出。</p>;
  }

  function updateSpan(
    review: IRR03LocalReviewRecord,
    span: string,
    changes: Partial<IRR03HumanSpanReview>,
  ): void {
    const round = rounds.find((item) => item.round === review.round);
    const modelSpan = round?.transition?.affected_spans.find((item) => item.span === span);
    const current = review.span_reviews.find((item) => item.span === span);
    const next: IRR03HumanSpanReview = {
      span,
      before_interpretation: current?.before_interpretation ?? modelSpan?.before_interpretation ?? "",
      after_interpretation: current?.after_interpretation ?? modelSpan?.after_interpretation ?? "",
      interpretation_depth: current?.interpretation_depth ?? 0,
      unsupported_interpretation: current?.unsupported_interpretation ?? 0,
      aesthetic_dimensions: current?.aesthetic_dimensions ?? {
        salience: 0,
        compression: 0,
        omission: 0,
        selection: 0,
      },
      evidence_refs: current?.evidence_refs ?? review.evidence_ids,
      ...changes,
    };
    onReviewChange({
      ...review,
      span_reviews: [
        ...review.span_reviews.filter((item) => item.span !== span),
        next,
      ],
    });
  }

  return (
    <section className="irr0-span-review-surface">
      <div className="irr0-span-review-heading">
        <div>
          <p className="irr0-label">Span Review</p>
          <h2>证据 → 原文跨度 → 重读变化</h2>
        </div>
        <span className={bundle.manifest.execution.run_type === "real_model" ? "irr0-provider-badge" : "irr0-fixture-badge"}>
          {bundle.manifest.execution.run_type === "real_model"
            ? bundle.manifest.execution.provider + " · " + bundle.manifest.execution.model
            : "fixture pipeline only"}
        </span>
      </div>
      <article className="irr0-story-source">
        <p className="irr0-label">原文</p>
        <p className="irr0-story-id">{storyId}</p>
        <p className="irr0-story-text">{storyText}</p>
      </article>
      <div className="irr0-rounds">
        {rounds.filter((round) => round.round > 0).map((round) => {
          const previous = rounds.find((candidate) => candidate.round === round.round - 1);
          const key = spanReviewKey(storyId, round.round);
          const review = reviews[key] ?? emptySpanReview(round, storyId);
          const options = spanOptions(round, storyText);
          const report = reportForRound(bundle, storyId, round.round);
          const metrics = asRecord(report?.metrics);
          const selected = review.selected_spans;
          return (
            <section className="irr0-round irr0-span-review-round" key={round.round}>
              <div className="irr0-round-heading">
                <h3>Round {round.round}</h3>
                <span>新增史料后的人工作业</span>
              </div>
              <EvidenceList evidence={round.evidence_added} />
              <div className="irr0-span-choice-block">
                <p className="irr0-label">原文 spans</p>
                <div className="irr0-span-choice-list">
                  {options.map((span, index) => (
                    <label className="irr0-span-choice" key={span + "-" + String(index)}>
                      <input
                        type="checkbox"
                        checked={selected.includes(span)}
                        onChange={(event) => {
                          const nextSelected = event.target.checked
                            ? [...new Set([...selected, span])]
                            : selected.filter((item) => item !== span);
                          onReviewChange({
                            ...review,
                            selected_spans: nextSelected,
                            no_effect: false,
                          });
                        }}
                      />
                      <span>{span}</span>
                    </label>
                  ))}
                  <label className="irr0-span-choice">
                    <input
                      type="checkbox"
                      checked={review.no_effect}
                      onChange={(event) => onReviewChange({
                        ...review,
                        no_effect: event.target.checked,
                        selected_spans: event.target.checked ? [] : selected,
                      })}
                    />
                    <span>没有影响</span>
                  </label>
                </div>
                <label className="irr0-span-other">
                  <span>其他</span>
                  <input
                    value={review.custom_span ?? ""}
                    onChange={(event) => {
                      const custom = event.target.value;
                      onReviewChange({
                        ...review,
                        custom_span: custom,
                        selected_spans: custom ? [...new Set([...selected, custom])] : selected,
                        no_effect: false,
                      });
                    }}
                    placeholder="输入原文跨度"
                  />
                </label>
              </div>

              <div className="irr0-span-before-after">
                <div>
                  <p className="irr0-label">Before interpretation</p>
                  {selected.length === 0
                    ? <p className="irr0-muted">尚未选择跨度。</p>
                    : selected.map((span) => <p key={"before-" + span}>{modelInterpretation(previous?.output ?? round.output, span)}</p>)}
                </div>
                <div>
                  <p className="irr0-label">After interpretation</p>
                  {selected.length === 0
                    ? <p className="irr0-muted">尚未选择跨度。</p>
                    : selected.map((span) => <p key={"after-" + span}>{modelInterpretation(round.output, span)}</p>)}
                </div>
              </div>

              {selected.map((span) => {
                const modelSpan: IRR03AffectedSpan | undefined = round.transition?.affected_spans.find((item) => item.span === span);
                const humanSpan = review.span_reviews.find((item) => item.span === span);
                const depth = humanSpan?.interpretation_depth ?? 0;
                const unsupported = humanSpan?.unsupported_interpretation ?? 0;
                const dimensions = humanSpan?.aesthetic_dimensions ?? {
                  salience: 0,
                  compression: 0,
                  omission: 0,
                  selection: 0,
                };
                return (
                  <article className="irr0-span-review-card" key={"review-" + span}>
                    <p className="irr0-span-text">{span}</p>
                    {modelSpan && <p className="irr0-muted">模型 affected span · 历史 {modelSpan.historical_depth} · 审美 {modelSpan.aesthetic_depth}</p>}
                    <div className="irr0-span-scale">
                      <span>历史深度</span>
                      {[0, 1, 2, 3, 4].map((value) => (
                        <label key={"depth-" + String(value)}>
                          <input
                            type="radio"
                            name={key + "-depth-" + span}
                            checked={depth === value}
                            onChange={() => updateSpan(review, span, { interpretation_depth: value })}
                          />
                          {value}
                        </label>
                      ))}
                    </div>
                    <div className="irr0-span-scale">
                      <span>审美深度</span>
                      {(["salience", "compression", "omission", "selection"] as const).map((dimension) => (
                        <label key={dimension}>
                          <input
                            type="checkbox"
                            checked={dimensions[dimension] === 1}
                            onChange={(event) => updateSpan(review, span, {
                              aesthetic_dimensions: {
                                ...dimensions,
                                [dimension]: event.target.checked ? 1 : 0,
                              },
                            })}
                          />
                          {dimension}
                        </label>
                      ))}
                    </div>
                    <label className="irr0-span-select">
                      <span>过度解释</span>
                      <select
                        value={String(unsupported)}
                        onChange={(event) => updateSpan(review, span, { unsupported_interpretation: Number(event.target.value) })}
                      >
                        <option value="0">支持</option>
                        <option value="1">无支持的延伸</option>
                        <option value="2">误导性重释</option>
                      </select>
                    </label>
                  </article>
                );
              })}

              <div className="irr0-span-review-stop">
                <p className="irr0-label">继续查史？</p>
                <div className="irr0-review-choice-list">
                  <button type="button" className={review.continue_reading === "yes" ? "active" : ""} onClick={() => onReviewChange({ ...review, continue_reading: "yes", stop_reason: null })}>Yes</button>
                  <button type="button" className={review.continue_reading === "no" ? "active" : ""} onClick={() => onReviewChange({ ...review, continue_reading: "no" })}>No</button>
                </div>
                <select
                  value={review.stop_reason ?? ""}
                  onChange={(event) => onReviewChange({ ...review, stop_reason: (event.target.value || null) as SpanStopReason })}
                >
                  <option value="">停止/继续理由（可选）</option>
                  <option value="unresolved_high_value_question">仍有高价值问题</option>
                  <option value="more_context_may_change_span">更多材料可能改变跨度</option>
                  <option value="saturated">已饱和</option>
                  <option value="new_evidence_low_value">新增材料价值低</option>
                  <option value="unsupported_drift">出现无支持漂移</option>
                </select>
              </div>

              <div className="irr0-span-metrics">
                <p className="irr0-label">模型诊断（非 Gold）</p>
                <span>历史深度 {numericValue(metrics.historical_depth)}</span>
                <span>审美深度 {numericValue(metrics.aesthetic_depth)}</span>
                <span>问题深度 {numericValue(metrics.question_depth)}</span>
                <span>过度解释 {numericValue(metrics.unsupported_interpretation_count)}</span>
              </div>
              {blind && <p className="irr0-muted">Blind review：Gold、目标深度与证据角色已隐藏。</p>}
            </section>
          );
        })}
      </div>
    </section>
  );
}

function loadStoredReviews(): Record<string, ReviewChoice> {
  if (typeof window === "undefined") return {};
  try {
    const value = JSON.parse(window.localStorage.getItem(REVIEW_STORAGE_KEY) ?? "{}") as Record<string, ReviewChoice>;
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function loadStoredSpanReviews(): Record<string, IRR03LocalReviewRecord> {
  if (typeof window === "undefined") return {};
  try {
    const value = JSON.parse(window.localStorage.getItem("shishuoSketch.irr0-3-span-review") ?? "{}") as Record<string, IRR03LocalReviewRecord>;
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function downloadReviews(value: Record<string, ReviewChoice>): void {
  const blob = new Blob([JSON.stringify({ schema: "irr0.2-local-review", records: value }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "irr0-2-local-review.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function downloadSpanReviews(value: Record<string, IRR03LocalReviewRecord>): void {
  const records = Object.values(value).sort((left, right) => {
    const storyOrder = left.story_id.localeCompare(right.story_id);
    return storyOrder || left.round - right.round;
  });
  const blob = new Blob([JSON.stringify({
    schema: "irr0.3-span-review",
    stage: "IRR0.3",
    schema_version: "v0",
    scope: { story_ids: PILOT_STORIES },
    records,
  }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "irr0-3-span-review.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function conditionLabel(mode: IRRReviewMode): string {
  return {
    text_only: "Text only",
    all_at_once: "All context",
    iterative: "Iterative",
    gold: "Gold",
  }[mode];
}

export function IRRReviewPage() {
  const [bundle, setBundle] = useState<IRRReviewBundle | null>(null);
  const [gold, setGold] = useState<IRRGoldRecord[] | null>(null);
  const [selectedStory, setSelectedStory] = useState(IRR04_PILOT_STORIES[0]);
  const [mode, setMode] = useState<IRRReviewMode>("text_only");
  const [surface, setSurface] = useState<"conditions" | "span_review" | "semantic_ladder">("semantic_ladder");
  const [blind, setBlind] = useState(false);
  const [reviews, setReviews] = useState<Record<string, ReviewChoice>>(loadStoredReviews);
  const [spanReviews, setSpanReviews] = useState<Record<string, IRR03LocalReviewRecord>>(loadStoredSpanReviews);
  const [spanBundle, setSpanBundle] = useState<IRR03Bundle | null>(null);
  const [spanLoading, setSpanLoading] = useState(false);
  const [spanError, setSpanError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void loadIRRReviewBundle()
      .then((next) => { if (active) { setBundle(next); setLoading(false); } })
      .catch((reason: unknown) => { if (active) { setError(reason instanceof Error ? reason.message : String(reason)); setLoading(false); } });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (mode !== "gold" || gold) return;
    void loadIRRGold().then((next) => setGold(next.records)).catch(() => setGold([]));
  }, [gold, mode]);

  useEffect(() => {
    if (surface !== "span_review" || spanBundle || spanError) return;
    let active = true;
    setSpanLoading(true);
    void loadIRR03ReviewBundle()
      .then((next) => {
        if (active) {
          setSpanBundle(next);
          setSpanLoading(false);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setSpanError(reason instanceof Error ? reason.message : String(reason));
          setSpanLoading(false);
        }
      });
    return () => { active = false; };
  }, [spanBundle, spanError, surface]);

  const selectedModelRecord = useMemo(() => {
    if (!bundle || mode === "gold") return undefined;
    const records = mode === "text_only" ? bundle.textOnly.records : mode === "all_at_once" ? bundle.allAtOnce.records : bundle.iterative.records;
    return recordFor(records, selectedStory);
  }, [bundle, mode, selectedStory]);
  const selectedGold = gold?.find((record) => record.story_id === selectedStory);
  const currentReviewKey = `${selectedStory}:${mode}`;
  const storyOptions = surface === "semantic_ladder" ? IRR04_PILOT_STORIES : PILOT_STORIES;

  function chooseReview(value: ReviewChoice): void {
    const next = { ...reviews, [currentReviewKey]: value };
    setReviews(next);
    window.localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(next));
  }

  function chooseSpanReview(value: IRR03LocalReviewRecord): void {
    const key = spanReviewKey(value.story_id, value.round);
    const next = { ...spanReviews, [key]: value };
    setSpanReviews(next);
    window.localStorage.setItem("shishuoSketch.irr0-3-span-review", JSON.stringify(next));
  }

  if (loading) return <main className="page-shell loading-state"><p className="brand">世说Sketch</p><p>正在读取 IRR 重读实验……</p></main>;
  if (error || bundle === null) return <main className="page-shell"><section className="error-panel"><p className="brand">世说Sketch</p><h1>IRR 实验载入失败</h1><p>{error ?? "实验数据不可用。"}</p></section></main>;
  const storyInput = recordFor(bundle.textOnly.records, selectedStory)?.inference_input?.story;

  return (
    <main className="page-shell irr0-review-page">
      <header className="site-header irr0-review-header">
        <div>
          <p className="brand">世说Sketch · Research</p>
          <h1>IRR0.4 语义递进重读实验</h1>
          <p className="tagline">以同一原文跨度为中心，比较字面、历史、关系与审美重读；同时检查 Memory / Fresh 与 Negative Control。</p>
        </div>
        <a className="ux2-index-back" href={import.meta.env.BASE_URL}>返回阅读</a>
      </header>

      <section className="irr0-review-toolbar" aria-label="实验控制">
        <div className="irr0-story-selector">
          <p className="irr0-label">Stories</p>
          {storyOptions.map((storyId) => <button type="button" key={storyId} className={selectedStory === storyId ? "active" : ""} onClick={() => setSelectedStory(storyId)}>{storyId}</button>)}
        </div>
        <div className="irr0-condition-selector" role="tablist" aria-label="审阅视图">
          <button type="button" role="tab" aria-selected={surface === "semantic_ladder"} className={surface === "semantic_ladder" ? "active" : ""} onClick={() => { setSurface("semantic_ladder"); if (!IRR04_PILOT_STORIES.includes(selectedStory)) setSelectedStory(IRR04_PILOT_STORIES[0]); }}>IRR0.4 Semantic Ladder</button>
          <button type="button" role="tab" aria-selected={surface === "span_review"} className={surface === "span_review" ? "active" : ""} onClick={() => setSurface("span_review")}>IRR0.3 Span Review</button>
          <button type="button" role="tab" aria-selected={surface === "conditions"} className={surface === "conditions" ? "active" : ""} onClick={() => setSurface("conditions")}>Baseline Conditions</button>
        </div>
        {surface === "conditions" && <div className="irr0-condition-selector" role="tablist" aria-label="阅读条件">
          {(["text_only", "all_at_once", "iterative"] as IRRReviewMode[]).map((current) => <button type="button" role="tab" aria-selected={mode === current} key={current} className={mode === current ? "active" : ""} onClick={() => setMode(current)}>{conditionLabel(current)}</button>)}
          {!blind && <button type="button" role="tab" aria-selected={mode === "gold"} className={mode === "gold" ? "gold active" : "gold"} onClick={() => setMode("gold")}>Gold</button>}
        </div>}
        <div className="irr0-blind-controls">
          <button type="button" onClick={() => { setBlind((value) => !value); if (!blind && mode === "gold") setMode("text_only"); }}>Blind review: {blind ? "ON" : "OFF"}</button>
          {surface === "conditions"
            ? <button type="button" onClick={() => downloadReviews(reviews)}>导出本地判断</button>
            : surface === "span_review"
              ? <button type="button" onClick={() => downloadSpanReviews(spanReviews)}>导出 Span Review</button>
              : null}
        </div>
      </section>

      {surface === "semantic_ladder" ? (
        <IRR04SemanticLadder storyId={selectedStory} blind={blind} />
      ) : surface === "span_review" ? (
        spanLoading
          ? <section className="irr0-condition-panel"><p className="irr0-muted">Span Review 载入中……</p></section>
          : spanError
            ? <section className="irr0-condition-panel"><p className="irr0-muted">Span Review 暂时不可用：{spanError}</p></section>
            : spanBundle
              ? <SpanReviewSurface bundle={spanBundle} storyId={selectedStory} blind={blind} reviews={spanReviews} onReviewChange={chooseSpanReview} />
              : <section className="irr0-condition-panel"><p className="irr0-muted">Span Review 尚未载入。</p></section>
      ) : (
      <>
      <article className="irr0-story-source">
        <p className="irr0-label">原文</p>
        <p className="irr0-story-id">{selectedStory}</p>
        {storyInput && <p className="irr0-story-text">{storyInput.text.simplified}</p>}
        {selectedModelRecord?.inference_input && selectedModelRecord.inference_input.evidence.length > 0 && mode === "all_at_once" && <EvidenceList evidence={selectedModelRecord.inference_input.evidence} title="全部可用史料" />}
      </article>

      <section className={mode === "gold" ? "irr0-condition-panel gold" : "irr0-condition-panel"}>
        <div className="irr0-condition-heading">
          <h2>{conditionLabel(mode)}</h2>
          {bundle.manifest.execution.real_model_run
            ? <span className="irr0-provider-badge">{bundle.manifest.execution.provider} · {bundle.manifest.execution.model}</span>
            : <span className="irr0-fixture-badge">fixture pipeline only</span>}
        </div>
        {mode === "iterative" && selectedModelRecord
          ? <IterativeRounds bundle={bundle} storyId={selectedStory} record={selectedModelRecord} blind={blind} />
          : mode === "gold"
            ? selectedGold ? <GoldRounds record={selectedGold} /> : <p className="irr0-muted">Gold 载入中……</p>
            : selectedModelRecord?.output
              ? <><ModelReading output={selectedModelRecord.output} /><p className="irr0-model-note">模型输入哈希：{selectedModelRecord.input_hash ?? "—"}</p></>
              : <p className="irr0-muted">该条件没有可用输出。</p>}
      </section>

      {!blind && <section className="irr0-analysis-panel">
        <p className="irr0-label">实验摘要</p>
        <p className="irr0-muted">{bundle.comparison.scientific_status === "fixture_pipeline_only" ? "当前为结构化 fixture，仅验证实验管线；没有真实模型凭据，因此不作性能结论。" : "当前结果来自已记录的模型运行。"}</p>
        <div className="irr0-summary-grid">
          {Object.entries(bundle.comparison.condition_summary).map(([condition, metrics]) => <div key={condition}><strong>{conditionLabel(condition as IRRReviewMode)}</strong><span>历史 {metrics.historical_score?.toFixed(3)} · 语言 {metrics.linguistic_salience_score?.toFixed(3)} · 审美 {metrics.aesthetic_operation_score?.toFixed(3)}</span></div>)}
        </div>
        <p className="irr0-muted">问题检查：context over text-only = {bundle.comparison.questions.context_improves_over_text_only ? "是" : "否"}；iterative over all-at-once = {bundle.comparison.questions.iterative_outperforms_all_at_once ? "是" : "否"}；hard-negative = {bundle.comparison.questions.hard_negative_recognized ? "识别" : "未识别"}；degradation = {bundle.comparison.questions.any_degradation ? "有" : "无"}。</p>
      </section>}

      {mode !== "gold" && <section className="irr0-local-review" aria-label="本地盲审判断">
        <p className="irr0-label">本地判断（不写入 Gold）</p>
        <div className="irr0-review-choice-list">
          {REVIEW_OPTIONS.map((option) => <button type="button" key={option} className={reviews[currentReviewKey] === option ? "active" : ""} onClick={() => chooseReview(option)}>{option}</button>)}
        </div>
        {reviews[currentReviewKey] && <p className="irr0-muted">已保存：{reviews[currentReviewKey]}</p>}
      </section>}
      </>
      )}
    </main>
  );
}
