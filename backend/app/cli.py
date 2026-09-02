from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.app.config import get_settings
from backend.app.knowledge import chunk_pages, extract_pdf_pages
from backend.app.storage import Database


def ingest_pdf(manifest_path: Path, pdf_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database = Database(get_settings().sqlite_path)
    manifest["local_filename"] = pdf_path.name
    manifest["sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    database.add_source(manifest)
    pages = extract_pdf_pages(pdf_path)
    chunks = chunk_pages(pages)
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
        "pages_needing_ocr": [page.page_number for page in pages if page.needs_ocr],
    }
    database.log_event("pdf_ingested", manifest["source_id"], result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="gi-onco")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest = subparsers.add_parser("ingest-pdf")
    ingest.add_argument("manifest", type=Path)
    ingest.add_argument("pdf", type=Path)
    args = parser.parse_args()
    if args.command == "ingest-pdf":
        print(json.dumps(ingest_pdf(args.manifest, args.pdf), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
