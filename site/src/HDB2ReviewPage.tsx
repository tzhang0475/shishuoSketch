import { useEffect, useMemo, useState } from "react";
import {
  loadHDB2ReviewIndex,
  loadHDB2ReviewItem,
  type HDB2HumanDecision,
  type HDB2ReviewIndex,
  type HDB2ReviewIndexItem,
  type HDB2ReviewItem,
  type HDB2AffectedFact,
} from "./hdb2Review";

const STORAGE_KEY = "shishuoSketch.hdb2-human-review";
type PriorityFilter = "all" | "P1" | "P2" | "P3";
type TypeFilter = "all" | HDB2ReviewIndexItem["review_type"];

function loadStoredDecisions(): Record<string, HDB2HumanDecision> {
  if (typeof window === "undefined") return {};
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, HDB2HumanDecision> : {};
  } catch {
    return {};
  }
}

function typeLabel(value: string): string {
  return {
    identity: "身份判断",
    candidate_person: "新人物候选",
    compositional_kinship: "结构性亲属",
    office_or_title_holder: "官职 / 称号持有者",
  }[value] ?? value;
}

function statusLabel(value: string): string {
  return {
    direct_existing: "已由 HDB1 直接解析",
    explicit_resolved: "明确证据解析",
    contextually_resolved: "语境解析",
    contextually_preferred: "语境偏好，仍待确认",
    resolved_new_candidate: "新人物候选",
    compositional_reference: "结构性亲属表达",
    ruler_reference: "帝王称谓表达",
    office_reference: "官职表达",
    unresolved: "未解析",
    conflict: "冲突",
  }[value] ?? value;
}

function prettyFactState(value: string | undefined): string {
  return value?.split("_").join(" ") ?? "未分类";
}

function exportDecisions(decisions: Record<string, HDB2HumanDecision>): void {
  const records = Object.values(decisions)
    .sort((left, right) => left.review_id.localeCompare(right.review_id))
    .map(({ updated_at: _updatedAt, ...record }) => record);
  const payload = {
    schema: "hdb2-human-review-decisions-v1",
    candidate_only: true,
    canonical_write_back: false,
    records,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "hdb2-human-review-decisions.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function EvidencePanel({ item }: { item: HDB2ReviewItem }) {
  return (
    <div className="hdb2-evidence-stack">
      {item.selected_evidence.map((evidence) => (
        <details className="irr0-evidence" key={evidence.evidence_ref} open={evidence.exact_spans.length > 0}>
          <summary>{evidence.source_work ?? "史料"} · {evidence.source_layer ?? ""} · {evidence.evidence_ref}</summary>
          <blockquote>{evidence.excerpt}</blockquote>
          {evidence.exact_spans.length > 0 && <p className="hdb2-exact-spans">直接证据：{evidence.exact_spans.join("；")}</p>}
        </details>
      ))}
    </div>
  );
}

function JudgmentPrompt({ item }: { item: HDB2ReviewItem }) {
  return (
    <section className="hdb2-judgment-prompt" aria-labelledby="hdb2-judgment-heading">
      <p id="hdb2-judgment-heading" className="hdb2-judgment-eyebrow">需要你的判断</p>
      <h3 className="hdb2-review-question">{item.review_question}</h3>
      <div className="hdb2-judgment-copy">
        <div>
          <p className="irr0-label">系统判断</p>
          <p>{item.system_summary}</p>
        </div>
        <div>
          <p className="irr0-label">为什么需要人工审核</p>
          <p>{item.why_review_needed}</p>
        </div>
      </div>
      <div className="hdb2-decision-options">
        <p className="irr0-label">可作的判断</p>
        <ul>
          {item.decision_options.map((option) => <li key={option.key}><strong>{option.label}</strong><span>{option.description}</span></li>)}
        </ul>
      </div>
    </section>
  );
}

function MaterializationImpact({ item }: { item: HDB2ReviewItem }) {
  return (
    <section className="hdb2-materialization-impact">
      <p className="irr0-label">如果接受此判断，可能解锁</p>
      {item.materialization_impact.summary.length === 0
        ? <p className="irr0-muted">当前没有可量化的解锁项。</p>
        : <ul>{item.materialization_impact.summary.map((entry) => <li key={entry.kind}><strong>{entry.label}</strong></li>)}</ul>}
    </section>
  );
}

function FactGroup({ label, facts }: { label: string; facts: HDB2AffectedFact[] }) {
  if (facts.length === 0) return null;
  return (
    <section className="hdb2-fact-group">
      <p className="irr0-sublabel">{label}</p>
      {facts.map((fact, index) => (
        <article className="hdb2-fact" key={`${String(fact.candidate_id ?? index)}-${index}`}>
          <strong>{String(fact.relation_surface ?? fact.relation_class ?? "历史事实候选")}</strong>
          <span>{prettyFactState(typeof fact.state === "string" ? fact.state : undefined)}</span>
          {fact.primary_blocker && <small>阻塞：{String(fact.primary_blocker)}</small>}
          {fact.exact_span && <blockquote>{String(fact.exact_span)}</blockquote>}
        </article>
      ))}
    </section>
  );
}

function HDB2ReviewDetail({
  item,
  decision,
  onAction,
}: {
  item: HDB2ReviewItem;
  decision: HDB2HumanDecision | undefined;
  onAction: (action: HDB2HumanDecision["action"], candidateKey?: string | null) => void;
}) {
  const proposed = item.proposed_identity;
  const compositional = item.current_state.compositional_referent;
  const affected = item.affected_facts;
  return (
    <article className="hdb2-review-detail">
      <header className="irr0-condition-heading">
        <div>
          <p className="irr0-label">{typeLabel(item.review_type)} · {item.priority}</p>
          <h2>{item.target_surface}</h2>
          <p className="irr0-muted">{item.story_id} · {item.occurrence_id}</p>
        </div>
        <span className="irr0-provider-badge">{statusLabel(item.current_state.status)}</span>
      </header>

      <JudgmentPrompt item={item} />

      <section className="hdb2-story-context">
        <p className="irr0-label">故事原文</p>
        <p className="irr0-story-text">{item.story_context || "暂无故事原文"}</p>
        {item.relevant_annotation_context.length > 0 && (
          <div className="hdb2-annotation-context">
            <p className="irr0-sublabel">相关刘注 / 注文</p>
            {item.relevant_annotation_context.map((text, index) => <blockquote key={`${text}-${index}`}>{text}</blockquote>)}
          </div>
        )}
      </section>

      <section className="hdb2-proposal">
        <p className="irr0-label">当前建议</p>
        <p className="hdb2-proposal-name">{proposed.label ?? "未提出单一人物"}</p>
        <p className="irr0-muted">{statusLabel(proposed.status)} · {proposed.basis ?? "无"}</p>
        {item.support_families.length > 0 && <p className="hdb2-support">支持族：{item.support_families.join("、")}</p>}
      </section>

      {item.review_type === "compositional_kinship" && (
        <section className="hdb2-compositional-warning">
          <p className="irr0-label">结构性亲属问题</p>
          <p>此表达不是自动等同于其中的基础人物。</p>
          {item.compositional_context ? (
            <dl className="hdb2-compositional-details">
              <div><dt>基准人物</dt><dd>{item.compositional_context.base_person?.label ?? "未确定"}{item.compositional_context.base_person?.surface && item.compositional_context.base_person.surface !== item.compositional_context.base_person.label ? `（${item.compositional_context.base_person.surface}）` : ""}</dd></div>
              <div><dt>关系类型</dt><dd>{item.compositional_context.relation_label ?? item.compositional_context.relation_type ?? "未确定"}{item.compositional_context.relation_surface ? `（${item.compositional_context.relation_surface}）` : ""}</dd></div>
              <div><dt>指代对象候选</dt><dd>{item.compositional_context.referent_candidates.length > 0 ? item.compositional_context.referent_candidates.map((candidate) => candidate.display_name).join("、") : "暂无安全候选"}</dd></div>
            </dl>
          ) : compositional ? <pre>{JSON.stringify(compositional, null, 2)}</pre> : <p className="irr0-muted">请确认其结构性亲属关系及可能的独立指代。</p>}
        </section>
      )}

      <section className="hdb2-candidate-section">
        <p className="irr0-label">{item.review_type === "compositional_kinship" ? "可能的指代对象（不是基准人物）" : "候选人物"}</p>
        {item.candidate_people.length === 0
          ? <p className="irr0-muted">没有安全候选；可保留未解析或提出新人物候选。</p>
          : <div className="hdb2-candidate-list">{item.candidate_people.map((candidate, index) => (
            <button type="button" key={`${candidate.candidate_key ?? "candidate"}-${candidate.display_name}`} className={decision?.candidate_key === candidate.candidate_key ? "active" : ""} onClick={() => onAction("choose_candidate", candidate.candidate_key)}>
              <strong>#{candidate.rank ?? index + 1} {candidate.display_name}</strong>
              <small>{candidate.person_id ?? "候选人物"}{candidate.source ? ` · ${candidate.source}` : ""}</small>
            </button>
          ))}</div>}
      </section>

      <section className="hdb2-evidence-section">
        <p className="irr0-label">选定证据</p>
        <EvidencePanel item={item} />
      </section>

      <section className="hdb2-facts">
        <p className="irr0-label">可能受影响的候选事实</p>
        <FactGroup label="关系" facts={affected.relations} />
        <FactGroup label="亲属" facts={affected.kinship} />
        <FactGroup label="婚姻" facts={affected.marriage} />
        <FactGroup label="官职" facts={affected.office} />
        {affected.person_story.length > 0 && <p className="irr0-muted">本故事人物链接：{affected.person_story.map((entry) => String(entry.person_id ?? "待定")).join("、")}</p>}
      </section>

      <MaterializationImpact item={item} />

      <section className="hdb2-human-actions" aria-label="人工判断">
        <p className="irr0-label">人工判断（仅保存本地审阅，不写入 canonical）</p>
        <div className="irr0-review-choice-list">
          <button type="button" className={decision?.action === "accept_proposed" ? "active" : ""} onClick={() => onAction("accept_proposed", proposed.candidate_key)}>接受当前建议</button>
          <button type="button" className={decision?.action === "new_person_candidate" ? "active" : ""} onClick={() => onAction("new_person_candidate", null)}>新人物候选</button>
          <button type="button" className={decision?.action === "keep_unresolved" ? "active" : ""} onClick={() => onAction("keep_unresolved", null)}>保持未解析</button>
          <button type="button" className={decision?.action === "evidence_problem" ? "active" : ""} onClick={() => onAction("evidence_problem", null)}>证据 / 问题标记</button>
        </div>
        {decision && <p className="irr0-muted">已保存：{decision.action}{decision.candidate_key ? ` · ${decision.candidate_key}` : ""}</p>}
      </section>
    </article>
  );
}

export function HDB2ReviewPage() {
  const [index, setIndex] = useState<HDB2ReviewIndex | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [item, setItem] = useState<HDB2ReviewItem | null>(null);
  const [decisions, setDecisions] = useState<Record<string, HDB2HumanDecision>>(loadStoredDecisions);
  const [priority, setPriority] = useState<PriorityFilter>("all");
  const [reviewType, setReviewType] = useState<TypeFilter>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadHDB2ReviewIndex().then((next) => {
      setIndex(next);
      setSelectedId(next.items[0]?.review_id ?? null);
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  const visibleItems = useMemo(() => {
    if (!index) return [];
    return index.items.filter((entry) => (priority === "all" || entry.priority === priority) && (reviewType === "all" || entry.review_type === reviewType));
  }, [index, priority, reviewType]);

  useEffect(() => {
    if (visibleItems.length > 0 && !visibleItems.some((entry) => entry.review_id === selectedId)) setSelectedId(visibleItems[0].review_id);
  }, [selectedId, visibleItems]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    void loadHDB2ReviewItem(selectedId).then((next) => { if (active) setItem(next); }).catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [selectedId]);

  function saveAction(action: HDB2HumanDecision["action"], candidateKey: string | null = null): void {
    if (!item) return;
    const nextRecord: HDB2HumanDecision = {
      review_id: item.review_id,
      occurrence_id: item.occurrence_id,
      action,
      candidate_key: candidateKey,
      note: "",
    };
    const next = { ...decisions, [item.review_id]: nextRecord };
    setDecisions(next);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function move(delta: number): void {
    if (!selectedId || visibleItems.length === 0) return;
    const current = visibleItems.findIndex((entry) => entry.review_id === selectedId);
    const next = (current + delta + visibleItems.length) % visibleItems.length;
    setSelectedId(visibleItems[next].review_id);
  }

  if (error) return <main className="page-shell"><section className="error-panel"><p className="brand">世说Sketch</p><h1>HDB2 审阅载入失败</h1><p>{error}</p></section></main>;
  if (!index) return <main className="page-shell loading-state"><p className="brand">世说Sketch</p><p>正在读取 HDB2 审阅队列……</p></main>;
  const current = index.items.find((entry) => entry.review_id === selectedId) ?? visibleItems[0];
  const currentDecision = current ? decisions[current.review_id] : undefined;

  return (
    <main className="page-shell irr0-review-page hdb2-review-page">
      <header className="site-header irr0-review-header">
        <div>
          <p className="brand">世说Sketch · Historical Review</p>
          <h1>HDB2 人物身份审阅工作台</h1>
          <p className="tagline">Occurrence-level candidate review；所有判断保存在浏览器本地，尚不写入 canonical。</p>
        </div>
        <a className="ux2-index-back" href={import.meta.env.BASE_URL}>返回阅读</a>
      </header>

      <section className="irr0-review-toolbar hdb2-review-toolbar" aria-label="HDB2 queue controls">
        <div className="hdb2-filter-row">
          <label>优先级 <select value={priority} onChange={(event) => setPriority(event.target.value as PriorityFilter)}><option value="all">全部</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option></select></label>
          <label>类型 <select value={reviewType} onChange={(event) => setReviewType(event.target.value as TypeFilter)}><option value="all">全部</option><option value="identity">身份判断</option><option value="candidate_person">新人物候选</option><option value="compositional_kinship">结构性亲属</option><option value="office_or_title_holder">官职 / 称号</option></select></label>
          <span className="irr0-muted">{visibleItems.length} / {index.item_count} 项</span>
        </div>
        <div className="irr0-blind-controls">
          <button type="button" onClick={() => move(-1)} disabled={!current}>上一项</button>
          <button type="button" onClick={() => move(1)} disabled={!current}>下一项</button>
          <button type="button" onClick={() => exportDecisions(decisions)}>导出人工判断</button>
        </div>
      </section>

      <section className="hdb2-review-grid">
        <aside className="hdb2-review-queue" aria-label="HDB2 review queue">
          {visibleItems.map((entry) => (
            <button type="button" key={entry.review_id} className={entry.review_id === current?.review_id ? "active" : ""} onClick={() => setSelectedId(entry.review_id)}>
              <span><strong>{entry.target_surface}</strong> · {entry.story_id}</span>
              <small>{entry.priority} · {typeLabel(entry.review_type)} · {statusLabel(entry.status)}</small>
            </button>
          ))}
        </aside>
        <div className="hdb2-review-main">
          {item && current ? <HDB2ReviewDetail item={item} decision={currentDecision} onAction={saveAction} /> : <p className="irr0-muted">没有符合当前筛选的审阅项。</p>}
        </div>
      </section>
    </main>
  );
}
