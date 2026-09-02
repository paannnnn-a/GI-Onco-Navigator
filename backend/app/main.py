import hashlib
import logging
import secrets
import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.auth import InvalidPatientToken, issue_patient_token, verify_patient_token
from backend.app.config import get_settings
from backend.app.observability import Metrics
from backend.app.schemas import (
    EvidenceReviewRequest,
    EvidenceReviewState,
    EvidenceSourceCreate,
    FacilityCreate,
    FacilityMatchRequest,
    FacilityMatchResponse,
    JourneyAssessment,
    NavigationAnswer,
    PatientNavigationPlan,
    PatientProfile,
    SourceLifecycleRecord,
    SourceLifecycleRequest,
)
from backend.app.services.citation_guard import CitationValidationError, validate_citations
from backend.app.services.facilities import match_facilities
from backend.app.services.journey import assess_journey
from backend.app.services.navigation import build_navigation_plan
from backend.app.services.retrieval import citation_from_row, retrieve
from backend.app.services.safety import classify_question
from backend.app.storage import Database

settings = get_settings()
database = Database(settings.sqlite_path)
metrics = Metrics()
logger = logging.getLogger("gi_onco.access")
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


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        metrics.record(request.method, request.url.path, 500)
        logger.exception("request_failed method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    metrics.record(request.method, route_path, response.status_code)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        "request method=%s route=%s status=%s duration_ms=%s request_id=%s",
        request.method, route_path, response.status_code, duration_ms, request_id,
    )
    return response


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    patient: PatientProfile


class QuestionResponse(BaseModel):
    status: str
    message: str
    assessment: JourneyAssessment


class PatientAccess(BaseModel):
    patient_id: str
    access_token: str
    expires_at: datetime


def require_admin(x_admin_key: str = Header(default="")) -> None:
    if not settings.admin_api_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="valid admin key required")


def require_patient(patient_id: str, authorization: str = Header(default="")) -> None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="patient access token required")
    try:
        verify_patient_token(token, settings.secret_key, patient_id)
    except InvalidPatientToken as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    if not database.ping():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


@app.get("/metrics", response_class=Response)
def prometheus_metrics() -> Response:
    return Response(metrics.prometheus(), media_type="text/plain; version=0.0.4")


@app.post("/api/v1/patient-access", response_model=PatientAccess, status_code=201)
def create_patient_access() -> PatientAccess:
    patient_id, token, expires_at = issue_patient_token(settings.secret_key)
    database.log_event("patient_access_issued", patient_id, {"expires_at": expires_at})
    return PatientAccess(
        patient_id=patient_id, access_token=token, expires_at=datetime.fromtimestamp(expires_at, UTC)
    )


@app.put(
    "/api/v1/patients/{patient_id}", response_model=PatientProfile, dependencies=[Depends(require_patient)]
)
def save_patient(patient_id: str, patient: PatientProfile) -> PatientProfile:
    if patient_id != patient.patient_id:
        raise HTTPException(status_code=400, detail="patient_id in path and body must match")
    if not patient.consent_to_store:
        raise HTTPException(status_code=422, detail="explicit consent_to_store is required")
    database.save_patient(patient)
    database.log_event("patient_saved", patient_id, {"cancer_type": patient.cancer_type.value})
    return patient


@app.get(
    "/api/v1/patients/{patient_id}", response_model=PatientProfile, dependencies=[Depends(require_patient)]
)
def get_patient(patient_id: str) -> PatientProfile:
    patient = database.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return patient


@app.delete(
    "/api/v1/patients/{patient_id}", status_code=204, dependencies=[Depends(require_patient)]
)
def delete_patient(patient_id: str) -> Response:
    deleted = database.delete_patient(patient_id)
    database.log_event("patient_deleted", patient_id, {"record_existed": deleted})
    return Response(status_code=204)


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


@app.post("/api/v1/admin/facilities", status_code=201, dependencies=[Depends(require_admin)])
def create_facility(facility: FacilityCreate) -> dict[str, str]:
    database.add_facility(facility.model_dump(mode="json"))
    database.log_event(
        "facility_registered", facility.facility_id, {"name": facility.name, "verified_at": str(facility.verified_at)}
    )
    return {"facility_id": facility.facility_id, "status": "registered"}


@app.post("/api/v1/facilities/match", response_model=FacilityMatchResponse)
def find_facilities(request: FacilityMatchRequest) -> FacilityMatchResponse:
    matches = match_facilities(
        database.list_verified_facilities(), request.patient, request.desired_services
    )
    return FacilityMatchResponse(
        matches=matches,
        official_registry_url="https://zgcx.nhc.gov.cn/unit",
        notice="结果仅依据已核验的机构登记、地点和公开服务标签筛选；未收录不代表不具备相关服务。",
    )


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


@app.post(
    "/api/v1/admin/evidence/sources/{source_id}/lifecycle",
    dependencies=[Depends(require_admin)],
)
def change_source_lifecycle(source_id: str, action: SourceLifecycleRequest) -> dict[str, object]:
    try:
        result = database.transition_source_status(
            source_id, action.status.value, action.actor, action.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc
    database.log_event("source_status_changed", source_id, result)
    return result


@app.get(
    "/api/v1/admin/evidence/sources/{source_id}/lifecycle",
    response_model=list[SourceLifecycleRecord],
    dependencies=[Depends(require_admin)],
)
def get_source_lifecycle(source_id: str) -> list[SourceLifecycleRecord]:
    try:
        return [
            SourceLifecycleRecord.model_validate(item)
            for item in database.list_source_status_events(source_id)
        ]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc


@app.post("/api/v1/journey/assess", response_model=JourneyAssessment)
def assess_patient_journey(patient: PatientProfile) -> JourneyAssessment:
    return assess_journey(patient)


@app.post("/api/v1/navigation/plan", response_model=PatientNavigationPlan)
def create_navigation_plan(patient: PatientProfile) -> PatientNavigationPlan:
    return build_navigation_plan(patient)


@app.post("/api/v1/navigation/question", response_model=NavigationAnswer)
def ask_navigation_question(request: QuestionRequest) -> NavigationAnswer:
    decision = classify_question(request.question, request.patient.symptoms)
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
        {
            "question_sha256": hashlib.sha256(request.question.encode("utf-8")).hexdigest(),
            "question_length": len(request.question),
            "source_ids": [item.source_id for item in citations],
        },
    )
    return NavigationAnswer(
        answer=answer,
        assessment=assessment,
        citations=citations,
        limitations=["当前版本采用抽取式回答，保留原始证据片段以降低无依据生成风险。"],
    )
