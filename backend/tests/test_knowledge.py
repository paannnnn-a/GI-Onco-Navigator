from backend.app.knowledge import ExtractedPage, chunk_pages, looks_corrupted


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

