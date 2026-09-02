# GI-Onco Navigator

An open-source, evidence-grounded postoperative navigation platform for gastrointestinal cancer patients.

GI-Onco Navigator 将患者结构化档案、术后阶段判断、医学资料治理、可追溯检索和安全边界整合为一个可部署的 Web 应用。它帮助患者理解“目前处于什么阶段、缺少哪些关键信息、复诊时可以讨论什么”，不诊断、不处方，也不替代诊疗团队。

## 当前能力

- 结肠癌、直肠癌、胃癌术后档案与字段校验
- 基于手术日期、病理和当前治疗信息的患者旅程状态机
- 危险症状与个体化治疗指令拦截
- PDF 文本提取、乱码/OCR 需求识别、分页切片与内容哈希
- 来源版本、证据类型、版权状态、审核状态与替代关系管理
- SQLite FTS5 检索、癌种过滤、证据等级排序与页码引用
- 仅使用 `approved` 片段的患者端抽取式回答
- 患者档案、资料注册、问答操作的审计记录
- 响应式 React 患者端，可调用后端完成阶段判断
- Docker、CI、自动测试和可扩展 AI Benchmark

> 默认不连接大模型。患者端保留检索到的原文证据片段，以降低无依据生成风险。模型生成可作为可选层接入，但仍须通过引用和安全校验。

## 快速运行

### Docker（推荐）

```bash
docker compose up --build
```

- 患者端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 本地开发

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn backend.app.main:app --reload
```

在另一个终端运行 `cd frontend`、`pnpm install` 和 `pnpm dev`。

## 资料导入

版权受限的指南和患者资料不会提交到 GitHub。仓库只保存来源清单、哈希、解析程序和允许公开的派生元数据。管理员在本地放置合法取得的 PDF 后运行：

```bash
gi-onco ingest-pdf data/sources/example.json /path/to/source.pdf
```

如果输出中的 `pages_needing_ocr` 非空，该来源不会因“导入成功”自动变为患者端可用；需完成 OCR、逐页质量检查和医学审核，再将切片状态改为 `approved`。

## 证据分层

1. 临床指南
2. 同行评议研究
3. 患者教育材料
4. 专家视频/会议内容
5. 患者社群和其他线索

系统明确显示证据类型、版本和定位信息。社群资料、医院名单和未核验的治疗结论默认隔离，不能直接驱动患者回答。

## 测试与评估

```bash
pytest -q
ruff check backend
gi-onco-benchmark benchmarks/cases
```

Benchmark 当前覆盖患者阶段和安全分类，可继续扩展检索 Recall@k、引用正确率、证据支持率和危险建议率。测试病例均为虚构数据，不含真实患者信息。

## 项目结构

```text
backend/       FastAPI、患者旅程、安全层、资料导入、检索与审计
frontend/      React + TypeScript 患者端
data/          来源元数据与本地资料目录（原始资料默认忽略）
benchmarks/    去标识化评测病例与评估程序
docs/          产品范围、数据库设计与证据治理规范
.github/       持续集成
```

详细说明见 [项目设计](docs/project_design.md)、[数据库设计](docs/database_design.md) 和 [证据治理](docs/evidence_governance.md)。

## 医疗安全与隐私

- 不输出具体患者的药物、方案、剂量或停药指令。
- 识别到可能的紧急症状时停止普通问答，并提示及时医疗评估。
- 未检索到已审核证据时明确拒答，不以模型常识补全。
- 不应将真实患者身份信息提交到公共仓库；生产部署还需身份认证、加密、访问控制、备份和合规审查。
- 本项目用于患者教育与就诊准备，不构成医疗建议。

## 贡献与许可

欢迎贡献代码、公开许可的资料元数据、解析器和虚构测试病例。新增医学内容必须注明来源、版本、版权状态与审核人，不能通过普通代码合并直接成为患者端已审核证据。

代码许可将在首次正式发布前确定；第三方医学资料始终遵循其各自版权和许可，不因本仓库而重新授权。
