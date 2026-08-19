import { useEffect, useMemo, useState } from "react";
import {
  loadIRR04ReviewBundle,
  type IRR04Bundle,
  type IRR04Condition,
  type IRR04ModelOutput,
  type IRR04NegativeControl,
  type IRR04Round,
  type IRR04StoryRecord,
} from "./irr04Review";

const STORAGE_KEY = "shishuoSketch.irr0-4-human-review";
const CONDITION_LABELS: Record<IRR04Condition, string> = { memory: "Memory", fresh: "Fresh" };
const DEEPENING = ["clear", "slight", "none", "worse"] as const;
type Deepening = typeof DEEPENING[number] | null;
type Unsupported = "none" | "unsupported" | "misleading" | null;
type Choice = "yes" | "no" | null;
type Branch = "main" | "negative_control";

interface HumanReview {
  story_id: string;
  branch: Branch;
  round_label: string;
  condition: IRR04Condition;
  visible_deepening: Deepening;
  historical_depth: number | null;
  aesthetic_depth: number | null;
  unsupported_interpretation: Unsupported;
  anchoring_detected: Choice;
  continue_reading: Choice;
  notes?: string;
}

type ReviewMap = Record<string, HumanReview>;

function reviewKey(storyId: string, branch: Branch, roundLabel: string, condition: IRR04Condition): string {
  return storyId + ":" + branch + ":" + roundLabel + ":" + condition;
}

function readReviews(): ReviewMap {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}") as ReviewMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function emptyReview(storyId: string, branch: Branch, roundLabel: string, condition: IRR04Condition): HumanReview {
  return {
    story_id: storyId,
    branch,
    round_label: roundLabel,
    condition,
    visible_deepening: null,
    historical_depth: null,
    aesthetic_depth: null,
    unsupported_interpretation: null,
    anchoring_detected: null,
    continue_reading: null,
  };
}

function outputFor(round: IRR04Round | IRR04NegativeControl, condition: IRR04Condition): IRR04ModelOutput {
  return condition === "memory" ? round.memory_reading.output : round.fresh_reading.output;
}

function storyText(record: IRR04StoryRecord): string {
  return record.rounds[0].memory_reading.inference_input.story.text.simplified;
}

function findReading(output: IRR04ModelOutput, target: string) {
  return output.span_readings.find((row) => row.span === target)
    ?? output.span_readings.find((row) => row.span.includes(target) || target.includes(row.span));
}

function evidenceFor(round: IRR04Round | IRR04NegativeControl) {
  const all = round.memory_reading.inference_input.evidence;
  const refs = new Set(round.evidence_bundle);
  return all.filter((item) => refs.has(item.evidence_ref));
}

function exportReviews(reviews: ReviewMap): void {
  const records = Object.values(reviews).sort((left, right) => (
    left.story_id.localeCompare(right.story_id)
    || left.branch.localeCompare(right.branch)
    || left.round_label.localeCompare(right.round_label)
    || left.condition.localeCompare(right.condition)
  ));
  const blob = new Blob([JSON.stringify({
    schema: "irr0.4-human-review",
    stage: "IRR0.4",
    schema_version: "v0",
    scope: { story_ids: ["27-jiajue-008", "09-pinzao-017", "06-yaliang-017"] },
    records,
  }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "irr0-4-human-review.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function HumanControls({
  review,
  onChange,
  blind,
}: {
  review: HumanReview;
  onChange: (next: HumanReview) => void;
  blind: boolean;
}) {
  return (
    <div className="irr04-human-controls">
      <p className="irr0-label">人工作业（不写入 Gold）</p>
      <div className="irr04-control-row">
        <span>可见深化</span>
        {DEEPENING.map((value) => <button type="button" key={value} className={review.visible_deepening === value ? "active" : ""} onClick={() => onChange({ ...review, visible_deepening: value })}>{value === "clear" ? "明显" : value === "slight" ? "轻微" : value === "none" ? "无" : "变差"}</button>)}
      </div>
      <div className="irr04-control-row">
        <span>历史深度</span>
        {[0, 1, 2, 3, 4].map((value) => <button type="button" key={value} className={review.historical_depth === value ? "active" : ""} onClick={() => onChange({ ...review, historical_depth: value })}>{value}</button>)}
      </div>
      <div className="irr04-control-row">
        <span>审美深度</span>
        {[0, 1, 2, 3, 4].map((value) => <button type="button" key={value} className={review.aesthetic_depth === value ? "active" : ""} onClick={() => onChange({ ...review, aesthetic_depth: value })}>{value}</button>)}
      </div>
      <label className="irr04-select-row">
        <span>过度解释</span>
        <select value={review.unsupported_interpretation ?? ""} onChange={(event) => onChange({ ...review, unsupported_interpretation: (event.target.value || null) as Unsupported })}>
          <option value="">未判断</option>
          <option value="none">无</option>
          <option value="unsupported">无支持</option>
          <option value="misleading">误导</option>
        </select>
      </label>
      <div className="irr04-control-row">
        <span>检测到锚定</span>
        {(["yes", "no"] as const).map((value) => <button type="button" key={value} className={review.anchoring_detected === value ? "active" : ""} onClick={() => onChange({ ...review, anchoring_detected: value })}>{value === "yes" ? "是" : "否"}</button>)}
      </div>
      <div className="irr04-control-row">
        <span>继续查史</span>
        {(["yes", "no"] as const).map((value) => <button type="button" key={value} className={review.continue_reading === value ? "active" : ""} onClick={() => onChange({ ...review, continue_reading: value })}>{value === "yes" ? "是" : "否"}</button>)}
      </div>
      {!blind && <p className="irr0-muted">这些判断独立于 Gold；用于记录人眼能否看见语义升级。</p>}
      {blind && <p className="irr0-muted">Blind review：目标跨度、预期效果和 Gold 已隐藏。</p>}
    </div>
  );
}

function LadderRound({
  record,
  round,
  condition,
  branch,
  blind,
  review,
  onReviewChange,
}: {
  record: IRR04StoryRecord;
  round: IRR04Round | IRR04NegativeControl;
  condition: IRR04Condition;
  branch: Branch;
  blind: boolean;
  review: HumanReview | undefined;
  onReviewChange: (next: HumanReview) => void;
}) {
  const output = outputFor(round, condition);
  const targets = blind
    ? output.span_readings.map((item) => item.span)
    : (round.gold?.target_spans ?? record.critical_spans);
  const uniqueTargets = [...new Set(targets)];
  return (
    <section className="irr04-ladder-round">
      <div className="irr04-round-title">
        <h3>{round.round_label}</h3>
        <span>{round.semantic_stage}</span>
      </div>
      <p className="irr0-muted">{round.driving_question}</p>
      {round.evidence_bundle.length > 0 && (
        <details className="irr04-evidence">
          <summary>新增史料 · {round.evidence_bundle.length} 条</summary>
          {evidenceFor(round).map((item) => <p key={item.evidence_ref}><strong>{item.source_layer} · {item.source}</strong>：{item.quote} <small>{item.evidence_ref}</small></p>)}
        </details>
      )}
      {!blind && round.gold && <div className="irr04-gold-note"><span>预期效果</span><p>{round.gold.expected_effect}</p><small>目标：{round.gold.target_spans.join("；")}</small></div>}
      <div className="irr04-span-readings">
        {uniqueTargets.length === 0 && <p className="irr0-muted">模型没有报告跨度。</p>}
        {uniqueTargets.map((target) => {
          const reading = findReading(output, target);
          return (
            <article className="irr04-span-reading" key={target}>
              <p className="irr04-span-source">{target}</p>
              {reading ? <>
                <p><span className="irr0-label">字面</span>{reading.literal_reading}</p>
                <p><span className="irr0-label">当前解释</span>{reading.current_interpretation}</p>
                <p className="irr0-muted">{reading.change_type} · {reading.changed_from_previous ? "changed" : "未改变"} · 依据 {reading.supporting_evidence_ids.join("、") || "原文"}</p>
                <div className="irr04-depth-grid"><span>场景 {reading.scene_historical_depth}</span><span>关系 {reading.relational_depth}</span><span>回望 {reading.retrospective_depth}</span><span>审美 {reading.aesthetic_depth}</span></div>
                {reading.unsupported_inference && <p className="irr04-warning">模型标记为无支持推断</p>}
              </> : <p className="irr0-muted">模型未覆盖该跨度。</p>}
            </article>
          );
        })}
      </div>
      {output.aesthetic_observations.length > 0 && <div className="irr04-aesthetic-observations"><p className="irr0-label">审美观察</p>{output.aesthetic_observations.map((item, index) => <p key={item.span + "-" + String(index)}><strong>{item.span}</strong> · {item.operations.join("、")}：{item.observation}</p>)}</div>}
      {round.round_label !== "R0" && review && <HumanControls review={review} blind={blind} onChange={onReviewChange} />}
    </section>
  );
}

export function IRR04SemanticLadder({ storyId, blind }: { storyId: string; blind: boolean }) {
  const [bundle, setBundle] = useState<IRR04Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [condition, setCondition] = useState<IRR04Condition>("memory");
  const [branch, setBranch] = useState<Branch>("main");
  const [reviews, setReviews] = useState<ReviewMap>(readReviews);

  useEffect(() => {
    let active = true;
    void loadIRR04ReviewBundle().then((next) => { if (active) setBundle(next); }).catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, []);

  const record = useMemo(() => bundle?.semanticLadders.records.find((item) => item.story_id === storyId), [bundle, storyId]);
  if (error) return <section className="irr0-condition-panel"><p className="irr0-muted">IRR0.4 载入失败：{error}</p></section>;
  if (!bundle || !record) return <section className="irr0-condition-panel"><p className="irr0-muted">IRR0.4 语义梯载入中……</p></section>;

  const rounds: Array<IRR04Round | IRR04NegativeControl> = branch === "main"
    ? record.rounds
    : [record.rounds[0], record.rounds[1], record.negative_control];
  function save(next: HumanReview): void {
    const key = reviewKey(next.story_id, next.branch, next.round_label, next.condition);
    const updated = { ...reviews, [key]: next };
    setReviews(updated);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }

  return (
    <section className="irr04-semantic-ladder">
      <div className="irr04-ladder-heading">
        <div><p className="irr0-label">IRR0.4 Semantic Ladder</p><h2>同一跨度的语义升级</h2></div>
        <span className={bundle.manifest.execution.run_type === "real_model" ? "irr0-provider-badge" : "irr0-fixture-badge"}>{bundle.manifest.execution.run_type === "real_model" ? bundle.manifest.execution.provider + " · " + bundle.manifest.execution.model : "fixture pipeline only"}</span>
      </div>
      <article className="irr0-story-source"><p className="irr0-label">原文</p><p className="irr0-story-id">{storyId}</p><p className="irr0-story-text">{storyText(record)}</p></article>
      <div className="irr04-ladder-toolbar">
        <div className="irr0-condition-selector" role="tablist" aria-label="重读方式">{(["memory", "fresh"] as IRR04Condition[]).map((value) => <button type="button" role="tab" aria-selected={condition === value} className={condition === value ? "active" : ""} key={value} onClick={() => setCondition(value)}>{CONDITION_LABELS[value]}</button>)}</div>
        <div className="irr0-condition-selector" role="tablist" aria-label="语义分支"><button type="button" role="tab" aria-selected={branch === "main"} className={branch === "main" ? "active" : ""} onClick={() => setBranch("main")}>主梯</button><button type="button" role="tab" aria-selected={branch === "negative_control"} className={branch === "negative_control" ? "active" : ""} onClick={() => setBranch("negative_control")}>Negative Control</button></div>
        <button type="button" onClick={() => exportReviews(reviews)}>导出人审</button>
      </div>
      <p className="irr0-muted">{branch === "main" ? "Literal → Event → Relational → Aesthetic" : "R1 → related but low-value evidence"} · {condition === "memory" ? "保留上一轮模型理解" : "每轮从原文重新开始"}</p>
      {rounds.map((round) => {
        if (round.round_label === "R0") return <LadderRound key={round.round_label} record={record} round={round} condition={condition} branch={branch} blind={blind} review={undefined} onReviewChange={save} />;
        const key = reviewKey(storyId, branch, round.round_label, condition);
        return <LadderRound key={round.round_label} record={record} round={round} condition={condition} branch={branch} blind={blind} review={reviews[key] ?? emptyReview(storyId, branch, round.round_label, condition)} onReviewChange={save} />;
      })}
      {blind && <p className="irr0-muted">Blind review 已开启：Gold 预期效果与目标跨度不显示。</p>}
    </section>
  );
}
