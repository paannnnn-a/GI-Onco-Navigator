import { CheckCircle2, ClipboardCheck, LockKeyhole, RefreshCw, ShieldAlert, Upload } from "lucide-react";
import { useState } from "react";

type Dimension = "copyright" | "extraction_quality" | "medical_accuracy" | "patient_readability";
type ExtractionAudit = { pages?: number; readable_text_pages?: number; pages_needing_ocr?: number; paragraphs?: number; verified_cues?: number; readable_blocks?: number; unresolved_blocks?: number; human_verified_content_free_pages?: { page_numbers: number[]; reviewer: string; reason: string } };
type Source = { source_id: string; title: string; evidence_type: string; review_status: string; version?: string; metadata?: { extraction_audit?: ExtractionAudit } };
type Review = { dimension: Dimension; decision: "approved" | "rejected"; reviewer: string; reason: string };
type ReviewState = { source_id: string; review_status: string; required_dimensions: Dimension[]; latest_reviews: Review[] };
type ChunkPage = { total: number; offset: number; limit: number; items: { chunk_id: string; ordinal: number; text: string; page_start?: number; page_end?: number; timestamp_start_seconds?: number; timestamp_end_seconds?: number; section_path: string[]; extraction_method: string; review_status: string; content_hash: string }[] };
type LifecycleEvent = { event_id: number; previous_status: string; new_status: string; actor: string; reason: string; created_at: string };

const CHUNK_PAGE_SIZE = 20;

const labels: Record<Dimension, string> = {
  copyright: "Copyright and permission",
  extraction_quality: "Extraction quality",
  medical_accuracy: "Medical accuracy",
  patient_readability: "Patient readability",
};

export function Admin() {
  const [adminKey, setAdminKey] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<Source | null>(null);
  const [state, setState] = useState<ReviewState | null>(null);
  const [chunks, setChunks] = useState<ChunkPage | null>(null);
  const [lifecycle, setLifecycle] = useState<LifecycleEvent[]>([]);
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState("patient_education");
  const [uploadCancer, setUploadCancer] = useState("colon");
  const [uploadCopyright, setUploadCopyright] = useState("unknown");
  const [uploadNotice, setUploadNotice] = useState("");

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const isForm = init?.body instanceof FormData;
    const response = await fetch(path, {
      ...init,
      headers: { ...(!isForm ? { "Content-Type": "application/json" } : {}), "X-Admin-Key": adminKey, ...init?.headers },
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail ?? "The operation could not be completed.");
    return body as T;
  }

  async function uploadEvidence() {
    if (!uploadFile || !uploadId.trim() || !uploadTitle.trim()) {
      setError("Select a source file and enter its source ID and title."); return;
    }
    setBusy(true); setError(""); setUploadNotice("");
    const form = new FormData();
    form.append("manifest_json", JSON.stringify({
      source_id: uploadId.trim(), title: uploadTitle.trim(), evidence_type: uploadType,
      cancer_types: [uploadCancer], copyright_status: uploadCopyright,
      metadata: { uploaded_from: "admin_workbench" },
    }));
    form.append("file", uploadFile);
    try {
      const result = await api<{ chunks: number; status: string; pages_needing_ocr?: number[] }>("/api/v1/admin/evidence/uploads", { method: "POST", body: form });
      const ocr = result.pages_needing_ocr?.length ? `; ${result.pages_needing_ocr.length} pages require OCR` : "";
      setUploadNotice(`Extracted ${result.chunks} chunks into mandatory quarantine${ocr}.`);
      setUploadFile(null); setUploadId(""); setUploadTitle("");
      await loadSources();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Evidence upload failed."); }
    finally { setBusy(false); }
  }

  async function loadSources() {
    setBusy(true); setError("");
    try {
      setSources(await api<Source[]>("/api/v1/admin/evidence/sources"));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to connect."); }
    finally { setBusy(false); }
  }

  async function openSource(source: Source) {
    setSelected(source); setChunks(null); setLifecycle([]); setError("");
    const sourceId = encodeURIComponent(source.source_id);
    try {
      const [reviewState, chunkPage, lifecycleEvents] = await Promise.all([
        api<ReviewState>(`/api/v1/admin/evidence/sources/${sourceId}/reviews`),
        api<ChunkPage>(`/api/v1/admin/evidence/sources/${sourceId}/chunks?offset=0&limit=${CHUNK_PAGE_SIZE}`),
        api<LifecycleEvent[]>(`/api/v1/admin/evidence/sources/${sourceId}/lifecycle`),
      ]);
      setState(reviewState); setChunks(chunkPage); setLifecycle(lifecycleEvents);
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load review state."); }
  }

  async function loadChunkPage(offset: number) {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      setChunks(await api<ChunkPage>(`/api/v1/admin/evidence/sources/${encodeURIComponent(selected.source_id)}/chunks?offset=${Math.max(0, offset)}&limit=${CHUNK_PAGE_SIZE}`));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load evidence chunks."); }
    finally { setBusy(false); }
  }

  async function submit(dimension: Dimension, decision: "approved" | "rejected") {
    if (!selected || reviewer.trim().length < 2 || reason.trim().length < 5) {
      setError("Enter the reviewer and a review rationale of at least five characters."); return;
    }
    setBusy(true); setError("");
    try {
      const next = await api<ReviewState>(`/api/v1/admin/evidence/sources/${selected.source_id}/reviews`, {
        method: "POST", body: JSON.stringify({ dimension, decision, reviewer, reason }),
      });
      setState(next);
      setSources((items) => items.map((item) => item.source_id === selected.source_id ? { ...item, review_status: next.review_status } : item));
      setReason("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Review submission failed."); }
    finally { setBusy(false); }
  }

  async function changeLifecycle(status: "quarantined" | "outdated" | "withdrawn") {
    if (!selected || reviewer.trim().length < 2 || reason.trim().length < 5) {
      setError("Enter the responsible person and rationale before changing source availability."); return;
    }
    setBusy(true); setError("");
    try {
      await api(`/api/v1/admin/evidence/sources/${selected.source_id}/lifecycle`, {
        method: "POST", body: JSON.stringify({ status, actor: reviewer, reason }),
      });
      setState((current) => current ? { ...current, review_status: status } : current);
      setSources((items) => items.map((item) => item.source_id === selected.source_id ? { ...item, review_status: status } : item));
      setLifecycle(await api<LifecycleEvent[]>(`/api/v1/admin/evidence/sources/${encodeURIComponent(selected.source_id)}/lifecycle`));
      setReason("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Status change failed."); }
    finally { setBusy(false); }
  }

  const latest = new Map(state?.latest_reviews.map((item) => [item.dimension, item]));
  const extractionAudit = selected?.metadata?.extraction_audit;
  const unresolved = extractionAudit?.pages_needing_ocr ?? extractionAudit?.unresolved_blocks ?? 0;

  return <main className="admin-shell">
    <header className="admin-header"><div><span className="eyebrow">GI-Onco Navigator</span><h1>Evidence governance workbench</h1><p>Every source starts in quarantine and requires all four approvals before patient retrieval.</p></div><a href="/">Return to patient app</a></header>
    <section className="admin-login"><LockKeyhole /><label>Administrator key<input type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} placeholder="Kept only in this page's memory" /></label><button onClick={loadSources} disabled={busy || !adminKey}><RefreshCw size={17} /> Connect and refresh</button></section>
    <section className="evidence-upload">
      <div><Upload /><span><b>Import evidence for review</b><small>PDF, DOCX, SRT, or VTT up to 25 MiB. Upload never publishes content.</small></span></div>
      <label>Source ID<input value={uploadId} onChange={(event) => setUploadId(event.target.value)} placeholder="Example: hospital-video-2026-01" /></label>
      <label>Source title<input value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} placeholder="Complete, recognizable source title" /></label>
      <label>Evidence type<select value={uploadType} onChange={(event) => setUploadType(event.target.value)}><option value="guideline">Clinical guideline</option><option value="peer_reviewed">Peer-reviewed research</option><option value="patient_education">Patient education</option><option value="expert_video">Expert video</option><option value="other">Other</option></select></label>
      <label>Cancer scope<select value={uploadCancer} onChange={(event) => setUploadCancer(event.target.value)}><option value="colon">Colon cancer</option><option value="rectal">Rectal cancer</option><option value="gastric">Gastric cancer</option><option value="other_gi">Other gastrointestinal cancer</option></select></label>
      <label>Copyright state<select value={uploadCopyright} onChange={(event) => setUploadCopyright(event.target.value)}><option value="unknown">Not verified</option><option value="licensed_local_use">Licensed for local use</option><option value="open_license">Open license</option><option value="public_domain">Public domain</option><option value="metadata_only">Metadata only</option></select></label>
      <label className="upload-file">Choose file<input type="file" accept=".pdf,.docx,.srt,.vtt" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} /></label>
      <button onClick={uploadEvidence} disabled={busy || !adminKey || !uploadFile}>Upload to quarantine</button>
      {uploadNotice && <p className="upload-notice" role="status">{uploadNotice}</p>}
    </section>
    {error && <div className="error-message" role="alert">{error}</div>}
    <div className="admin-columns">
      <section className="source-list"><h2>Evidence sources <small>{sources.length}</small></h2>{sources.length === 0 && <p className="admin-empty">Connect to view registered sources.</p>}{sources.map((source) => <button key={source.source_id} onClick={() => openSource(source)} className={selected?.source_id === source.source_id ? "selected" : ""}><span><b>{source.title}</b><small>{source.evidence_type}{source.version ? ` · ${source.version}` : ""}</small></span><em data-status={source.review_status}>{source.review_status}</em></button>)}</section>
      <section className="review-panel">
        {!selected || !state ? <div className="admin-empty"><ClipboardCheck size={40} /><p>Select a source to inspect and record reviews.</p></div> : <>
          <div className="review-title"><div><small>{selected.source_id}</small><h2>{selected.title}</h2></div><strong data-status={state.review_status}>{state.review_status}</strong></div>
          {extractionAudit && <section className="extraction-audit" data-complete={unresolved === 0}><div><b>Extraction completeness</b><strong>{unresolved === 0 ? "Ready for human sampling" : `${unresolved} units remain unresolved`}</strong></div><p>{extractionAudit.pages !== undefined ? `${extractionAudit.pages} pages total; ${extractionAudit.readable_text_pages ?? 0} have readable text.` : extractionAudit.paragraphs !== undefined ? `${extractionAudit.paragraphs} non-empty paragraphs extracted.` : `${extractionAudit.verified_cues ?? extractionAudit.readable_blocks ?? 0} content units checked.`}{unresolved > 0 && " Complete OCR and re-ingest before approving extraction quality."}</p></section>}
          <div className="lifecycle-actions"><span>Emergency source control</span><button onClick={() => changeLifecycle("quarantined")} disabled={busy}>Re-quarantine</button><button onClick={() => changeLifecycle("outdated")} disabled={busy}>Mark outdated</button><button className="reject" onClick={() => changeLifecycle("withdrawn")} disabled={busy}>Withdraw</button></div>
          <div className="reviewer-fields"><label>Reviewer<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Real name or accountable team identifier" /></label><label>Review rationale<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Record scope, findings, and decision rationale" /></label></div>
          {extractionAudit?.human_verified_content_free_pages && <section className="blank-page-review"><b>Human-verified content-free pages</b><p>Pages {extractionAudit.human_verified_content_free_pages.page_numbers.join(", ")} · {extractionAudit.human_verified_content_free_pages.reviewer}</p><small>{extractionAudit.human_verified_content_free_pages.reason}</small></section>}
          <section className="chunk-preview"><h3>Extracted-content sampling <small>{chunks?.total ?? 0} chunks{chunks && chunks.total > 0 ? `; showing ${chunks.offset + 1}–${Math.min(chunks.offset + chunks.items.length, chunks.total)}` : ""}</small></h3>{chunks?.items.length === 0 && <p>This source has no reviewable chunks and cannot be approved from its title alone.</p>}{chunks?.items.map((chunk) => <details key={chunk.chunk_id}><summary><span>Chunk {chunk.ordinal + 1}</span><small>{chunk.page_start ? `Page ${chunk.page_start}${chunk.page_end && chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ""}` : chunk.timestamp_start_seconds !== undefined ? `${chunk.timestamp_start_seconds}–${chunk.timestamp_end_seconds ?? "?"} seconds` : chunk.section_path.join(" / ") || "No locator"} · {chunk.extraction_method}</small></summary><p>{chunk.text}</p><code>SHA-256 {chunk.content_hash}</code></details>)}{chunks && chunks.total > chunks.limit && <div className="chunk-pagination"><button onClick={() => loadChunkPage(chunks.offset - chunks.limit)} disabled={busy || chunks.offset === 0}>Previous</button><span>Page {Math.floor(chunks.offset / chunks.limit) + 1} of {Math.ceil(chunks.total / chunks.limit)}</span><button onClick={() => loadChunkPage(chunks.offset + chunks.limit)} disabled={busy || chunks.offset + chunks.items.length >= chunks.total}>Next</button></div>}</section>
          <section className="lifecycle-history"><h3>Source lifecycle history</h3>{lifecycle.length === 0 ? <p>No lifecycle change has been recorded.</p> : <ol>{lifecycle.map((event) => <li key={event.event_id}><b>{event.previous_status} → {event.new_status}</b><span>{event.actor} · {new Date(event.created_at).toLocaleString("en")}</span><p>{event.reason}</p></li>)}</ol>}</section>
          <div className="review-gates">{state.required_dimensions.map((dimension) => { const item = latest.get(dimension); return <article key={dimension}><div>{item?.decision === "approved" ? <CheckCircle2 /> : <ShieldAlert />}<span><b>{labels[dimension]}</b><small>{item ? `${item.reviewer}: ${item.reason}` : "Not reviewed"}</small></span></div><div><button onClick={() => submit(dimension, "approved")} disabled={busy}>Approve</button><button className="reject" onClick={() => submit(dimension, "rejected")} disabled={busy}>Reject</button></div></article>; })}</div>
        </>}
      </section>
    </div>
  </main>;
}
