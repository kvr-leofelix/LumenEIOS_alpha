"""AI Question Studio: learning-resource links as a retrieval source next to the chapter PDF."""
import json

import httpx
import pytest

from backend.app.api.v1 import assessments as assessments_api
from backend.app.services import web_source
from backend.app.services.llm_service import QwenQuestionStudioService
from backend.app.services.ocr_service import qwen_model
from backend.app.services.web_source import (
    WebSource,
    WebSourceError,
    chunk_text,
    extract_readable_text,
    fetch_web_source,
    normalize_urls,
)

ARTICLE = "Photosynthesis converts light energy into chemical energy stored in glucose. " * 8

WIKI_HTML = f"""<html><head><title>Photosynthesis - Wikipedia</title><script>var x = "tracking";</script></head>
<body><nav>Main menu Donate Log in</nav>
<div id="mw-content-text"><p>{ARTICLE}<sup>[1]</sup></p>
<div class="reflist">1. Some citation that is not lesson text</div>
<p>Chlorophyll absorbs mostly blue and red light.</p></div>
<footer>Privacy policy</footer></body></html>"""

ONE_MCQ = json.dumps({"mcqs": [{
    "type": "mcq", "text": "What does chlorophyll absorb?", "options": ["Red", "Green", "Infrared", "X-rays"],
    "correct_answer": "Red", "marking_rubric": "Red light is absorbed.", "competency": "CU",
}]})


def test_extracts_article_text_without_page_chrome():
    title, text = extract_readable_text(WIKI_HTML)
    assert title == "Photosynthesis - Wikipedia"
    assert "converts light energy" in text and "Chlorophyll absorbs" in text
    for junk in ("Main menu", "tracking", "Privacy policy", "citation that is not", "[1]"):
        assert junk not in text


def test_chunks_stay_under_the_passage_size():
    chunks = chunk_text("\n\n".join(["word " * 120] * 10), size=1500)
    assert len(chunks) > 1
    assert all(len(chunk) <= 1500 for chunk in chunks)


@pytest.mark.parametrize("urls, message", [
    (["ftp://example.org/file"], "not a web link"),
    (["https://user:pw@example.org/"], "username or password"),
    (["https://example.org:8080/"], "standard web ports"),
    ([f"https://example.org/{i}" for i in range(4)], "at most 3"),
])
def test_rejects_unsafe_or_too_many_links(urls, message):
    with pytest.raises(WebSourceError, match=message):
        normalize_urls(urls)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost/", "http://10.0.0.5/", "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
])
async def test_blocks_requests_into_private_networks(url):
    with pytest.raises(WebSourceError, match="private or internal"):
        await fetch_web_source(url)


def mock_client(routes):
    def handler(request: httpx.Request):
        return routes[str(request.url)]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


@pytest.fixture
def public_dns(monkeypatch):
    async def check(host):
        if host == "internal.test":
            raise WebSourceError("'internal.test' points to a private or internal address, which isn't allowed.")
    monkeypatch.setattr(web_source, "_check_public_host", check)


@pytest.mark.asyncio
async def test_fetches_a_page_and_rechecks_every_redirect(public_dns):
    html = httpx.Response(200, text=WIKI_HTML, headers={"content-type": "text/html; charset=utf-8"})
    async with mock_client({
        "https://short.example/p": httpx.Response(301, headers={"location": "https://en.example.org/wiki/P"}),
        "https://en.example.org/wiki/P": html,
    }) as client:
        source = await fetch_web_source("https://short.example/p", client)
    assert source.url == "https://en.example.org/wiki/P"
    assert source.title == "Photosynthesis - Wikipedia"

    async with mock_client({
        "https://evil.example/": httpx.Response(302, headers={"location": "http://internal.test/secrets"}),
    }) as client:
        with pytest.raises(WebSourceError, match="private or internal"):
            await fetch_web_source("https://evil.example/", client)


@pytest.mark.asyncio
async def test_rejects_non_html_and_empty_pages(public_dns):
    async with mock_client({
        "https://x.example/a.pdf": httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}),
        "https://x.example/empty": httpx.Response(200, text="<html><body><nav>menu</nav></body></html>",
                                                  headers={"content-type": "text/html"}),
    }) as client:
        with pytest.raises(WebSourceError, match="Only web pages"):
            await fetch_web_source("https://x.example/a.pdf", client)
        with pytest.raises(WebSourceError, match="readable lesson text"):
            await fetch_web_source("https://x.example/empty", client)


def test_link_passages_go_through_the_same_retrieval_and_prompt(monkeypatch):
    service = QwenQuestionStudioService()
    prompts = []
    monkeypatch.setattr(service, "_generate_text", lambda prompt, **_: prompts.append(prompt) or ONE_MCQ)
    # Far more text than the 16k context: retrieval must pick the passage about the focus topic.
    filler = WebSource(url="https://a.example/history", title="History", text="\n\n".join(["Ancient trade routes. " * 60] * 20))
    relevant = WebSource(url="https://b.example/chlorophyll", title="Chlorophyll", text="Chlorophyll absorbs red and blue light. " * 30)

    questions = service._generate_sync(
        None, "sub-sci", "Science", None, None, 1, 0, "Understand", "chlorophyll", [filler, relevant],
    )

    assert "Link: Chlorophyll (https://b.example/chlorophyll), part 1 of 1" in prompts[0]
    assert questions[0]["source_document_ids"] == []
    assert questions[0]["source_document_names"] == ["https://a.example/history", "https://b.example/chlorophyll"]


def test_generation_needs_some_source():
    from backend.app.services.llm_service import QwenQuestionStudioInputError
    with pytest.raises(QwenQuestionStudioInputError, match="PDF or a learning-resource link"):
        QwenQuestionStudioService()._generate_sync(None, "sub-sci", "Science", None, None, 1, 0, "Apply", None, [])


@pytest.mark.asyncio
async def test_endpoint_generates_from_links_without_a_pdf(client, teacher_token, monkeypatch):
    async def fake_fetch(url):
        return WebSource(url=url, title="Photosynthesis", text=ARTICLE)
    monkeypatch.setattr(assessments_api, "fetch_web_source", fake_fetch)
    def generate(messages, max_new_tokens):
        prompt = messages[0]["content"][0]["text"]
        assert "Photosynthesis" in prompt
        assert "JSON object" in prompt
        return ONE_MCQ

    monkeypatch.setattr(qwen_model, "generate", generate)
    headers = {"Authorization": f"Bearer {teacher_token}"}
    body = {"subject_id": "sub-sci", "subject_name": "Science", "mcq_count": 1, "theory_count": 0,
            "bloom_level": "Understand", "save_to_bank": False,
            "source_urls": ["https://en.wikipedia.org/wiki/Photosynthesis"]}

    response = await client.post("/api/v1/assessments/generate-questions-beta", json=body, headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == assessments_api.settings.QWEN_VL_MODEL_ID
    assert data["source_documents_used"] == ["https://en.wikipedia.org/wiki/Photosynthesis"]
    assert data["questions"][0]["source_document_names"] == ["https://en.wikipedia.org/wiki/Photosynthesis"]


@pytest.mark.asyncio
async def test_endpoint_rejects_missing_or_bad_sources(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    base = {"subject_id": "sub-sci", "mcq_count": 1, "theory_count": 0, "bloom_level": "Apply"}
    none = await client.post("/api/v1/assessments/generate-questions-beta", json=base, headers=headers)
    assert none.status_code == 400 and "learning-resource link" in none.json()["detail"]
    bad = await client.post("/api/v1/assessments/generate-questions-beta",
                            json={**base, "source_urls": ["file:///etc/passwd"]}, headers=headers)
    assert bad.status_code == 400 and "not a web link" in bad.json()["detail"]
