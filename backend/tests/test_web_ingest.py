import pytest

from backend.app.web_ingest import extract_web_chunks, validate_public_https_url


def test_extract_webpage_removes_scripts_and_preserves_heading() -> None:
    content = """<html><nav>菜单内容不应收录</nav><main><h1>复诊准备</h1>
    <p>复诊前可以整理已有检查资料和希望向诊疗团队确认的问题。</p>
    <script>危险的脚本内容绝不能进入知识库。</script></main></html>""".encode()
    chunks = extract_web_chunks(content)
    assert len(chunks) == 1
    assert chunks[0].section_path[0] == "复诊准备"
    assert "检查资料" in chunks[0].text
    assert "脚本" not in chunks[0].text


def test_web_ingestion_refuses_local_and_insecure_urls() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        validate_public_https_url("http://example.com/page")
    with pytest.raises(ValueError, match="private"):
        validate_public_https_url("https://127.0.0.1/private")
