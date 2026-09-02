import { CheckCircle2, ClipboardCheck, LockKeyhole, RefreshCw, ShieldAlert } from "lucide-react";
import { useState } from "react";

type Dimension = "copyright" | "extraction_quality" | "medical_accuracy" | "patient_readability";
type Source = { source_id: string; title: string; evidence_type: string; review_status: string; version?: string };
type Review = { dimension: Dimension; decision: "approved" | "rejected"; reviewer: string; reason: string };
type ReviewState = { source_id: string; review_status: string; required_dimensions: Dimension[]; latest_reviews: Review[] };
type ChunkPage = { total: number; items: { chunk_id: string; ordinal: number; text: string; page_start?: number; page_end?: number; timestamp_start_seconds?: number; timestamp_end_seconds?: number; section_path: string[]; extraction_method: string; review_status: string; content_hash: string }[] };

const labels: Record<Dimension, string> = {
  copyright: "版权与授权",
  extraction_quality: "提取质量",
  medical_accuracy: "医学准确性",
  patient_readability: "患者可读性",
};

export function Admin() {
  const [adminKey, setAdminKey] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<Source | null>(null);
  const [state, setState] = useState<ReviewState | null>(null);
  const [chunks, setChunks] = useState<ChunkPage | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Admin-Key": adminKey, ...init?.headers },
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail ?? "操作未完成");
    return body as T;
  }

  async function loadSources() {
    setBusy(true); setError("");
    try {
      setSources(await api<Source[]>("/api/v1/admin/evidence/sources"));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "无法连接"); }
    finally { setBusy(false); }
  }

  async function openSource(source: Source) {
    setSelected(source); setError("");
    try {
      const [reviewState, chunkPage] = await Promise.all([
        api<ReviewState>(`/api/v1/admin/evidence/sources/${source.source_id}/reviews`),
        api<ChunkPage>(`/api/v1/admin/evidence/sources/${source.source_id}/chunks?limit=20`),
      ]);
      setState(reviewState); setChunks(chunkPage);
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : "无法读取审核状态"); }
  }

  async function submit(dimension: Dimension, decision: "approved" | "rejected") {
    if (!selected || reviewer.trim().length < 2 || reason.trim().length < 5) {
      setError("请填写审核人，并记录不少于 5 个字的审核依据。"); return;
    }
    setBusy(true); setError("");
    try {
      const next = await api<ReviewState>(`/api/v1/admin/evidence/sources/${selected.source_id}/reviews`, {
        method: "POST", body: JSON.stringify({ dimension, decision, reviewer, reason }),
      });
      setState(next);
      setSources((items) => items.map((item) => item.source_id === selected.source_id ? { ...item, review_status: next.review_status } : item));
      setReason("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "审核提交失败"); }
    finally { setBusy(false); }
  }

  async function changeLifecycle(status: "quarantined" | "outdated" | "withdrawn") {
    if (!selected || reviewer.trim().length < 2 || reason.trim().length < 5) {
      setError("下线或隔离资料前，请填写操作人和具体理由。"); return;
    }
    setBusy(true); setError("");
    try {
      await api(`/api/v1/admin/evidence/sources/${selected.source_id}/lifecycle`, {
        method: "POST", body: JSON.stringify({ status, actor: reviewer, reason }),
      });
      setState((current) => current ? { ...current, review_status: status } : current);
      setSources((items) => items.map((item) => item.source_id === selected.source_id ? { ...item, review_status: status } : item));
      setReason("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "状态变更失败"); }
    finally { setBusy(false); }
  }

  const latest = new Map(state?.latest_reviews.map((item) => [item.dimension, item]));

  return <main className="admin-shell">
    <header className="admin-header"><div><span className="eyebrow">GI-Onco Navigator</span><h1>证据治理工作台</h1><p>资料默认隔离。四项审核全部通过后，才允许进入患者检索。</p></div><a href="/">返回患者端</a></header>
    <section className="admin-login"><LockKeyhole /><label>管理密钥<input type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} placeholder="仅保存在当前页面内存中" /></label><button onClick={loadSources} disabled={busy || !adminKey}><RefreshCw size={17} /> 连接并刷新</button></section>
    {error && <div className="error-message" role="alert">{error}</div>}
    <div className="admin-columns">
      <section className="source-list"><h2>资料来源 <small>{sources.length}</small></h2>{sources.length === 0 && <p className="admin-empty">连接后查看已登记资料。</p>}{sources.map((source) => <button key={source.source_id} onClick={() => openSource(source)} className={selected?.source_id === source.source_id ? "selected" : ""}><span><b>{source.title}</b><small>{source.evidence_type}{source.version ? ` · ${source.version}` : ""}</small></span><em data-status={source.review_status}>{source.review_status}</em></button>)}</section>
      <section className="review-panel">
        {!selected || !state ? <div className="admin-empty"><ClipboardCheck size={40} /><p>选择一个来源，查看并记录审核。</p></div> : <>
          <div className="review-title"><div><small>{selected.source_id}</small><h2>{selected.title}</h2></div><strong data-status={state.review_status}>{state.review_status}</strong></div>
          <div className="lifecycle-actions"><span>紧急状态控制</span><button onClick={() => changeLifecycle("quarantined")} disabled={busy}>重新隔离</button><button onClick={() => changeLifecycle("outdated")} disabled={busy}>标记过期</button><button className="reject" onClick={() => changeLifecycle("withdrawn")} disabled={busy}>撤回</button></div>
          <div className="reviewer-fields"><label>审核人<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="真实姓名或团队标识" /></label><label>本次审核依据<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="记录核对范围、发现和决定理由" /></label></div>
          <section className="chunk-preview"><h3>提取内容抽查 <small>{chunks?.total ?? 0} 个内容块，当前显示前 20 个</small></h3>{chunks?.items.length === 0 && <p>该来源尚无可审核内容块，不能仅凭来源名称完成内容审核。</p>}{chunks?.items.map((chunk) => <details key={chunk.chunk_id}><summary><span>内容块 {chunk.ordinal + 1}</span><small>{chunk.page_start ? `第 ${chunk.page_start}${chunk.page_end && chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ""} 页` : chunk.timestamp_start_seconds !== undefined ? `${chunk.timestamp_start_seconds}–${chunk.timestamp_end_seconds ?? "?"} 秒` : chunk.section_path.join(" / ") || "无定位"} · {chunk.extraction_method}</small></summary><p>{chunk.text}</p><code>SHA-256 {chunk.content_hash}</code></details>)}</section>
          <div className="review-gates">{state.required_dimensions.map((dimension) => { const item = latest.get(dimension); return <article key={dimension}><div>{item?.decision === "approved" ? <CheckCircle2 /> : <ShieldAlert />}<span><b>{labels[dimension]}</b><small>{item ? `${item.reviewer}：${item.reason}` : "尚未审核"}</small></span></div><div><button onClick={() => submit(dimension, "approved")} disabled={busy}>通过</button><button className="reject" onClick={() => submit(dimension, "rejected")} disabled={busy}>拒绝</button></div></article>; })}</div>
        </>}
      </section>
    </div>
  </main>;
}
