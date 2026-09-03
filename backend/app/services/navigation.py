from backend.app.schemas import (
    NavigationTopic,
    PatientNavigationPlan,
    PatientProfile,
    TreatmentStatus,
)
from backend.app.services.journey import assess_journey

PHASE_NAVIGATION: dict[TreatmentStatus, tuple[str, str, str, list[str]]] = {
    TreatmentStatus.POSTOPERATIVE_RECOVERY: (
        "early_recovery",
        "Early recovery check-in",
        "Organize discharge instructions, recovery observations, and questions that may need earlier clinical review.",
        [
            "Which recovery changes should I record, and who should I contact if they occur?",
            "Do my discharge instructions identify wound, stoma, eating, hydration, and activity questions for this stage?",
        ],
    ),
    TreatmentStatus.PATHOLOGY_REVIEW: (
        "pathology_review",
        "Pathology review preparation",
        "Identify missing pathology and operative details before discussing the postoperative assessment.",
        [
            "Which parts of my pathology report are still missing or need clarification?",
            "Are the stage, margins, lymph-node findings, and relevant molecular-test results documented?",
        ],
    ),
    TreatmentStatus.ADJUVANT_EVALUATION: (
        "postoperative_evaluation",
        "Postoperative evaluation visit",
        "Prepare the complete record and questions needed for a clinician-led discussion of possible next steps.",
        [
            "Is my surgical, pathology, and molecular-testing record complete for this evaluation?",
            "What benefits, risks, uncertainties, and alternatives should I ask the treating team to explain?",
        ],
    ),
    TreatmentStatus.ACTIVE_TREATMENT: (
        "treatment_monitoring",
        "Treatment monitoring preparation",
        "Structure clinician-confirmed treatment information, symptoms, tests, and contact questions without changing treatment.",
        [
            "Which symptoms, measurements, and test results should I bring to the next treatment visit?",
            "Who should I contact about a new or worsening problem, and what information should I provide?",
        ],
    ),
    TreatmentStatus.SURVEILLANCE: (
        "surveillance_preparation",
        "Surveillance preparation",
        "Keep clinician-provided follow-up dates, completed tests, and interval health changes organized.",
        [
            "Which follow-up items has my clinical team scheduled, and where are their results recorded?",
            "Which interval changes should I document and discuss at the next visit?",
        ],
    ),
    TreatmentStatus.REHABILITATION: (
        "rehabilitation",
        "Rehabilitation discussion",
        "Organize function, nutrition, activity, and quality-of-life concerns for professional assessment.",
        [
            "Which recovery goals and functional changes should I discuss with the care team?",
            "Would a dietitian, rehabilitation, stoma-care, or psychosocial assessment be relevant to my recorded concerns?",
        ],
    ),
    TreatmentStatus.UNKNOWN: (
        "stage_clarification",
        "Clarify the current phase",
        "Complete the minimum timeline and clinical record before relying on phase-specific navigation.",
        [
            "What was my surgery date, and what current treatment or follow-up plan has my clinician recorded?",
            "Which operative, discharge, and pathology records should I obtain before the next visit?",
        ],
    ),
}


def phase_navigation_topic(status: TreatmentStatus) -> NavigationTopic:
    category, title, purpose, questions = PHASE_NAVIGATION[status]
    return NavigationTopic(
        category=category,
        title=title,
        purpose=purpose,
        suggested_questions=questions,
    )


def build_navigation_plan(profile: PatientProfile) -> PatientNavigationPlan:
    assessment = assess_journey(profile)
    topics = [
        phase_navigation_topic(assessment.current_status),
        NavigationTopic(
            category="records",
            title="Pathology and surgical records",
            purpose="Confirm that the core records needed for follow-up discussions are complete.",
            suggested_questions=[
                "Are my pathology report, operative note, and discharge summary complete?",
                "Which report fields may affect the next discussion, and is additional testing needed?",
            ],
        ),
        NavigationTopic(
            category="facility_navigation",
            title="Facility information",
            purpose="Filter facilities by location preferences and verified public service tags, then confirm the result through official registries.",
            suggested_questions=[
                "Which facilities publicly list services relevant to the issue I need to discuss?",
                "What should I confirm with my insurer and the destination facility before traveling for care?",
            ],
        ),
        NavigationTopic(
            category="follow_up",
            title="Follow-up preparation",
            purpose="Organize timing and required records into a practical checklist.",
            suggested_questions=[
                "When should my next visit occur, and which records should I bring?",
                "Which changes should prompt me to contact the care team earlier?",
            ],
        ),
        NavigationTopic(
            category="nutrition_activity",
            title="Nutrition and activity",
            purpose="Find reviewed patient-education material relevant to the surgery, symptoms, and treatment stage.",
            suggested_questions=[
                "Which nutrition and activity questions need individual review given my surgery and current symptoms?",
                "Would an assessment by a dietitian or rehabilitation professional be appropriate?",
            ],
        ),
    ]
    if profile.symptoms:
        topics.insert(
            0,
            NavigationTopic(
                category="symptoms",
                title="Symptom log",
                purpose="Organize symptom onset, frequency, and changes for assessment by the care team.",
                suggested_questions=["Do these symptoms require an earlier visit, and which changes should I record?"],
            ),
        )
    return PatientNavigationPlan(
        assessment=assessment,
        topics=topics,
        safety_notice="This plan organizes information and questions for clinical visits. It does not provide an individual diagnosis, prescription, or treatment decision.",
    )
