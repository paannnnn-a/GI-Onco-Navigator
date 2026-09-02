import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.schemas import (
    EvidenceReviewRequest,
    EvidenceReviewState,
    EvidenceSourceCreate,
    JourneyAssessment,
    NavigationAnswer,
    PatientNavigationPlan,
    PatientProfile,
)
from backend.app.services.citation_guard import CitationValidationError, validate_citations
from backend.app.services.journey import assess_journey
from backend.app.services.navigation import build_navigation_plan
from backend.app.services.retrieval import citation_from_row, retrieve
from backend.app.services.safety import classify_question
from backend.app.storage import Database

settings = get_settings()
database = Database(settings.sqlite_path)
app = FastAPI(
    title="GI-Onco Navigator API",
    version="0.1.0",
    description="Evidence-grounded postoperative information navigation. Not medical advice.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    patient: PatientProfile


class QuestionResponse(BaseModel):
    status: str
    message: str
    assessment: JourneyAssessment


def require_admin(x_admin_key: str = Header(default="")) -> None:
    if not settings.admin_api_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="valid admin key required")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.put("/api/v1/patients/{patient_id}", response_model=PatientProfile)
def save_patient(patient_id: str, patient: PatientProfile) -> PatientProfile:
    if patient_id != patient.patient_id:
        raise HTTPException(status_code=400, detail="patient_id in path and body must match")
    database.save_patient(patient)
    database.log_event("patient_saved", patient_id, {"cancer_type": patient.cancer_type.value})
    return patient


@app.get("/api/v1/patients/{patient_id}", response_model=PatientProfile)
def get_patient(patient_id: str) -> PatientProfile:
    patient = database.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return patient


@app.get("/api/v1/evidence/sources")
def list_evidence_sources() -> list[dict[str, object]]:
    public_fields = {"source_id", "title", "evidence_type", "version", "publication_date", "public_url"}
    return [
        {key: value for key, value in source.items() if key in public_fields}
        for source in database.list_sources()
        if source["review_status"] == "approved"
    ]


@app.get("/api/v1/admin/evidence/sources", dependencies=[Depends(require_admin)])
def list_admin_evidence_sources() -> list[dict[str, object]]:
    return database.list_sources()


@app.post("/api/v1/admin/evidence/sources", status_code=201, dependencies=[Depends(require_admin)])
def create_evidence_source(source: EvidenceSourceCreate) -> dict[str, str]:
    payload = source.model_dump(mode="json")
    payload["review_status"] = "quarantined"
    database.add_source(payload)
    database.log_event("source_registered", source.source_id, {"title": source.title})
    return {"source_id": source.source_id, "status": "registered"}


@app.get(
    "/api/v1/admin/evidence/sources/{source_id}/reviews",
    response_model=EvidenceReviewState,
    dependencies=[Depends(require_admin)],
)
def get_evidence_reviews(source_id: str) -> EvidenceReviewState:
    try:
        return EvidenceReviewState.model_validate(database.get_review_state(source_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc


@app.post(
    "/api/v1/admin/evidence/sources/{source_id}/reviews",
    response_model=EvidenceReviewState,
    dependencies=[Depends(require_admin)],
)
def review_evidence_source(source_id: str, review: EvidenceReviewRequest) -> EvidenceReviewState:
    try:
        state = database.review_source(
            source_id,
            review.dimension.value,
            review.decision.value,
            review.reviewer,
            review.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc
    database.log_event(
        "source_reviewed",
        source_id,
        {"dimension": review.dimension.value, "decision": review.decision.value, "reviewer": review.reviewer},
    )
    return EvidenceReviewState.model_validate(state)


@app.post("/api/v1/journey/assess", response_model=JourneyAssessment)
def assess_patient_journey(patient: PatientProfile) -> JourneyAssessment:
    return assess_journey(patient)


@app.post("/api/v1/navigation/plan", response_model=PatientNavigationPlan)
def create_navigation_plan(patient: PatientProfile) -> PatientNavigationPlan:
    return build_navigation_plan(patient)


@app.post("/api/v1/navigation/question", response_model=NavigationAnswer)
def ask_navigation_question(request: QuestionRequest) -> NavigationAnswer:
    decision = classify_question(request.question)
    assessment = assess_journey(request.patient)
    if not decision.allowed:
        raise HTTPException(status_code=422, detail={"category": decision.category, "message": decision.message})
    rows = retrieve(database, request.question, request.patient.cancer_type.value)
    citations = [citation_from_row(row) for row in rows]
    if not citations:
        return NavigationAnswer(
            answer="当前经过审核的证据库中没有检索到足以回答这一问题的内容。请补充资料，或把这个问题带给诊疗团队确认。",
            assessment=assessment,
            citations=[],
            limitations=["未找到经过审核且与当前癌种匹配的证据片段。"],
        )
    try:
        validate_citations(citations)
    except CitationValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    evidence_summary = "\n\n".join(
        f"证据 {index}：{citation.excerpt}" for index, citation in enumerate(citations, start=1)
    )
    answer = (
        "以下是与问题最相关的已审核资料片段，供你理解情况并准备就诊讨论；系统不据此给出治疗决定。\n\n"
        + evidence_summary
    )
    database.log_event(
        "navigation_answered",
        request.patient.patient_id,
        {"question": request.question, "source_ids": [item.source_id for item in citations]},
    )
    return NavigationAnswer(
        answer=answer,
        assessment=assessment,
        citations=citations,
        limitations=["当前版本采用抽取式回答，保留原始证据片段以降低无依据生成风险。"],
    )
