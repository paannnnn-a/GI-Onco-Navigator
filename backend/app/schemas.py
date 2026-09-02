from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CancerType(StrEnum):
    COLON = "colon"
    RECTAL = "rectal"
    GASTRIC = "gastric"
    OTHER_GI = "other_gi"


class TreatmentStatus(StrEnum):
    POSTOPERATIVE_RECOVERY = "postoperative_recovery"
    PATHOLOGY_REVIEW = "pathology_review"
    ADJUVANT_EVALUATION = "adjuvant_evaluation"
    ACTIVE_TREATMENT = "active_treatment"
    SURVEILLANCE = "surveillance"
    REHABILITATION = "rehabilitation"
    UNKNOWN = "unknown"


class EvidenceType(StrEnum):
    GUIDELINE = "guideline"
    PATIENT_EDUCATION = "patient_education"
    EXPERT_VIDEO = "expert_video"
    PEER_REVIEWED = "peer_reviewed"
    OTHER = "other"


class ReviewDimension(StrEnum):
    COPYRIGHT = "copyright"
    EXTRACTION_QUALITY = "extraction_quality"
    MEDICAL_ACCURACY = "medical_accuracy"
    PATIENT_READABILITY = "patient_readability"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PatientProfile(BaseModel):
    patient_id: str = Field(min_length=1, max_length=64)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: str | None = Field(default=None, max_length=32)
    province: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=64)
    accepts_cross_province_care: bool | None = None
    cancer_type: CancerType
    surgery_date: date | None = None
    surgery_type: str | None = Field(default=None, max_length=256)
    pathological_stage: str | None = Field(default=None, max_length=64)
    t_stage: str | None = Field(default=None, max_length=16)
    n_stage: str | None = Field(default=None, max_length=16)
    m_stage: str | None = Field(default=None, max_length=16)
    margin_status: str | None = Field(default=None, max_length=32)
    lymph_nodes_examined: int | None = Field(default=None, ge=0)
    lymph_nodes_positive: int | None = Field(default=None, ge=0)
    mismatch_repair_status: str | None = Field(default=None, max_length=32)
    current_treatment: str | None = Field(default=None, max_length=256)
    symptoms: list[str] = Field(default_factory=list, max_length=30)
    medications: list[str] = Field(default_factory=list, max_length=50)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_nodes(self) -> "PatientProfile":
        if (
            self.lymph_nodes_examined is not None
            and self.lymph_nodes_positive is not None
            and self.lymph_nodes_positive > self.lymph_nodes_examined
        ):
            raise ValueError("positive lymph nodes cannot exceed examined lymph nodes")
        return self


class MissingInformation(BaseModel):
    field: str
    patient_friendly_label: str
    reason: str
    discuss_with: str = "treating clinician"


class JourneyAssessment(BaseModel):
    current_status: TreatmentStatus
    confidence: str
    explanation: str
    missing_information: list[MissingInformation]
    next_discussion_topics: list[str]
    emergency_notice: str | None = None


class Citation(BaseModel):
    source_id: str
    title: str
    evidence_type: EvidenceType
    version: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    timestamp_start_seconds: int | None = Field(default=None, ge=0)
    excerpt: str | None = None
    public_url: str | None = None
    section_path: list[str] = Field(default_factory=list)
    review_status: str = "unreviewed"


class NavigationAnswer(BaseModel):
    answer: str
    assessment: JourneyAssessment
    citations: list[Citation]
    limitations: list[str]
    requires_clinician_review: bool = True


class NavigationTopic(BaseModel):
    category: str
    title: str
    purpose: str
    suggested_questions: list[str]
    evidence_required: bool = True


class PatientNavigationPlan(BaseModel):
    assessment: JourneyAssessment
    topics: list[NavigationTopic]
    safety_notice: str


class EvidenceSourceCreate(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    evidence_type: EvidenceType
    version: str | None = None
    publication_date: date | None = None
    cancer_types: list[CancerType] = Field(default_factory=list)
    intended_audience: str = "patient"
    copyright_status: str = "metadata_only"
    license_name: str | None = None
    public_url: str | None = None
    local_filename: str | None = None
    sha256: str | None = None
    supersedes_source_id: str | None = None
    review_status: str = "unreviewed"
    metadata: dict[str, object] = Field(default_factory=dict)


class EvidenceReviewRequest(BaseModel):
    dimension: ReviewDimension
    decision: ReviewDecision
    reviewer: str = Field(min_length=2, max_length=128)
    reason: str = Field(min_length=5, max_length=2000)


class EvidenceReviewRecord(BaseModel):
    review_id: int
    source_id: str
    dimension: ReviewDimension
    decision: ReviewDecision
    reviewer: str
    reason: str
    created_at: datetime


class EvidenceReviewState(BaseModel):
    source_id: str
    review_status: str
    required_dimensions: list[ReviewDimension]
    latest_reviews: list[EvidenceReviewRecord]


class FacilityCreate(BaseModel):
    facility_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=2, max_length=300)
    province: str = Field(min_length=2, max_length=64)
    city: str = Field(min_length=2, max_length=64)
    official_registration_url: str = Field(pattern=r"^https://")
    official_website: str | None = Field(default=None, pattern=r"^https://")
    cancer_types: list[CancerType] = Field(default_factory=list)
    service_tags: list[str] = Field(default_factory=list, max_length=50)
    verification_status: str = "verified"
    verified_at: date
    verification_note: str = Field(min_length=5, max_length=1000)


class FacilityMatchRequest(BaseModel):
    patient: PatientProfile
    desired_services: list[str] = Field(default_factory=list, max_length=20)


class FacilityMatch(BaseModel):
    facility_id: str
    name: str
    province: str
    city: str
    official_registration_url: str
    official_website: str | None = None
    matched_reasons: list[str]
    unmatched_services: list[str]
    verification_status: str
    verified_at: date
    disclaimer: str


class FacilityMatchResponse(BaseModel):
    matches: list[FacilityMatch]
    official_registry_url: str
    notice: str
