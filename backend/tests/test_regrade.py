"""Post-submit answer-key flow: attempt without a key -> fill key -> regrade."""

from __future__ import annotations

from tests.conftest import MINI_SATMD, upload


def _import_mini(client) -> int:
    resp = upload(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _start(client, doc_id: int) -> tuple[int, list[dict]]:
    resp = client.post("/api/sessions", json={"document_id": doc_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["session_id"], body["questions"]


def test_submit_without_key_then_regrade(client) -> None:
    doc_id = _import_mini(client)
    session_id, questions = _start(client, doc_id)
    ids = [str(q["id"]) for q in questions]

    # exam with no key in the source: submit grades nothing
    res = client.post(
        f"/api/sessions/{session_id}/submit",
        json={"answers": {ids[0]: "B", ids[1]: "A"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["graded"] == 0
    assert body["correct"] == 0
    assert [i["chosen"] for i in body["items"]] == ["B", "A"]

    # user fills the key afterwards, then regrades from stored choices
    client.put(
        f"/api/documents/{doc_id}/answers", json={"answers": {"Q001": "B", "Q002": "D"}}
    )
    re = client.post(f"/api/sessions/{session_id}/regrade")
    assert re.status_code == 200, re.text
    graded = re.json()
    assert graded["graded"] == 2
    assert graded["correct"] == 1
    assert [i["is_correct"] for i in graded["items"]] == [True, False]
    assert [i["chosen"] for i in graded["items"]] == ["B", "A"]
    assert [i["answer"] for i in graded["items"]] == ["B", "D"]


def test_regrade_is_repeatable(client) -> None:
    doc_id = _import_mini(client)
    session_id, questions = _start(client, doc_id)
    first_id = str(questions[0]["id"])
    client.post(f"/api/sessions/{session_id}/submit", json={"answers": {first_id: "A"}})
    client.put(
        f"/api/documents/{doc_id}/answers", json={"answers": {"Q001": "B", "Q002": "D"}}
    )

    first = client.post(f"/api/sessions/{session_id}/regrade").json()
    second = client.post(f"/api/sessions/{session_id}/regrade").json()
    assert first == second
    # changing the key later changes the grade too
    client.put(
        f"/api/documents/{doc_id}/answers", json={"answers": {"Q001": "A", "Q002": "D"}}
    )
    third = client.post(f"/api/sessions/{session_id}/regrade").json()
    assert third["correct"] == 1
    assert first["correct"] == 0


def test_regrade_requires_submission_and_session(client) -> None:
    doc_id = _import_mini(client)
    session_id, _questions = _start(client, doc_id)          # never submitted
    assert client.post(f"/api/sessions/{session_id}/regrade").status_code == 409
    assert client.post("/api/sessions/999999/regrade").status_code == 404
