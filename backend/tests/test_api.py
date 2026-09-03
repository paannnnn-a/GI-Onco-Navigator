import json
import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.storage import Database


def test_patient_round_trip_and_safe_empty_answer(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "api.db")
    monkeypatch.setattr(main, "database", database)
    client = TestClient(main.app)
    access = client.post("/api/v1/patient-access").json()
    patient = {
        "patient_id": access["patient_id"],
        "cancer_type": "colon",
        "surgery_date": "2026-08-20",
        "consent_to_store": True,
    }
    url = f"/api/v1/patients/{access['patient_id']}"
    headers = {"Authorization": f"Bearer {access['access_token']}"}
    assert client.put(url, json=patient).status_code == 401
    assert client.put(url, json=patient, headers=headers).status_code == 200
    assert client.get(url, headers=headers).json()["cancer_type"] == "colon"
    reminder = client.post(
        f"{url}/reminders",
        json={
            "title": "复诊事项", "due_at": "2026-09-10T09:00:00+08:00",
            "source_note": "门诊预约通知",
        },
        headers=headers,
    )
    assert reminder.status_code == 201
    reminder_id = reminder.json()["reminder_id"]
    assert len(client.get(f"{url}/reminders", headers=headers).json()) == 1
    completed = client.patch(
        f"{url}/reminders/{reminder_id}", json={"status": "completed"}, headers=headers
    )
    assert completed.json()["status"] == "completed"
    exported = client.get(f"{url}/export", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["patient"]["patient_id"] == access["patient_id"]
    assert exported.json()["reminders"][0]["reminder_id"] == reminder_id
    assert "access_token" not in exported.text
    response = client.post(
        "/api/v1/navigation/question",
        json={"question": "复诊时需要准备什么？", "patient": patient},
    )
    assert response.status_code == 200
    assert response.json()["citations"] == []
    assert response.json()["requires_clinician_review"] is True
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_patient_record_requires_explicit_storage_consent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "database", Database(tmp_path / "consent.db"))
    client = TestClient(main.app)
    access = client.post("/api/v1/patient-access").json()
    response = client.put(
        f"/api/v1/patients/{access['patient_id']}",
        json={"patient_id": access["patient_id"], "cancer_type": "gastric"},
        headers={"Authorization": f"Bearer {access['access_token']}"},
    )
    assert response.status_code == 422
    assert "consent" in response.json()["detail"]


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
        "copyright_status": "synthetic_test_permission",
    }
    assert client.post("/api/v1/admin/evidence/sources", json=source).status_code == 401
    response = client.post(
        "/api/v1/admin/evidence/sources",
        json=source,
        headers={"X-Admin-Key": main.settings.admin_api_key},
    )
    assert response.status_code == 201
    assert client.get("/api/v1/evidence/sources").json() == []
    assert client.get("/api/v1/admin/evidence/sources").status_code == 401
    assert len(client.get("/api/v1/admin/evidence/sources", headers={"X-Admin-Key": main.settings.admin_api_key}).json()) == 1


def test_admin_can_upload_transcript_only_into_quarantine(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "upload.db")
    monkeypatch.setattr(main, "database", database)
    client = TestClient(main.app)
    manifest = {
        "source_id": "uploaded-transcript",
        "title": "合成专家视频字幕",
        "evidence_type": "expert_video",
        "cancer_types": ["colon"],
        "copyright_status": "synthetic_test_permission",
    }
    response = client.post(
        "/api/v1/admin/evidence/uploads",
        data={"manifest_json": json.dumps(manifest, ensure_ascii=False)},
        files={
            "file": (
                "verified.srt",
                "1\n00:00:01,000 --> 00:00:05,000\n这是完全虚构的测试字幕。\n".encode(),
                "application/x-subrip",
            )
        },
        headers={"X-Admin-Key": main.settings.admin_api_key},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "quarantined"
    assert response.json()["chunks"] == 1
    source = database.get_source("uploaded-transcript")
    assert source is not None
    assert source["review_status"] == "quarantined"
    assert source["local_filename"] == "verified.srt"
    total, chunks = database.list_source_chunks("uploaded-transcript", 0, 10)
    assert total == 1
    assert chunks[0]["timestamp_start_seconds"] == 1


def test_admin_upload_rejects_unsupported_or_disguised_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "database", Database(tmp_path / "rejected-upload.db"))
    client = TestClient(main.app)
    headers = {"X-Admin-Key": main.settings.admin_api_key}
    manifest = json.dumps(
        {
            "source_id": "bad-upload",
            "title": "无效上传",
            "evidence_type": "other",
            "copyright_status": "synthetic_test_permission",
        },
        ensure_ascii=False,
    )
    unsupported = client.post(
        "/api/v1/admin/evidence/uploads",
        data={"manifest_json": manifest},
        files={"file": ("source.exe", b"not executable", "application/octet-stream")},
        headers=headers,
    )
    assert unsupported.status_code == 415
    disguised = client.post(
        "/api/v1/admin/evidence/uploads",
        data={"manifest_json": manifest},
        files={"file": ("source.pdf", b"not a pdf", "application/pdf")},
        headers=headers,
    )
    assert disguised.status_code == 422

    monkeypatch.setattr(main, "MAX_DOCX_UNCOMPRESSED_BYTES", 10)
    oversized_docx = BytesIO()
    with zipfile.ZipFile(oversized_docx, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", b"0" * 20)
    archive_bomb = client.post(
        "/api/v1/admin/evidence/uploads",
        data={"manifest_json": manifest},
        files={
            "file": (
                "oversized.docx", oversized_docx.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert archive_bomb.status_code == 422
    assert "safety limit" in archive_bomb.json()["detail"]


def test_admin_upload_cannot_replace_existing_source(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "duplicate-upload.db")
    monkeypatch.setattr(main, "database", database)
    database.add_source(
        {
            "source_id": "existing-source", "title": "已有来源", "evidence_type": "guideline",
            "version": "1", "publication_date": None, "cancer_types": ["colon"],
            "intended_audience": "patient", "copyright_status": "open_license",
            "license_name": "test", "public_url": None, "local_filename": None,
            "sha256": None, "supersedes_source_id": None, "review_status": "quarantined",
            "metadata": {},
        }
    )
    response = TestClient(main.app).post(
        "/api/v1/admin/evidence/uploads",
        data={
            "manifest_json": json.dumps(
                {
                    "source_id": "existing-source", "title": "替换内容",
                    "evidence_type": "guideline", "copyright_status": "open_license",
                }
            )
        },
        files={"file": ("replacement.srt", b"1\n00:00:01,000 --> 00:00:02,000\ntest\n")},
        headers={"X-Admin-Key": main.settings.admin_api_key},
    )
    assert response.status_code == 409
    assert database.get_source("existing-source")["title"] == "已有来源"


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


def test_evidence_requires_all_review_gates_before_patient_search(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "review.db")
    monkeypatch.setattr(main, "database", database)
    client = TestClient(main.app)
    headers = {"X-Admin-Key": main.settings.admin_api_key}
    source = {
        "source_id": "review-source",
        "title": "待审核患者资料",
        "evidence_type": "patient_education",
        "cancer_types": ["colon"],
        "copyright_status": "synthetic_test_permission",
    }
    assert client.post("/api/v1/admin/evidence/sources", json=source, headers=headers).status_code == 201
    database.add_chunk(
        {
            "chunk_id": "review-chunk", "source_id": "review-source", "ordinal": 0,
            "text": "复诊准备包括整理检查资料。", "page_start": 2, "page_end": 2,
            "timestamp_start_seconds": None, "timestamp_end_seconds": None,
            "section_path": [], "cancer_types": ["colon"], "tags": ["复诊"],
            "extraction_method": "test_fixture", "review_status": "quarantined", "content_hash": "review",
        }
    )
    chunks = client.get(
        "/api/v1/admin/evidence/sources/review-source/chunks", headers=headers
    )
    assert chunks.status_code == 200
    assert chunks.json()["total"] == 1
    assert chunks.json()["items"][0]["page_start"] == 2
    assert "整理检查资料" in chunks.json()["items"][0]["text"]
    assert database.search("复诊", "colon", approved_only=True) == []
    dimensions = ["copyright", "extraction_quality", "medical_accuracy", "patient_readability"]
    for dimension in dimensions:
        response = client.post(
            "/api/v1/admin/evidence/sources/review-source/reviews",
            json={
                "dimension": dimension, "decision": "approved", "reviewer": "Reviewer A",
                "reason": "已核对原文、来源及患者适用性。",
            },
            headers=headers,
        )
        assert response.status_code == 200
    assert response.json()["review_status"] == "approved"
    assert len(database.search("复诊", "colon", approved_only=True)) == 1
    response = client.post(
        "/api/v1/admin/evidence/sources/review-source/lifecycle",
        json={"status": "withdrawn", "actor": "Reviewer A", "reason": "发现内容需要重新核验。"},
        headers=headers,
    )
    assert response.status_code == 200
    assert database.search("复诊", "colon", approved_only=True) == []
    events = client.get(
        "/api/v1/admin/evidence/sources/review-source/lifecycle", headers=headers
    ).json()
    assert events[0]["new_status"] == "withdrawn"
    state = client.get(
        "/api/v1/admin/evidence/sources/review-source/reviews", headers=headers
    ).json()
    assert state["latest_reviews"] == []
    state = client.post(
        "/api/v1/admin/evidence/sources/review-source/reviews",
        json={
            "dimension": "copyright", "decision": "approved", "reviewer": "Reviewer A",
            "reason": "撤回后的新一轮版权复核已完成。",
        },
        headers=headers,
    ).json()
    assert state["review_status"] == "review_in_progress"
    assert database.search("复诊", "colon", approved_only=True) == []


def test_rejection_keeps_source_out_of_patient_search(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "rejected.db")
    monkeypatch.setattr(main, "database", database)
    database.add_source(
        {
            "source_id": "rejected", "title": "不合格资料", "evidence_type": "other", "version": None,
            "publication_date": None, "cancer_types": ["rectal"], "intended_audience": "patient",
            "copyright_status": "unknown", "license_name": None, "public_url": None,
            "local_filename": None, "sha256": None, "supersedes_source_id": None,
            "review_status": "quarantined", "metadata": {},
        }
    )
    state = database.review_source("rejected", "medical_accuracy", "rejected", "Doctor B", "内容缺少可验证依据。")
    assert state["review_status"] == "rejected"


def test_admin_facility_registration_and_public_matching(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "database", Database(tmp_path / "facilities.db"))
    client = TestClient(main.app)
    facility = {
        "facility_id": "synthetic-facility", "name": "合成测试医疗机构",
        "province": "山东省", "city": "济南市",
        "official_registration_url": "https://zgcx.nhc.gov.cn/unit",
        "cancer_types": ["colon"], "service_tags": ["营养门诊"],
        "verified_at": "2026-09-01", "verification_note": "合成测试记录，不代表真实机构。",
    }
    assert client.post("/api/v1/admin/facilities", json=facility).status_code == 401
    assert client.post(
        "/api/v1/admin/facilities", json=facility,
        headers={"X-Admin-Key": main.settings.admin_api_key},
    ).status_code == 201
    response = client.post(
        "/api/v1/facilities/match",
        json={
            "patient": {
                "patient_id": "facility-patient", "cancer_type": "colon",
                "province": "山东省", "city": "济南市", "accepts_cross_province_care": False,
            },
            "desired_services": ["营养门诊"],
        },
    )
    assert response.status_code == 200
    assert response.json()["matches"][0]["facility_id"] == "synthetic-facility"
    assert response.json()["official_registry_url"] == "https://zgcx.nhc.gov.cn/unit"


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
            "review_status": "quarantined",
            "content_hash": "fixture",
        }
    )
    for dimension in ["copyright", "extraction_quality", "medical_accuracy", "patient_readability"]:
        database.review_source(
            "source-1", dimension, "approved", "Fixture Reviewer", "测试资料已完成对应审核。"
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
