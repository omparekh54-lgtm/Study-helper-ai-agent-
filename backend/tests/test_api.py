"""End-to-end: upload → pipeline → dashboard → topic kit → video → exports (offline LLM)."""

import pytest

from app.jobs import jobs


@pytest.fixture(scope="module")
async def processed(client, sample_pdf):
    resp = await client.post("/api/documents", files={"file": ("photosynthesis-notes.pdf", sample_pdf, "application/pdf")})
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "queued"
    await jobs.wait_idle(timeout=120)
    resp = await client.get(f"/api/documents/{doc['id']}")
    return resp.json()


async def test_health(client):
    body = (await client.get("/api/health")).json()
    assert body["status"] == "ok" and body["database"] is True
    assert body["generator"] == "fake" and body["video"] is True


async def test_document_becomes_ready_with_units_and_topics(processed):
    doc = processed
    assert doc["status"] == "ready", doc
    assert doc["counts"]["topics"] >= 2
    assert doc["counts"]["ready_topics"] == doc["counts"]["topics"]
    assert doc["counts"]["questions"] > 0 and doc["counts"]["qa"] > 0
    assert doc["counts"]["verified_questions"] == doc["counts"]["questions"]  # fake verifier approves all
    assert doc["units"] and all(u["topics"] for u in doc["units"])
    assert doc["counts"]["videos_ready"] == doc["counts"]["topics"]


async def test_topic_detail_has_grounded_kit_and_video(client, processed):
    topic_id = processed["units"][0]["topics"][0]["id"]
    topic = (await client.get(f"/api/topics/{topic_id}")).json()
    assert topic["kit_status"] == "ready"
    q = topic["questions"][0]
    assert len(q["options"]) == 4 and 0 <= q["answer_index"] < 4
    assert q["source_quote"] and q["source_loc"].startswith("p")
    assert topic["qa"][0]["answer"]
    assert topic["video"]["status"] == "ready"
    assert topic["video"]["url"].endswith("/video.mp4")
    assert topic["video"]["scenes"][0]["start"] == 0
    assert topic["youtube"]["mode"] == "search" and len(topic["youtube"]["links"]) == 3
    assert topic["prev_topic"] is None and topic["next_topic"] is not None


async def test_video_supports_range_requests_and_captions(client, processed):
    topic_id = processed["units"][0]["topics"][0]["id"]
    full = await client.get(f"/api/topics/{topic_id}/video.mp4")
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4"
    size = len(full.content)
    part = await client.get(f"/api/topics/{topic_id}/video.mp4", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 0-99/{size}"
    assert len(part.content) == 100
    tail = await client.get(f"/api/topics/{topic_id}/video.mp4", headers={"Range": "bytes=-50"})
    assert tail.status_code == 206 and len(tail.content) == 50
    bad = await client.get(f"/api/topics/{topic_id}/video.mp4", headers={"Range": f"bytes={size + 10}-"})
    assert bad.status_code == 416
    download = await client.get(f"/api/topics/{topic_id}/video.mp4?download=true")
    assert "attachment" in download.headers["content-disposition"]
    poster = await client.get(f"/api/topics/{topic_id}/poster.jpg")
    assert poster.status_code == 200 and poster.content[:3] == b"\xff\xd8\xff"
    vtt = await client.get(f"/api/topics/{topic_id}/video.vtt")
    assert vtt.text.startswith("WEBVTT") and "-->" in vtt.text


async def test_pdf_exports(client, processed):
    topic_id = processed["units"][0]["topics"][0]["id"]
    for url in (
        f"/api/topics/{topic_id}/quiz.pdf",
        f"/api/topics/{topic_id}/qa.pdf",
        f"/api/documents/{processed['id']}/study-pack.pdf",
    ):
        resp = await client.get(url)
        assert resp.status_code == 200, url
        assert resp.content.startswith(b"%PDF")
        assert "attachment" in resp.headers["content-disposition"]


async def test_mock_test_covers_all_topics(client, processed):
    resp = await client.get(f"/api/documents/{processed['id']}/mock-test?count=12")
    body = resp.json()
    assert 0 < len(body["questions"]) <= 12
    assert len({q["topic_id"] for q in body["questions"]}) == min(processed["counts"]["topics"], len(body["questions"]))


async def test_duplicate_upload_is_deduplicated(client, processed, sample_pdf):
    resp = await client.post("/api/documents", files={"file": ("copy.pdf", sample_pdf, "application/pdf")})
    assert resp.status_code == 200
    assert resp.json()["id"] == processed["id"] and resp.json()["duplicate"] is True


async def test_request_video_and_retry_topic(client, processed):
    topic_id = processed["units"][0]["topics"][-1]["id"]
    resp = await client.post(f"/api/topics/{topic_id}/video")
    assert resp.status_code == 200 and resp.json()["status"] == "ready"
    resp = await client.post(f"/api/topics/{topic_id}/retry")
    assert resp.status_code == 200
    await jobs.wait_idle(timeout=120)
    topic = (await client.get(f"/api/topics/{topic_id}")).json()
    assert topic["kit_status"] == "ready" and topic["video"]["status"] == "ready"
    doc = (await client.get(f"/api/documents/{processed['id']}")).json()
    assert doc["status"] == "ready"


async def test_upload_errors_are_friendly(client):
    resp = await client.post("/api/documents", files={"file": ("x.exe", b"MZ" * 300, "application/octet-stream")})
    assert resp.status_code == 422 and "Unsupported file type" in resp.json()["detail"]
    resp = await client.post("/api/documents")
    assert resp.status_code == 422 and resp.json()["detail"] == "Please choose a file to upload."


async def test_unknown_ids_404(client):
    assert (await client.get("/api/documents/nope")).status_code == 404
    assert (await client.get("/api/topics/nope")).status_code == 404


async def test_delete_document(client):
    text = ("Newton's first law states that an object remains at rest unless acted on by a force. " * 30).encode()
    doc = (await client.post("/api/documents", files={"file": ("physics.txt", text, "text/plain")})).json()
    await jobs.wait_idle(timeout=120)
    assert (await client.delete(f"/api/documents/{doc['id']}")).status_code == 204
    assert (await client.get(f"/api/documents/{doc['id']}")).status_code == 404


async def test_cors_allows_vercel_previews(client):
    resp = await client.options(
        "/api/health",
        headers={"Origin": "https://studyforge-git-main-me.vercel.app", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("access-control-allow-origin") == "https://studyforge-git-main-me.vercel.app"
