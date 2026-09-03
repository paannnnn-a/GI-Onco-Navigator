from __future__ import annotations

from datetime import UTC, date, datetime

from backend.app.schemas import FacilityMatch, PatientProfile

DISCLAIMER = "This is an informational filter based on location and public service tags. It is not a hospital ranking, outcome comparison, or care recommendation. Verify current services through official channels."


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
            reasons.append("Matches the city in the patient profile")
        elif same_province:
            reasons.append("Matches the province in the patient profile")
        elif patient.accepts_cross_province_care:
            reasons.append("The profile allows facilities outside the home province")
        else:
            reasons.append("The profile does not include a complete location preference")
        if matched_services:
            reasons.append("Matching public service tags: " + ", ".join(matched_services))
        verified_at = date.fromisoformat(str(facility["verified_at"]))
        if (today - verified_at).days > 365:
            reasons.append("Registry verification is over one year old; confirm it before relying on this result")
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
