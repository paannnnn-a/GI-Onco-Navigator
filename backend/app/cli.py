from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.app.config import get_settings
from backend.app.knowledge import (
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


def ingest_pdf(
    manifest_path: Path,
    pdf_path: Path,
    use_ocr: bool = False,
    target_database: Database | None = None,
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    database = target_database or Database(get_settings().sqlite_path)
    manifest["local_filename"] = manifest.get("local_filename") or pdf_path.name
    manifest["sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    pages = extract_pdf_pages(pdf_path, RapidOcrEngine() if use_ocr else None)
    chunks = chunk_pages(pages)
    unresolved_pages = [page.page_number for page in pages if page.needs_ocr]
    manifest.setdefault("metadata", {})["extraction_audit"] = {
        "pages": len(pages),
        "readable_text_pages": len(pages) - len(unresolved_pages),
        "pages_needing_ocr": len(unresolved_pages),
        "page_numbers_needing_ocr": unresolved_pages,
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
                ingest_pdf(args.manifest, args.pdf, use_ocr=args.ocr),
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
