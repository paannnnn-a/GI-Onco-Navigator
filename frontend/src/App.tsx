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
  citations: { title: string; version?: string; page_start?: number; excerpt?: string }[];
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
  colon: { title: "结肠癌术后导航", subtitle: "整理病理信息、定位阶段并准备复诊问题" },
  rectal: { title: "直肠癌术后导航", subtitle: "关注病理、后续治疗评估与功能恢复" },
  gastric: { title: "胃癌术后导航", subtitle: "匹配术后阶段、营养与随访教育资料" },
};

const statusNames: Record<string, string> = {
  postoperative_recovery: "早期术后恢复",
  pathology_review: "病理资料整理",
  adjuvant_evaluation: "后续治疗评估",
  active_treatment: "治疗进行中",
  surveillance: "随访阶段",
  rehabilitation: "康复阶段",
  unknown: "信息不足，暂无法判断",
};

async function postJson<T>(url: string, body: object): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = data?.detail?.message ?? data?.detail ?? "服务暂时不可用";
    throw new Error(typeof message === "string" ? message : "请求未完成");
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
    fetch(`/api/v1/patients/${patientAccess.patient_id}/reminders`, {
      headers: { "Authorization": `Bearer ${patientAccess.access_token}` },
    }).then((response) => response.ok ? response.json() : []).then(setReminders).catch(() => undefined);
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
      setError(caught instanceof Error ? caught.message : "请求失败");
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
      setError(caught instanceof Error ? caught.message : "请求失败");
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
    } catch (caught) { setError(caught instanceof Error ? caught.message : "查询失败"); }
    finally { setLoading(false); }
  }

  async function saveRecord() {
    if (!saveConsent) { setError("请先勾选明确同意保存本次结构化档案。"); return; }
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
      if (!response.ok) throw new Error("档案保存失败，请稍后重试。");
      setRecordStatus("档案已保存；访问凭证仅保留在当前浏览器会话中。你可以随时删除。 ");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "保存失败"); }
    finally { setLoading(false); }
  }

  async function deleteRecord() {
    if (!patientAccess) return;
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/v1/patients/${patientAccess.patient_id}`, {
        method: "DELETE", headers: { "Authorization": `Bearer ${patientAccess.access_token}` },
      });
      if (!response.ok) throw new Error("档案删除失败，请稍后重试。");
      sessionStorage.removeItem("gi-onco-patient-access"); setPatientAccess(null);
      setSaveConsent(false); setRecordStatus("服务器中的结构化档案已删除。");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "删除失败"); }
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
      if (!response.ok) throw new Error("复诊事项保存失败，请确认档案已保存。");
      const reminder = await response.json() as PatientReminder;
      setReminders((items) => [...items, reminder].sort((a, b) => a.due_at.localeCompare(b.due_at)));
      setReminderTitle(""); setReminderDate(""); setReminderSource("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "保存失败"); }
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
        <a className="brand" href="#top" aria-label="GI-Onco Navigator 首页">
          <span className="brand-mark"><HeartPulse size={21} /></span><span>GI-Onco Navigator</span>
        </a>
        <nav aria-label="主导航"><a href="#journey">我的阶段</a><a href="#evidence">循证提问</a><a href="#safety">安全说明</a></nav>
      </header>

      <section id="top" className="hero">
        <div className="eyebrow">胃肠肿瘤术后循证导航</div>
        <h1>把复杂资料，整理成<br /><em>下一步能讨论的问题</em></h1>
        <p className="hero-copy">根据你的术后档案，从经过审核的指南、患者教育材料和专家内容中查找相关信息，清楚展示来源、适用范围和仍需确认的事项。</p>
        <div className="notice"><ShieldCheck size={18} /> 本平台提供信息导航，不诊断、不处方、不替代医生。</div>
      </section>

      <section id="journey" className="workspace">
        <div className="section-heading"><span>01</span><div><h2>从你的情况开始</h2><p>先选择癌种，再完善用于导航的术后信息。</p></div></div>
        <div className="cancer-grid" role="radiogroup" aria-label="选择癌种">
          {(Object.keys(pathways) as CancerType[]).map((key, index) => (
            <button key={key} className={cancerType === key ? "cancer-card active" : "cancer-card"} onClick={() => setCancerType(key)} role="radio" aria-checked={cancerType === key}>
              <span className="card-index">0{index + 1}</span><strong>{pathways[key].title}</strong><small>{pathways[key].subtitle}</small><ArrowRight size={20} />
            </button>
          ))}
        </div>
        <div className="selected-path"><div><span>已选择</span><strong>{selected.title}</strong></div><button onClick={() => setShowProfile(true)}>建立我的术后档案 <ArrowRight size={18} /></button></div>

        {showProfile && (
          <div className="profile-panel full">
            <div><label htmlFor="surgery-date">手术日期</label><input id="surgery-date" type="date" value={surgeryDate} onChange={(event) => setSurgeryDate(event.target.value)} /></div>
            <div><label htmlFor="stage">病理分期</label><input id="stage" value={stage} onChange={(event) => setStage(event.target.value)} placeholder="例如 III 期；不清楚可留空" /></div>
            <div><label htmlFor="margin">切缘状态</label><input id="margin" value={margin} onChange={(event) => setMargin(event.target.value)} placeholder="例如 R0；以病理报告为准" /></div>
            <div><label htmlFor="mmr">MMR / MSI 状态</label><input id="mmr" value={mmr} onChange={(event) => setMmr(event.target.value)} placeholder="例如 pMMR；不清楚可留空" /></div>
            <div><label htmlFor="treatment">当前治疗记录</label><input id="treatment" value={treatment} onChange={(event) => setTreatment(event.target.value)} placeholder="只记录医生已确定的治疗" /></div>
            <div><label htmlFor="symptoms">当前症状</label><input id="symptoms" value={symptoms} onChange={(event) => setSymptoms(event.target.value)} placeholder="多个症状用逗号分隔" /></div>
            <div><label htmlFor="province">所在省份</label><input id="province" value={province} onChange={(event) => setProvince(event.target.value)} placeholder="例如 山东省" /></div>
            <div><label htmlFor="city">所在城市</label><input id="city" value={city} onChange={(event) => setCity(event.target.value)} placeholder="例如 济南市" /></div>
            <label className="check-field"><input type="checkbox" checked={crossProvince} onChange={(event) => setCrossProvince(event.target.checked)} />愿意查看跨省机构信息</label>
            <label className="check-field consent"><input type="checkbox" checked={saveConsent} onChange={(event) => setSaveConsent(event.target.checked)} />我明确同意将以上结构化信息保存到当前部署的服务器；不包含姓名、证件号或手机号。</label>
            <button className="primary" onClick={createPlan} disabled={loading}>{loading ? "正在整理…" : "生成导航计划"}</button>
            <button className="secondary" onClick={saveRecord} disabled={loading || !saveConsent}>保存我的档案</button>
            {patientAccess && <button className="danger-link" onClick={deleteRecord} disabled={loading}>删除服务器档案</button>}
            {recordStatus && <div className="record-status" role="status">{recordStatus}</div>}
            {patientAccess && <section className="reminder-editor"><h3>按诊疗团队安排记录复诊事项</h3><p>平台不会自行计算医学随访时间；请只录入预约通知或诊疗团队已经确认的日期。</p><input value={reminderTitle} onChange={(event) => setReminderTitle(event.target.value)} placeholder="事项，例如复诊或检查" /><input type="datetime-local" value={reminderDate} onChange={(event) => setReminderDate(event.target.value)} /><input value={reminderSource} onChange={(event) => setReminderSource(event.target.value)} placeholder="日期来源，例如门诊预约通知" /><button className="secondary" onClick={addReminder} disabled={loading || !reminderTitle || !reminderDate || !reminderSource}>保存事项</button>{reminders.map((reminder) => <article key={reminder.reminder_id} data-complete={reminder.status === "completed"}><div><b>{reminder.title}</b><small>{new Date(reminder.due_at).toLocaleString("zh-CN")} · {reminder.source_note}</small></div>{reminder.status === "pending" && <button onClick={() => completeReminder(reminder)}>标记完成</button>}</article>)}</section>}
            {error && <div className="error-message" role="alert">{error}</div>}
          </div>
        )}

        {plan && (
          <div className="plan" aria-live="polite">
            <div className="status-card"><small>系统整理出的当前阶段</small><h3>{statusNames[plan.assessment.current_status] ?? plan.assessment.current_status}</h3><p>{plan.assessment.explanation}</p></div>
            {plan.assessment.missing_information.length > 0 && <div className="missing"><strong>建议补充或向医生确认</strong><ul>{plan.assessment.missing_information.map((item) => <li key={item.patient_friendly_label}>{item.patient_friendly_label}：{item.reason}</li>)}</ul></div>}
            <div className="topic-grid">{plan.topics.map((topic) => <article key={topic.category}><span>{topic.title}</span><p>{topic.purpose}</p><ul>{topic.suggested_questions.map((item) => <li key={item}>{item}</li>)}</ul></article>)}</div>
          </div>
        )}
        {plan && <div className="facility-box">
          <div><h3>机构信息筛选</h3><p>只按地点和已核验的公开服务标签筛选，不提供医院或医生排名。</p></div>
          <label htmlFor="services">希望了解的服务</label>
          <input id="services" value={desiredServices} onChange={(event) => setDesiredServices(event.target.value)} placeholder="例如 营养门诊、造口门诊、多学科门诊" />
          <button className="primary" onClick={findFacilities} disabled={loading}>查询核验信息</button>
          {facilities && <div className="facility-results"><p>{facilities.notice}</p>{facilities.matches.length === 0 ? <div className="empty-evidence">当前目录没有符合条件且已核验的机构。可前往<a href={facilities.official_registry_url} target="_blank" rel="noreferrer">国家卫生健康委医院执业登记查询</a>自行核实。</div> : facilities.matches.map((item) => <article key={item.facility_id}><h4>{item.name}</h4><small>{item.province} · {item.city}</small><ul>{item.matched_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>{item.unmatched_services.length > 0 && <p>尚未核实：{item.unmatched_services.join("、")}</p>}<a href={item.official_registration_url} target="_blank" rel="noreferrer">查看官方登记</a><p className="facility-disclaimer">{item.disclaimer}</p></article>)}</div>}
        </div>}
      </section>

      <section id="evidence" className="evidence-band">
        <div className="section-heading light"><span>02</span><div><h2>每个结论都有来处</h2><p>只有经过审核并带有定位信息的证据才能进入回答。</p></div></div>
        <div className="evidence-grid"><article><FileCheck2 /><b>临床指南</b><p>展示版本、章节和原文页码。</p></article><article><BookOpen /><b>患者教育</b><p>把专业内容转成可理解的解释。</p></article><article><HeartPulse /><b>专家内容</b><p>保留医院、会议和视频时间戳。</p></article></div>
        <div className="question-box">
          <label htmlFor="question">输入一个用于了解信息或准备复诊的问题</label>
          <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="例如：复诊时需要准备哪些资料？" />
          <button onClick={askQuestion} disabled={loading || !question.trim()}>检索已审核证据</button>
          {answer && <div className="answer"><h3>循证导航结果</h3><p>{answer.answer}</p>{answer.citations.length > 0 ? <ol>{answer.citations.map((citation, index) => <li key={`${citation.title}-${index}`}><strong>{citation.title}</strong>{citation.version && ` · ${citation.version}`}{citation.page_start && ` · 第 ${citation.page_start} 页`}</li>)}</ol> : <div className="empty-evidence">当前没有足够的已审核证据，系统已安全拒答。</div>}</div>}
        </div>
      </section>

      <section id="safety" className="safety"><ShieldCheck size={34} /><div><h2>安全边界</h2><p>出现危险症状时优先提示及时就医；涉及具体药物、方案或剂量时，引导你与诊疗团队确认。请勿在演示系统输入姓名、身份证号、手机号等身份信息。</p></div></section>
    </main>
  );
}
