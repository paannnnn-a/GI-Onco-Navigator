from fastapi.testclient import TestClient

from backend.app import main
from backend.app.storage import Database


def test_patient_round_trip_and_safe_empty_answer(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "api.db")
    monkeypatch.setattr(main, "database", database)
    client = TestClient(main.app)
    patient = {
        "patient_id": "patient-test",
        "cancer_type": "colon",
        "surgery_date": "2026-08-20",
    }
    assert client.put("/api/v1/patients/patient-test", json=patient).status_code == 200
    assert client.get("/api/v1/patients/patient-test").json()["cancer_type"] == "colon"
    response = client.post(
        "/api/v1/navigation/question",
        json={"question": "复诊时需要准备什么？", "patient": patient},
    )
    assert response.status_code == 200
    assert response.json()["citations"] == []
    assert response.json()["requires_clinician_review"] is True


def test_rejects_prescriptive_question(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "database", Database(tmp_path / "api.db"))
    client = TestClient(main.app)
    response = client.post(
        "/api/v1/navigation/question",
        json={
            "question": "我该吃什么药，具体剂量是多少？",
            "patient": {"patient_id": "safe-test", "cancer_type": "rectal"},
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "individual_treatment_instruction"


def test_admin_source_registration_requires_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "database", Database(tmp_path / "api.db"))
    client = TestClient(main.app)
    source = {
        "source_id": "admin-source",
        "title": "管理员测试来源",
        "evidence_type": "guideline",
        "cancer_types": ["colon"],
    }
    assert client.post("/api/v1/admin/evidence/sources", json=source).status_code == 401
    response = client.post(
        "/api/v1/admin/evidence/sources",
        json=source,
        headers={"X-Admin-Key": main.settings.admin_api_key},
    )
    assert response.status_code == 201


def test_navigation_plan_includes_symptom_topic() -> None:
    response = TestClient(main.app).post(
        "/api/v1/navigation/plan",
        json={
            "patient_id": "plan-test",
            "cancer_type": "gastric",
            "symptoms": ["食欲下降"],
        },
    )
    assert response.status_code == 200
    assert response.json()["topics"][0]["category"] == "symptoms"


def test_approved_evidence_answer_contains_locator(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "api.db")
    monkeypatch.setattr(main, "database", database)
    database.add_source(
        {
            "source_id": "source-1",
            "title": "测试患者教育资料",
            "evidence_type": "patient_education",
            "version": "1",
            "publication_date": "2026-01-01",
            "cancer_types": ["gastric"],
            "intended_audience": "patient",
            "copyright_status": "test_only",
            "license_name": None,
            "public_url": None,
            "local_filename": None,
            "sha256": None,
            "supersedes_source_id": None,
            "review_status": "approved",
            "metadata": {},
        }
    )
    database.add_chunk(
        {
            "chunk_id": "chunk-1",
            "source_id": "source-1",
            "ordinal": 0,
            "text": "复诊准备包括整理已有检查资料和需要向诊疗团队确认的问题。",
            "page_start": 3,
            "page_end": 3,
            "timestamp_start_seconds": None,
            "timestamp_end_seconds": None,
            "section_path": ["复诊准备"],
            "cancer_types": ["gastric"],
            "tags": ["复诊"],
            "extraction_method": "test_fixture",
            "review_status": "approved",
            "content_hash": "fixture",
        }
    )
    response = TestClient(main.app).post(
        "/api/v1/navigation/question",
        json={
            "question": "复诊准备",
            "patient": {"patient_id": "answer-test", "cancer_type": "gastric"},
        },
    )
    assert response.status_code == 200
    assert response.json()["citations"][0]["page_start"] == 3
