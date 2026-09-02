from backend.app.knowledge import (
    ExtractedPage,
    chunk_pages,
    chunk_transcript,
    extract_docx_paragraphs,
    extract_transcript_cues,
    looks_corrupted,
)


def test_corrupt_text_detection() -> None:
    assert looks_corrupted("")
    assert looks_corrupted("δ൭Ҩ" * 30)
    assert not looks_corrupted("这是一段用于患者教育的正常中文文本。" * 10)


def test_chunk_preserves_page_locator() -> None:
    pages = [
        ExtractedPage(3, "第一段。" * 30, "pdf_text", False),
        ExtractedPage(4, "第二段。" * 30, "pdf_text", False),
    ]
    chunks = chunk_pages(pages, target_chars=1000)
    assert len(chunks) == 1
    assert chunks[0].page_start == 3
    assert chunks[0].page_end == 4


def test_extract_docx_paragraphs(tmp_path) -> None:
    from docx import Document

    path = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("第一段可用资料")
    document.add_paragraph("")
    document.add_paragraph("第二段可用资料")
    document.save(path)
    blocks = extract_docx_paragraphs(path)
    assert [block.page_number for block in blocks] == [1, 3]
    assert all(block.method == "docx_paragraph" for block in blocks)


def test_transcript_preserves_video_timestamp(tmp_path) -> None:
    path = tmp_path / "expert.srt"
    path.write_text(
        "1\n00:00:32,100 --> 00:00:38,900\n复诊前请整理已有资料。\n\n"
        "2\n00:00:39,000 --> 00:00:45,000\n具体情况需要与诊疗团队确认。\n",
        encoding="utf-8",
    )
    cues = extract_transcript_cues(path)
    chunks = chunk_transcript(cues)
    assert len(cues) == 2
    assert chunks[0].start_seconds == 32
    assert chunks[0].end_seconds == 45
    assert "诊疗团队" in chunks[0].text
