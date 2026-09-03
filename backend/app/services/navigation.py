from backend.app.schemas import NavigationTopic, PatientNavigationPlan, PatientProfile
from backend.app.services.journey import assess_journey


def build_navigation_plan(profile: PatientProfile) -> PatientNavigationPlan:
    assessment = assess_journey(profile)
    topics = [
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
