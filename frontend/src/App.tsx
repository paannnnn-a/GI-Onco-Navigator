import { ArrowRight, BookOpen, FileCheck2, HeartPulse, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

type CancerType = "colon" | "rectal" | "gastric";

const pathways: Record<CancerType, { title: string; subtitle: string }> = {
  colon: { title: "结肠癌术后导航", subtitle: "整理病理信息、定位阶段并准备复诊问题" },
  rectal: { title: "直肠癌术后导航", subtitle: "关注病理、后续治疗评估与功能恢复" },
  gastric: { title: "胃癌术后导航", subtitle: "匹配术后阶段、营养与随访教育资料" },
};

export function App() {
  const [cancerType, setCancerType] = useState<CancerType>("colon");
  const [showProfile, setShowProfile] = useState(false);
  const [surgeryDate, setSurgeryDate] = useState("");
  const [stage, setStage] = useState("");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const selected = useMemo(() => pathways[cancerType], [cancerType]);

  async function assess() {
    setLoading(true);
    setResult("");
    try {
      const response = await fetch("/api/v1/journey/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: crypto.randomUUID(),
          cancer_type: cancerType,
          surgery_date: surgeryDate || null,
          pathological_stage: stage || null,
        }),
      });
      if (!response.ok) throw new Error("服务暂时不可用");
      const data = await response.json();
      setResult(`${data.explanation}\n\n建议与医生讨论：\n${data.next_discussion_topics.map((x: string) => `• ${x}`).join("\n")}`);
    } catch (error) {
      setResult(error instanceof Error ? error.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="GI-Onco Navigator 首页">
          <span className="brand-mark"><HeartPulse size={21} /></span>
          <span>GI-Onco Navigator</span>
        </a>
        <nav aria-label="主导航">
          <a href="#journey">我的阶段</a>
          <a href="#evidence">循证资料</a>
          <a href="#safety">安全说明</a>
        </nav>
      </header>

      <section id="top" className="hero">
        <div className="eyebrow">胃肠肿瘤术后循证导航</div>
        <h1>把复杂资料，整理成<br /><em>下一步能讨论的问题</em></h1>
        <p className="hero-copy">
          根据你的术后档案，从经过审核的指南、患者教育材料和专家内容中查找相关信息，
          清楚展示来源、适用范围和仍需确认的事项。
        </p>
        <div className="notice"><ShieldCheck size={18} /> 本平台提供信息导航，不诊断、不处方、不替代医生。</div>
      </section>

      <section id="journey" className="workspace">
        <div className="section-heading">
          <span>01</span>
          <div><h2>从你的情况开始</h2><p>先选择癌种，随后逐步完善术后档案。</p></div>
        </div>
        <div className="cancer-grid" role="radiogroup" aria-label="选择癌种">
          {(Object.keys(pathways) as CancerType[]).map((key) => (
            <button
              key={key}
              className={cancerType === key ? "cancer-card active" : "cancer-card"}
              onClick={() => setCancerType(key)}
              role="radio"
              aria-checked={cancerType === key}
            >
              <span className="card-index">{key === "colon" ? "01" : key === "rectal" ? "02" : "03"}</span>
              <strong>{pathways[key].title}</strong>
              <small>{pathways[key].subtitle}</small>
              <ArrowRight size={20} />
            </button>
          ))}
        </div>
        <div className="selected-path">
          <div><span>已选择</span><strong>{selected.title}</strong></div>
          <button onClick={() => setShowProfile((value) => !value)}>建立我的术后档案 <ArrowRight size={18} /></button>
        </div>
        {showProfile && (
          <div className="profile-panel">
            <div><label htmlFor="surgery-date">手术日期</label><input id="surgery-date" type="date" value={surgeryDate} onChange={(e) => setSurgeryDate(e.target.value)} /></div>
            <div><label htmlFor="stage">病理分期（如 III 期）</label><input id="stage" value={stage} onChange={(e) => setStage(e.target.value)} placeholder="尚不清楚可留空" /></div>
            <button onClick={assess} disabled={loading}>{loading ? "正在整理…" : "判断当前阶段"}</button>
            {result && <pre className="assessment-result">{result}</pre>}
          </div>
        )}
      </section>

      <section id="evidence" className="evidence-band">
        <div className="section-heading light">
          <span>02</span><div><h2>每个结论都有来处</h2><p>不同类型的证据不会混在一起。</p></div>
        </div>
        <div className="evidence-grid">
          <article><FileCheck2 /><b>临床指南</b><p>展示版本、章节和原文页码。</p></article>
          <article><BookOpen /><b>患者教育</b><p>把专业内容转成可理解的解释。</p></article>
          <article><HeartPulse /><b>专家内容</b><p>保留医院、会议和视频时间戳。</p></article>
        </div>
      </section>

      <section id="safety" className="safety">
        <ShieldCheck size={34} />
        <div><h2>安全边界</h2><p>出现危险症状时优先提示及时就医；涉及具体药物、方案或剂量时，引导你与诊疗团队确认。</p></div>
      </section>
    </main>
  );
}
