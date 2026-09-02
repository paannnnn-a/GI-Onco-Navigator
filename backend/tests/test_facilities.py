from datetime import date

from backend.app.schemas import PatientProfile
from backend.app.services.facilities import match_facilities


def _facility(identifier: str, province: str, city: str, services: list[str]) -> dict[str, object]:
    return {
        "facility_id": identifier, "name": f"测试机构{identifier}", "province": province,
        "city": city, "official_registration_url": "https://zgcx.nhc.gov.cn/unit",
        "official_website": None, "cancer_types": ["colon"], "service_tags": services,
        "verification_status": "verified", "verified_at": "2026-08-01",
    }


def test_facility_filter_respects_no_cross_province_preference() -> None:
    patient = PatientProfile(
        patient_id="p", cancer_type="colon", province="山东省", city="济南市",
        accepts_cross_province_care=False,
    )
    rows = match_facilities(
        [_facility("local", "山东省", "济南市", ["胃肠肿瘤多学科门诊"]),
         _facility("remote", "北京市", "北京市", ["胃肠肿瘤多学科门诊"])],
        patient, ["胃肠肿瘤多学科门诊"], today=date(2026, 9, 2),
    )
    assert [item.facility_id for item in rows] == ["local"]
    assert "医院排名" in rows[0].disclaimer


def test_facility_match_discloses_unmatched_services() -> None:
    patient = PatientProfile(patient_id="p", cancer_type="colon", accepts_cross_province_care=True)
    rows = match_facilities(
        [_facility("one", "山东省", "济南市", ["营养门诊"])], patient,
        ["营养门诊", "造口门诊"], today=date(2026, 9, 2),
    )
    assert rows[0].unmatched_services == ["造口门诊"]
