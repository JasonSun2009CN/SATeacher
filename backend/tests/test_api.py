from pathlib import Path

from app.db import satmd_path
from tests.conftest import MINI_SATMD, upload


def test_health(client) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_import_satmd(client) -> None:
    resp = upload(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Mini Bank"
    assert body["question_count"] == 2
    assert body["answered_count"] == 0
    assert body["needs_answers"] is True
    assert body["answers_status"] == "none"


def test_import_pdf(client, sat_pdf: Path) -> None:
    resp = upload(client, "sat-sample.pdf", sat_pdf.read_bytes())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["question_count"] == 5
    assert body["answers_status"] == "external"
    assert body["needs_answers"] is False
    assert body["warnings"]


def test_reject_unsupported_type(client) -> None:
    resp = upload(client, "notes.txt", "hello")
    assert resp.status_code == 415


def test_reject_empty_file(client) -> None:
    resp = upload(client, "empty.md", b"")
    assert resp.status_code == 400


def test_reject_broken_satmd_reports_line(client) -> None:
    broken = MINI_SATMD.replace("- D. four", "- D. four\n- E. five")
    resp = upload(client, "broken.md", broken)
    assert resp.status_code == 422
    assert "line" in resp.json()["detail"]


def test_reject_non_pdf_bytes(client) -> None:
    resp = upload(client, "junk.pdf", b"this is not a pdf")
    assert resp.status_code == 422


def _import_mini(client) -> dict:
    resp = upload(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 200
    return resp.json()


def test_answer_key_entry_flow(client) -> None:
    doc = _import_mini(client)
    doc_id = doc["id"]

    questions = client.get(f"/api/documents/{doc_id}/questions").json()
    assert len(questions) == 2
    assert all(q["answer"] is None for q in questions)

    bad = client.put(f"/api/documents/{doc_id}/answers", json={"answers": {"Q001": "E"}})
    assert bad.status_code == 400

    resp = client.put(
        f"/api/documents/{doc_id}/answers",
        json={"answers": {"Q001": "B", "Q002": "D"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["answered_count"] == 2
    assert resp.json()["needs_answers"] is False

    questions = client.get(f"/api/documents/{doc_id}/questions").json()
    assert [q["answer"] for q in questions] == ["B", "D"]

    # the on-disk SAT-MD is kept in sync for export/debugging
    text = satmd_path(doc_id).read_text()
    assert "! answer: B" in text and "! answer: D" in text
    assert "answers: external" in text


def test_unknown_document_is_404(client) -> None:
    assert client.get("/api/documents/999999").status_code == 404
    assert client.put("/api/documents/999999/answers",
                      json={"answers": {"Q001": "A"}}).status_code == 404


def test_session_hides_answers_then_grades(client) -> None:
    doc = _import_mini(client)
    doc_id = doc["id"]

    start = client.post("/api/sessions", json={"document_id": doc_id})
    assert start.status_code == 200, start.text
    payload = start.json()
    questions = payload["questions"]
    assert len(questions) == 2
    assert all("answer" not in q for q in questions), "answers must not leak to the quiz UI"
    assert questions[0]["options"] == ["A. one", "B. two", "C. three", "D. four"]

    # answers are entered first, otherwise nothing can be graded
    client.put(f"/api/documents/{doc_id}/answers",
               json={"answers": {"Q001": "A", "Q002": "C"}})

    start = client.post("/api/sessions", json={"document_id": doc_id})
    payload = start.json()
    q1, q2 = payload["questions"]
    session_id = payload["session_id"]

    submit = client.post(
        f"/api/sessions/{session_id}/submit",
        json={"answers": {str(q1["id"]): "A", str(q2["id"]): "B"}},
    )
    assert submit.status_code == 200, submit.text
    result = submit.json()
    assert result["total"] == 2
    assert result["graded"] == 2
    assert result["correct"] == 1
    first, second = result["items"]
    assert first["is_correct"] is True and first["answer"] == "A"
    assert second["is_correct"] is False and second["answer"] == "C"

    history = client.get(f"/api/documents/{doc_id}/history").json()
    assert history and history[0]["correct"] == 1


def test_submit_unknown_session(client) -> None:
    assert client.post("/api/sessions/999999/submit", json={}).status_code == 404
    assert client.post("/api/sessions", json={"document_id": 999999}).status_code == 404


def test_asset_serving(client, sat_pdf: Path) -> None:
    doc = upload(client, "sat-sample.pdf", sat_pdf.read_bytes()).json()
    doc_id = doc["id"]
    questions = client.get(f"/api/documents/{doc_id}/questions").json()
    images = [img for q in questions for img in q["images"]]
    assert images, "the fixture PDF must produce at least one figure"

    name = images[0].removeprefix("assets/")
    resp = client.get(f"/api/documents/{doc_id}/assets/{name}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert client.get(f"/api/documents/{doc_id}/assets/..%2Fapp.db").status_code in (400, 404)
    assert client.get(f"/api/documents/{doc_id}/assets/nope.png").status_code == 404


def test_delete_document(client) -> None:
    doc = _import_mini(client)
    doc_id = doc["id"]
    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get(f"/api/documents/{doc_id}").status_code == 404


def test_list_documents(client) -> None:
    docs = client.get("/api/documents").json()
    assert isinstance(docs, list)
    assert all("question_count" in d for d in docs)
