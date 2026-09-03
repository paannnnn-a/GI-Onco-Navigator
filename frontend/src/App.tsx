import { ArrowRight, BookOpen, FileCheck2, HeartPulse, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type CancerType = "colon" | "rectal" | "gastric";
type Profile = {
  patient_id: string;
  cancer_type: CancerType;
  surgery_date: string | null;
  pathological_stage: string | null;
  margin_status: string | null;
  mismatch_repair_status: string | null;
  current_treatment: string | null;
  symptoms: string[];
  province: string | null;
  city: string | null;
  accepts_cross_province_care: boolean;
  consent_to_store: boolean;
};
type Topic = { category: string; title: string; purpose: string; suggested_questions: string[] };
type Plan = {
  assessment: {
    current_status: string;
    explanation: string;
    missing_information: { patient_friendly_label: string; reason: string }[];
  };
  topics: Topic[];
  safety_notice: string;
};
type Answer = {
  answer: string;
  citations: {
    source_id: string; title: string; evidence_type: string; version?: string;
    page_start?: number; page_end?: number; timestamp_start_seconds?: number;
    excerpt?: string; public_url?: string; section_path: string[]; review_status: string;
  }[];
  limitations: string[];
};
type FacilityResponse = {
  matches: { facility_id: string; name: string; province: string; city: string; matched_reasons: string[]; unmatched_services: string[]; official_registration_url: string; official_website?: string; disclaimer: string }[];
  official_registry_url: string;
  notice: string;
};
type PatientAccess = { patient_id: string; access_token: string; expires_at: string };
type PatientReminder = { reminder_id: string; title: string; due_at: string; source_note: string; status: string };

const pathways: Record<CancerType, { title: string; subtitle: string }> = {
  colon: { title: "Colon cancer navigation", subtitle: "Organize pathology, understand your phase, and prepare visit questions" },
  rectal: { title: "Rectal cancer navigation", subtitle: "Focus on pathology, treatment evaluation, and functional recovery" },
  gastric: { title: "Gastric cancer navigation", subtitle: "Connect your postoperative phase with nutrition and follow-up education" },
};

const statusNames: Record<string, string> = {
  postoperative_recovery: "Early postoperative recovery",
  pathology_review: "Pathology information preparation",
  adjuvant_evaluation: "Postoperative treatment evaluation",
  active_treatment: "Active treatment",
  surveillance: "Surveillance",
  rehabilitation: "Rehabilitation",
  unknown: "Not enough information to determine a phase",
};

const evidenceNames: Record<string, string> = {
  guideline: "Clinical guideline", peer_reviewed: "Peer-reviewed research", patient_education: "Patient education",
  expert_video: "Expert video", other: "Other material",
};

export function citationLocator(citation: Answer["citations"][number]): string {
  if (citation.page_start) {
    return `Page ${citation.page_start}${citation.page_end && citation.page_end !== citation.page_start ? `–${citation.page_end}` : ""}`;
  }
  if (citation.timestamp_start_seconds !== undefined) return `Video at ${citation.timestamp_start_seconds} seconds`;
  if (citation.section_path.length) return citation.section_path.join(" / ");
  return "Locator unavailable";
}

async function postJson<T>(url: string, body: object): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = data?.detail?.message ?? data?.detail ?? "The service is temporarily unavailable.";
    throw new Error(typeof message === "string" ? message : "The request could not be completed.");
  }
  return data as T;
}

export function App() {
  const [cancerType, setCancerType] = useState<CancerType>("colon");
  const [showProfile, setShowProfile] = useState(false);
  const [surgeryDate, setSurgeryDate] = useState("");
  const [stage, setStage] = useState("");
  const [margin, setMargin] = useState("");
  const [mmr, setMmr] = useState("");
  const [treatment, setTreatment] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [crossProvince, setCrossProvince] = useState(false);
  const [desiredServices, setDesiredServices] = useState("");
  const [facilities, setFacilities] = useState<FacilityResponse | null>(null);
  const [saveConsent, setSaveConsent] = useState(false);
  const [patientAccess, setPatientAccess] = useState<PatientAccess | null>(() => {
    try { return JSON.parse(sessionStorage.getItem("gi-onco-patient-access") ?? "null"); }
    catch { return null; }
  });
  const [recordStatus, setRecordStatus] = useState("");
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderDate, setReminderDate] = useState("");
  const [reminderSource, setReminderSource] = useState("");
  const [reminders, setReminders] = useState<PatientReminder[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const selected = useMemo(() => pathways[cancerType], [cancerType]);

  useEffect(() => {
    if (!patientAccess) return;
    const headers = { "Authorization": `Bearer ${patientAccess.access_token}` };
    async function restoreSession() {
      try {
        const [recordResponse, reminderResponse] = await Promise.all([
          fetch(`/api/v1/patients/${patientAccess!.patient_id}`, { headers }),
          fetch(`/api/v1/patients/${patientAccess!.patient_id}/reminders`, { headers }),
        ]);
        if ([401, 403].includes(recordResponse.status) || [401, 403].includes(reminderResponse.status)) {
          sessionStorage.removeItem("gi-onco-patient-access"); setPatientAccess(null);
          setRecordStatus("The access token expired. Save the profile again when needed."); return;
        }
        if (recordResponse.ok) {
          const record = await recordResponse.json() as Profile;
          setCancerType(record.cancer_type); setSurgeryDate(record.surgery_date ?? "");
          setStage(record.pathological_stage ?? ""); setMargin(record.margin_status ?? "");
          setMmr(record.mismatch_repair_status ?? ""); setTreatment(record.current_treatment ?? "");
          setSymptoms(record.symptoms.join("、")); setProvince(record.province ?? "");
          setCity(record.city ?? ""); setCrossProvince(Boolean(record.accepts_cross_province_care));
          setSaveConsent(Boolean(record.consent_to_store)); setShowProfile(true);
          setRecordStatus("The profile saved in this browser session was restored from the server.");
        }
        if (reminderResponse.ok) setReminders(await reminderResponse.json() as PatientReminder[]);
      } catch { setRecordStatus("The saved profile could not be restored; the local access token remains available."); }
    }
    void restoreSession();
  }, [patientAccess]);

  function profile(): Profile {
    return {
      patient_id: patientAccess?.patient_id ?? "local-demo-patient",
      cancer_type: cancerType,
      surgery_date: surgeryDate || null,
      pathological_stage: stage || null,
      margin_status: margin || null,
      mismatch_repair_status: mmr || null,
      current_treatment: treatment || null,
      symptoms: symptoms.split(/[，,、]/).map((value) => value.trim()).filter(Boolean),
      province: province || null,
      city: city || null,
      accepts_cross_province_care: crossProvince,
      consent_to_store: saveConsent,
    };
  }

  async function createPlan() {
    setLoading(true);
    setError("");
    try {
      setPlan(await postJson<Plan>("/api/v1/navigation/plan", profile()));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function askQuestion() {
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(await postJson<Answer>("/api/v1/navigation/question", { question, patient: profile() }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function findFacilities() {
    setLoading(true); setError("");
    try {
      setFacilities(await postJson<FacilityResponse>("/api/v1/facilities/match", {
        patient: profile(),
        desired_services: desiredServices.split(/[，,、]/).map((value) => value.trim()).filter(Boolean),
      }));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Search failed."); }
    finally { setLoading(false); }
  }

  async function saveRecord() {
    if (!saveConsent) { setError("Provide explicit consent before saving this structured profile."); return; }
    setLoading(true); setError(""); setRecordStatus("");
    try {
      let access = patientAccess;
      if (!access) {
        access = await postJson<PatientAccess>("/api/v1/patient-access", {});
        sessionStorage.setItem("gi-onco-patient-access", JSON.stringify(access));
        setPatientAccess(access);
      }
      const record = { ...profile(), patient_id: access.patient_id, consent_to_store: true };
      const response = await fetch(`/api/v1/patients/${access.patient_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${access.access_token}` },
        body: JSON.stringify(record),
      });
      if (!response.ok) throw new Error("The profile could not be saved. Try again later.");
      setRecordStatus("Profile saved. The access token remains only in this browser session, and you can delete the profile at any time.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Save failed."); }
    finally { setLoading(false); }
  }

  async function deleteRecord() {
    if (!patientAccess) return;
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/v1/patients/${patientAccess.patient_id}`, {
        method: "DELETE", headers: { "Authorization": `Bearer ${patientAccess.access_token}` },
      });
      if (!response.ok) throw new Error("The profile could not be deleted. Try again later.");
      sessionStorage.removeItem("gi-onco-patient-access"); setPatientAccess(null);
      setSaveConsent(false); setRecordStatus("The structured profile was deleted from the server.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Delete failed."); }
    finally { setLoading(false); }
  }

  async function exportRecord() {
    if (!patientAccess) return;
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/v1/patients/${patientAccess.patient_id}/export`, {
        headers: { "Authorization": `Bearer ${patientAccess.access_token}` },
      });
      if (!response.ok) throw new Error("Profile export failed. Confirm that the access token is still valid.");
      const blob = new Blob([await response.text()], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `gi-onco-record-${patientAccess.patient_id}.json`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
      setRecordStatus("Profile and reminders exported. The file does not contain the access token.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Export failed."); }
    finally { setLoading(false); }
  }

  async function addReminder() {
    if (!patientAccess || !reminderTitle.trim() || !reminderDate || !reminderSource.trim()) return;
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/v1/patients/${patientAccess.patient_id}/reminders`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${patientAccess.access_token}` },
        body: JSON.stringify({ title: reminderTitle, due_at: new Date(reminderDate).toISOString(), source_note: reminderSource }),
      });
      if (!response.ok) throw new Error("The reminder could not be saved. Confirm that the profile has been saved.");
      const reminder = await response.json() as PatientReminder;
      setReminders((items) => [...items, reminder].sort((a, b) => a.due_at.localeCompare(b.due_at)));
      setReminderTitle(""); setReminderDate(""); setReminderSource("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Save failed."); }
    finally { setLoading(false); }
  }

  async function completeReminder(reminder: PatientReminder) {
    if (!patientAccess) return;
    const response = await fetch(`/api/v1/patients/${patientAccess.patient_id}/reminders/${reminder.reminder_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${patientAccess.access_token}` },
      body: JSON.stringify({ status: "completed" }),
    });
    if (response.ok) setReminders((items) => items.map((item) => item.reminder_id === reminder.reminder_id ? { ...item, status: "completed" } : item));
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="GI-Onco Navigator home">
          <span className="brand-mark"><HeartPulse size={21} /></span><span>GI-Onco Navigator</span>
        </a>
        <nav aria-label="Main navigation"><a href="#journey">My journey</a><a href="#evidence">Evidence search</a><a href="#safety">Safety</a></nav>
      </header>

      <section id="top" className="hero">
        <div className="eyebrow">Evidence-grounded gastrointestinal cancer navigation</div>
        <h1>Turn complex information into<br /><em>questions you can discuss next</em></h1>
        <p className="hero-copy">Use your postoperative profile to find relevant information in reviewed guidance, patient education, and expert material, with clear provenance, scope, and remaining uncertainties.</p>
        <div className="notice"><ShieldCheck size={18} /> Information navigation only. No diagnosis, prescription, or replacement for your clinical team.</div>
      </section>

      <section id="journey" className="workspace">
        <div className="section-heading"><span>01</span><div><h2>Start with your situation</h2><p>Select a cancer type, then add the postoperative details used for navigation.</p></div></div>
        <div className="cancer-grid" role="radiogroup" aria-label="Select cancer type">
          {(Object.keys(pathways) as CancerType[]).map((key, index) => (
            <button key={key} className={cancerType === key ? "cancer-card active" : "cancer-card"} onClick={() => setCancerType(key)} role="radio" aria-checked={cancerType === key}>
              <span className="card-index">0{index + 1}</span><strong>{pathways[key].title}</strong><small>{pathways[key].subtitle}</small><ArrowRight size={20} />
            </button>
          ))}
        </div>
        <div className="selected-path"><div><span>Selected</span><strong>{selected.title}</strong></div><button onClick={() => setShowProfile(true)}>Build my postoperative profile <ArrowRight size={18} /></button></div>

        {showProfile && (
          <div className="profile-panel full">
            <div><label htmlFor="surgery-date">Surgery date</label><input id="surgery-date" type="date" value={surgeryDate} onChange={(event) => setSurgeryDate(event.target.value)} /></div>
            <div><label htmlFor="stage">Pathological stage</label><input id="stage" value={stage} onChange={(event) => setStage(event.target.value)} placeholder="Example: stage III; leave blank if unknown" /></div>
            <div><label htmlFor="margin">Margin status</label><input id="margin" value={margin} onChange={(event) => setMargin(event.target.value)} placeholder="Example: R0; use the pathology report" /></div>
            <div><label htmlFor="mmr">MMR / MSI status</label><input id="mmr" value={mmr} onChange={(event) => setMmr(event.target.value)} placeholder="Example: pMMR; leave blank if unknown" /></div>
            <div><label htmlFor="treatment">Current treatment record</label><input id="treatment" value={treatment} onChange={(event) => setTreatment(event.target.value)} placeholder="Record only treatment confirmed by your clinical team" /></div>
            <div><label htmlFor="symptoms">Current symptoms</label><input id="symptoms" value={symptoms} onChange={(event) => setSymptoms(event.target.value)} placeholder="Separate multiple symptoms with commas" /></div>
            <div><label htmlFor="province">State or province</label><input id="province" value={province} onChange={(event) => setProvince(event.target.value)} placeholder="Example: Shandong" /></div>
            <div><label htmlFor="city">City</label><input id="city" value={city} onChange={(event) => setCity(event.target.value)} placeholder="Example: Jinan" /></div>
            <label className="check-field"><input type="checkbox" checked={crossProvince} onChange={(event) => setCrossProvince(event.target.checked)} />Show facilities outside my state or province</label>
            <label className="check-field consent"><input type="checkbox" checked={saveConsent} onChange={(event) => setSaveConsent(event.target.checked)} />I explicitly consent to storing this structured profile on the current deployment. Do not include names, government IDs, or phone numbers.</label>
            <button className="primary" onClick={createPlan} disabled={loading}>{loading ? "Preparing…" : "Create navigation plan"}</button>
            <button className="secondary" onClick={saveRecord} disabled={loading || !saveConsent}>Save my profile</button>
            {patientAccess && <button className="secondary" onClick={exportRecord} disabled={loading}>Export my data</button>}
            {patientAccess && <button className="danger-link" onClick={deleteRecord} disabled={loading}>Delete server profile</button>}
            {recordStatus && <div className="record-status" role="status">{recordStatus}</div>}
            {patientAccess && <section className="reminder-editor"><h3>Record dates supplied by your clinical team</h3><p>The platform does not calculate medical follow-up schedules. Enter only dates confirmed in an appointment notice or by your clinical team.</p><input value={reminderTitle} onChange={(event) => setReminderTitle(event.target.value)} placeholder="Item, such as a visit or test" /><input type="datetime-local" value={reminderDate} onChange={(event) => setReminderDate(event.target.value)} /><input value={reminderSource} onChange={(event) => setReminderSource(event.target.value)} placeholder="Date source, such as an appointment notice" /><button className="secondary" onClick={addReminder} disabled={loading || !reminderTitle || !reminderDate || !reminderSource}>Save reminder</button>{reminders.map((reminder) => <article key={reminder.reminder_id} data-complete={reminder.status === "completed"}><div><b>{reminder.title}</b><small>{new Date(reminder.due_at).toLocaleString("en")} · {reminder.source_note}</small></div>{reminder.status === "pending" && <button onClick={() => completeReminder(reminder)}>Mark complete</button>}</article>)}</section>}
            {error && <div className="error-message" role="alert">{error}</div>}
          </div>
        )}

        {plan && (
          <div className="plan" aria-live="polite">
            <div className="status-card"><small>Current phase organized by the system</small><h3>{statusNames[plan.assessment.current_status] ?? plan.assessment.current_status}</h3><p>{plan.assessment.explanation}</p></div>
            {plan.assessment.missing_information.length > 0 && <div className="missing"><strong>Information to add or confirm with your clinician</strong><ul>{plan.assessment.missing_information.map((item) => <li key={item.patient_friendly_label}>{item.patient_friendly_label}: {item.reason}</li>)}</ul></div>}
            <div className="topic-grid">{plan.topics.map((topic) => <article key={topic.category}><span>{topic.title}</span><p>{topic.purpose}</p><ul>{topic.suggested_questions.map((item) => <li key={item}>{item}</li>)}</ul></article>)}</div>
          </div>
        )}
        {plan && <div className="facility-box">
          <div><h3>Facility information filter</h3><p>Filters only by location and verified public service attributes. It does not rank hospitals or clinicians.</p></div>
          <label htmlFor="services">Services of interest</label>
          <input id="services" value={desiredServices} onChange={(event) => setDesiredServices(event.target.value)} placeholder="Example: nutrition, stoma care, multidisciplinary clinic" />
          <button className="primary" onClick={findFacilities} disabled={loading}>Search verified information</button>
          {facilities && <div className="facility-results"><p>{facilities.notice}</p>{facilities.matches.length === 0 ? <div className="empty-evidence">No verified facility in the current directory matches these filters. Check the <a href={facilities.official_registry_url} target="_blank" rel="noreferrer">official National Health Commission register</a>.</div> : facilities.matches.map((item) => <article key={item.facility_id}><h4>{item.name}</h4><small>{item.province} · {item.city}</small><ul>{item.matched_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>{item.unmatched_services.length > 0 && <p>Not verified: {item.unmatched_services.join(", ")}</p>}<a href={item.official_registration_url} target="_blank" rel="noreferrer">View official registration</a><p className="facility-disclaimer">{item.disclaimer}</p></article>)}</div>}
        </div>}
      </section>

      <section id="evidence" className="evidence-band">
        <div className="section-heading light"><span>02</span><div><h2>Every statement has provenance</h2><p>Only reviewed evidence with a valid locator can support an answer.</p></div></div>
        <div className="evidence-grid"><article><FileCheck2 /><b>Clinical guidance</b><p>Shows edition, section, and original page.</p></article><article><BookOpen /><b>Patient education</b><p>Supports understandable explanations of specialist material.</p></article><article><HeartPulse /><b>Expert material</b><p>Retains institution, meeting, and video timestamps.</p></article></div>
        <div className="question-box">
          <label htmlFor="question">Ask an information or visit-preparation question</label>
          <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Example: What information should I prepare for my next visit?" />
          <button onClick={askQuestion} disabled={loading || !question.trim()}>Search approved evidence</button>
          {answer && <div className="answer"><h3>Evidence navigation result</h3><p>{answer.answer}</p>{answer.citations.length > 0 ? <ol className="citation-list">{answer.citations.map((citation) => <li key={citation.source_id}><div><span>{evidenceNames[citation.evidence_type] ?? citation.evidence_type}</span><strong>{citation.public_url ? <a href={citation.public_url} target="_blank" rel="noreferrer">{citation.title}</a> : citation.title}</strong><small>{citation.version && `${citation.version} · `}{citationLocator(citation)} · Reviewed</small></div>{citation.excerpt && <blockquote>{citation.excerpt}</blockquote>}</li>)}</ol> : <div className="empty-evidence">There is not enough approved evidence. The system failed closed.</div>}{answer.limitations.length > 0 && <div className="answer-limitations"><strong>Important limitations</strong><ul>{answer.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>}</div>}
        </div>
      </section>

      <section id="safety" className="safety"><ShieldCheck size={34} /><div><h2>Safety boundary</h2><p>Potential emergency symptoms prompt timely medical assessment. Questions about a specific drug, regimen, or dose are redirected to the treating team. Do not enter names, government IDs, phone numbers, or other identifying information in a demonstration deployment.</p></div></section>
    </main>
  );
}
