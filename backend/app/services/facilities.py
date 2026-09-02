from __future__ import annotations

from datetime import UTC, date, datetime

from backend.app.schemas import FacilityMatch, PatientProfile

DISCLAIMER = "这是按地点和公开服务标签进行的信息筛选，不代表医院排名、疗效比较或就医推荐。请通过官方渠道核实最新服务信息。"


def match_facilities(
    facilities: list[dict[str, object]],
    patient: PatientProfile,
    desired_services: list[str],
    today: date | None = None,
) -> list[FacilityMatch]:
    today = today or datetime.now(UTC).date()
    desired = {item.strip().lower() for item in desired_services if item.strip()}
    matches: list[tuple[int, FacilityMatch]] = []
    for facility in facilities:
        cancer_types = {str(item) for item in facility.get("cancer_types", [])}
        if cancer_types and patient.cancer_type.value not in cancer_types:
            continue
        same_province = bool(patient.province and facility["province"] == patient.province)
        same_city = bool(patient.city and facility["city"] == patient.city)
        if patient.province and patient.accepts_cross_province_care is False and not same_province:
            continue
        services = {str(item).strip().lower() for item in facility.get("service_tags", [])}
        matched_services = sorted(desired & services)
        unmatched = sorted(desired - services)
        reasons: list[str] = []
        if same_city:
            reasons.append("与档案所在城市一致")
        elif same_province:
            reasons.append("与档案所在省份一致")
        elif patient.accepts_cross_province_care:
            reasons.append("档案允许查看跨省机构")
        else:
            reasons.append("档案未提供完整地点偏好")
        if matched_services:
            reasons.append("公开服务标签匹配：" + "、".join(matched_services))
        verified_at = date.fromisoformat(str(facility["verified_at"]))
        if (today - verified_at).days > 365:
            reasons.append("登记信息核验已超过一年，请优先重新核实")
        match = FacilityMatch(
            facility_id=str(facility["facility_id"]), name=str(facility["name"]),
            province=str(facility["province"]), city=str(facility["city"]),
            official_registration_url=str(facility["official_registration_url"]),
            official_website=(str(facility["official_website"]) if facility.get("official_website") else None),
            matched_reasons=reasons, unmatched_services=unmatched,
            verification_status=str(facility["verification_status"]), verified_at=verified_at,
            disclaimer=DISCLAIMER,
        )
        location_order = 0 if same_city else 1 if same_province else 2
        matches.append((location_order, match))
    return [item for _, item in sorted(matches, key=lambda pair: (pair[0], pair[1].name))]
