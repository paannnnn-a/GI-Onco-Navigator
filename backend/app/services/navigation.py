from backend.app.schemas import NavigationTopic, PatientNavigationPlan, PatientProfile
from backend.app.services.journey import assess_journey


def build_navigation_plan(profile: PatientProfile) -> PatientNavigationPlan:
    assessment = assess_journey(profile)
    topics = [
        NavigationTopic(
            category="records",
            title="病理与手术资料",
            purpose="确认用于后续讨论的基础资料是否完整。",
            suggested_questions=[
                "我的病理报告、手术记录和出院记录是否已经齐全？",
                "报告中哪些字段会影响后续讨论，需要补充检测吗？",
            ],
        ),
        NavigationTopic(
            category="follow_up",
            title="复诊与随访准备",
            purpose="将时间安排和需要携带的资料整理成清单。",
            suggested_questions=[
                "下一次复诊应在什么时候，需要携带哪些资料？",
                "出现哪些变化时应提前联系诊疗团队？",
            ],
        ),
        NavigationTopic(
            category="nutrition_activity",
            title="营养与活动",
            purpose="根据手术类型、症状和治疗阶段查找经过审核的患者教育材料。",
            suggested_questions=[
                "结合我的手术和当前症状，饮食与活动有哪些需要个体化确认的地方？",
                "是否需要营养科或康复专业人员评估？",
            ],
        ),
    ]
    if profile.symptoms:
        topics.insert(
            0,
            NavigationTopic(
                category="symptoms",
                title="症状记录",
                purpose="把症状出现时间、频率和变化整理后交给诊疗团队评估。",
                suggested_questions=["这些症状是否需要提前就诊，应该记录哪些变化？"],
            ),
        )
    return PatientNavigationPlan(
        assessment=assessment,
        topics=topics,
        safety_notice="本计划用于整理信息和就诊问题，不提供个体化诊断、处方或治疗决定。",
    )
