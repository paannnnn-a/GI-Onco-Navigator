from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.app.config import get_settings
from backend.app.knowledge import (
    ExtractedPage,
    audit_pdf,
    chunk_pages,
    chunk_transcript,
    extract_docx_paragraphs,
    extract_pdf_pages,
    extract_transcript_cues,
)
from backend.app.ocr import RapidOcrEngine
from backend.app.schemas import EvidenceSourceCreate
from backend.app.storage import Database
from backend.app.web_ingest import extract_web_chunks, fetch_public_webpage


def load_manifest(manifest_path: Path) -> dict[str, object]:
    """Load and validate a source manifest using the same contract as the admin API."""
    source = EvidenceSourceCreate.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    manifest = source.model_dump(mode="json")
    manifest["review_status"] = "quarantined"
    return manifest


def verify_content_free_pages(
    pages: list[ExtractedPage],
    page_numbers: set[int],
    reviewer: str | None,
    reason: str | None,
) -> dict[str, object] | None:
    """Record an accountable visual decision for blank or page-furniture-only pages."""
    if not page_numbers:
        return None
    if not reviewer or len(reviewer.strip()) < 2 or not reason or len(reason.strip()) < 5:
        raise ValueError(
            "verified content-free pages require --blank-page-reviewer and --blank-page-reason"
        )
    by_number = {page.page_number: page for page in pages}
    invalid = sorted(page_numbers - set(by_number))
    if invalid:
        raise ValueError(f"verified content-free page numbers are outside the PDF: {invalid}")
    ineligible = sorted(
        number
        for number in page_numbers
        if not by_number[number].needs_ocr or len(by_number[number].text.strip()) > 3
    )
    if ineligible:
        raise ValueError(
            "only unresolved pages with at most three extracted characters can be marked content-free: "
            f"{ineligible}"
        )
    return {
        "page_numbers": sorted(page_numbers),
        "reviewer": reviewer.strip(),
        "reason": reason.strip(),
    }


def ingest_pdf(
    manifest_path: Path,
    pdf_path: Path,
    use_ocr: bool = False,
    target_database: Database | None = None,
    verified_content_free_pages: set[int] | None = None,
    blank_page_reviewer: str | None = None,
    blank_page_reason: str | None = None,
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    database = target_database or Database(get_settings().sqlite_path)
    manifest["local_filename"] = manifest.get("local_filename") or pdf_path.name
    manifest["sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    pages = extract_pdf_pages(pdf_path, RapidOcrEngine() if use_ocr else None)
    chunks = chunk_pages(pages)
    content_free_review = verify_content_free_pages(
        pages,
        verified_content_free_pages or set(),
        blank_page_reviewer,
        blank_page_reason,
    )
    verified_page_numbers = set(verified_content_free_pages or set())
    unresolved_pages = [
        page.page_number
        for page in pages
        if page.needs_ocr and page.page_number not in verified_page_numbers
    ]
    manifest.setdefault("metadata", {})["extraction_audit"] = {
        "pages": len(pages),
        "readable_text_pages": len(pages) - len(unresolved_pages),
        "pages_needing_ocr": len(unresolved_pages),
        "page_numbers_needing_ocr": unresolved_pages,
    }
    if content_free_review:
        manifest["metadata"]["extraction_audit"][
            "human_verified_content_free_pages"
        ] = content_free_review
    database.add_source(manifest)
    database.reset_source_for_ingestion(str(manifest["source_id"]))
    for chunk in chunks:
        database.add_chunk(
            {
                "chunk_id": f"{manifest['source_id']}:{chunk.ordinal:05d}",
                "source_id": manifest["source_id"],
                "ordinal": chunk.ordinal,
                "text": chunk.text,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "timestamp_start_seconds": None,
                "timestamp_end_seconds": None,
                "section_path": [],
                "cancer_types": manifest.get("cancer_types", []),
                "tags": manifest.get("tags", []),
                "extraction_method": chunk.extraction_method,
                "review_status": manifest.get("review_status", "unreviewed"),
                "content_hash": chunk.content_hash,
            }
        )
    result = {
        "source_id": manifest["source_id"],
        "pages": len(pages),
        "chunks": len(chunks),
        "pages_needing_ocr": unresolved_pages,
    }
    database.log_event("pdf_ingested", manifest["source_id"], result)
    return result


def ingest_docx(
    manifest_path: Path, docx_path: Path, target_database: Database | None = None
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    database = target_database or Database(get_settings().sqlite_path)
    manifest["local_filename"] = manifest.get("local_filename") or docx_path.name
    manifest["sha256"] = hashlib.sha256(docx_path.read_bytes()).hexdigest()
    blocks = extract_docx_paragraphs(docx_path)
    chunks = chunk_pages(blocks)
    manifest.setdefault("metadata", {})["extraction_audit"] = {
        "paragraphs": len(blocks), "readable_blocks": len(blocks), "unresolved_blocks": 0
    }
    database.add_source(manifest)
    database.reset_source_for_ingestion(str(manifest["source_id"]))
    for chunk in chunks:
        database.add_chunk(
            {
                "chunk_id": f"{manifest['source_id']}:{chunk.ordinal:05d}",
                "source_id": manifest["source_id"],
                "ordinal": chunk.ordinal,
                "text": chunk.text,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "timestamp_start_seconds": None,
                "timestamp_end_seconds": None,
                "section_path": [],
                "cancer_types": manifest.get("cancer_types", []),
                "tags": manifest.get("tags", []),
                "extraction_method": "docx_paragraph",
                "review_status": manifest.get("review_status", "unreviewed"),
                "content_hash": chunk.content_hash,
            }
        )
    result = {"source_id": manifest["source_id"], "paragraphs": len(blocks), "chunks": len(chunks)}
    database.log_event("docx_ingested", manifest["source_id"], result)
    return result


def ingest_transcript(
    manifest_path: Path, transcript_path: Path, target_database: Database | None = None
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    database = target_database or Database(get_settings().sqlite_path)
    manifest["local_filename"] = manifest.get("local_filename") or transcript_path.name
    manifest["sha256"] = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
    cues = extract_transcript_cues(transcript_path)
    chunks = chunk_transcript(cues)
    manifest.setdefault("metadata", {})["extraction_audit"] = {
        "verified_cues": len(cues), "readable_blocks": len(chunks), "unresolved_blocks": 0
    }
    database.add_source(manifest)
    database.reset_source_for_ingestion(str(manifest["source_id"]))
    for chunk in chunks:
        database.add_chunk(
            {
                "chunk_id": f"{manifest['source_id']}:{chunk.ordinal:05d}",
                "source_id": manifest["source_id"], "ordinal": chunk.ordinal, "text": chunk.text,
                "page_start": None, "page_end": None,
                "timestamp_start_seconds": chunk.start_seconds,
                "timestamp_end_seconds": chunk.end_seconds,
                "section_path": [], "cancer_types": manifest.get("cancer_types", []),
                "tags": manifest.get("tags", []), "extraction_method": "verified_subtitle",
                "review_status": "quarantined", "content_hash": chunk.content_hash,
            }
        )
    result = {"source_id": manifest["source_id"], "cues": len(cues), "chunks": len(chunks)}
    database.log_event("transcript_ingested", manifest["source_id"], result)
    return result


def ingest_web(manifest_path: Path) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    public_url = str(manifest.get("public_url") or "")
    content = fetch_public_webpage(public_url)
    manifest["sha256"] = hashlib.sha256(content).hexdigest()
    database = Database(get_settings().sqlite_path)
    chunks = extract_web_chunks(content)
    manifest.setdefault("metadata", {})["extraction_audit"] = {
        "readable_blocks": len(chunks), "unresolved_blocks": 0
    }
    database.add_source(manifest)
    database.reset_source_for_ingestion(str(manifest["source_id"]))
    for chunk in chunks:
        database.add_chunk(
            {
                "chunk_id": f"{manifest['source_id']}:{chunk.ordinal:05d}",
                "source_id": manifest["source_id"], "ordinal": chunk.ordinal, "text": chunk.text,
                "page_start": None, "page_end": None, "timestamp_start_seconds": None,
                "timestamp_end_seconds": None, "section_path": chunk.section_path,
                "cancer_types": manifest.get("cancer_types", []), "tags": manifest.get("tags", []),
                "extraction_method": "web_html", "review_status": "quarantined",
                "content_hash": chunk.content_hash,
            }
        )
    result = {"source_id": manifest["source_id"], "url": public_url, "chunks": len(chunks)}
    database.log_event("webpage_ingested", manifest["source_id"], result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="gi-onco")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest = subparsers.add_parser("ingest-pdf")
    ingest.add_argument("manifest", type=Path)
    ingest.add_argument("pdf", type=Path)
    ingest.add_argument("--ocr", action="store_true", help="run fully local OCR on unreadable pages")
    ingest.add_argument(
        "--verified-content-free-page",
        action="append",
        type=int,
        default=[],
        help="page visually confirmed to contain no source content; repeat for multiple pages",
    )
    ingest.add_argument("--blank-page-reviewer")
    ingest.add_argument("--blank-page-reason")
    audit = subparsers.add_parser(
        "audit-pdf", help="report extraction quality without storing document content"
    )
    audit.add_argument("pdf", type=Path)
    ingest_docx_parser = subparsers.add_parser("ingest-docx")
    ingest_docx_parser.add_argument("manifest", type=Path)
    ingest_docx_parser.add_argument("docx", type=Path)
    ingest_transcript_parser = subparsers.add_parser("ingest-transcript")
    ingest_transcript_parser.add_argument("manifest", type=Path)
    ingest_transcript_parser.add_argument("transcript", type=Path, help="UTF-8 SRT or WebVTT file")
    ingest_web_parser = subparsers.add_parser("ingest-web")
    ingest_web_parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.command == "ingest-pdf":
        print(
            json.dumps(
                ingest_pdf(
                    args.manifest,
                    args.pdf,
                    use_ocr=args.ocr,
                    verified_content_free_pages=set(args.verified_content_free_page),
                    blank_page_reviewer=args.blank_page_reviewer,
                    blank_page_reason=args.blank_page_reason,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "audit-pdf":
        print(json.dumps(audit_pdf(args.pdf), ensure_ascii=False, indent=2))
    elif args.command == "ingest-docx":
        print(json.dumps(ingest_docx(args.manifest, args.docx), ensure_ascii=False, indent=2))
    elif args.command == "ingest-transcript":
        print(
            json.dumps(
                ingest_transcript(args.manifest, args.transcript), ensure_ascii=False, indent=2
            )
        )
    elif args.command == "ingest-web":
        print(json.dumps(ingest_web(args.manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
