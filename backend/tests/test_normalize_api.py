"""CB-style normalization — the whole-document run and the single-question API.

The batch-12 code shipped untested and could not have worked end to end
(``options`` was a list where a dict was assumed, and the write path used a
renderer built for a different dataclass). These tests pin the working
contract: applied rewrites survive round-trip, failures keep the original,
answers/sources never move.
"""

from __future__ import annotations

import json
import time

import pytest

from tests.conftest import upload

ANSWERED_SATMD = """---
satmd: 1
title: "Answered Bank"
source: "answered.md"
lang: en
answers: inline
---

:::q {#Q001 sec=rw no=1 type=mc difficulty=e}
@material
The passage below was written in 1902.

@stem
Which choice best completes the sentence?

- A. one
- B. two
- C. three
- D. four
! answer: B
! source: p.1
:::

:::q {#Q002 sec=math no=2}
@stem
What is the value of $x$ if $x + 2 = 5$?

- A. 1
- B. 3
- C. 5
- D. 7
! answer: C
:::
"""

NO_ANSWER_SATMD = """---
satmd: 1
title: "No Answers"
source: "none.md"
lang: en
answers: none
---

:::q {#Q001 sec=rw no=1}
@stem
Which choice best completes the sentence?

- A. one
- B. two
- C. three
- D. four
:::
"""


def _patch_llm(monkeypatch: pytest.MonkeyPatch, transform):
    """Fake the LLM: each call echoes the question JSON through ``transform``."""
    calls: list[dict] = []

    def complete(system, messages, **kwargs):    # noqa: ANN001
        payload = json.loads(messages[0]["content"])
        calls.append(payload)
        return json.dumps(transform(payload))

    monkeypatch.setattr("app.llm.configured", lambda: True)
    monkeypatch.setattr("app.llm.complete", complete)
    return calls


def _wait_status(client, doc_id: int, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while True:
        resp = client.get(f"/api/documents/{doc_id}/normalize")
        assert resp.status_code == 200, resp.text
        job = resp.json()
        if job["status"] != "running":
            return job
        assert time.time() < deadline, f"normalization never finished: {job}"
        time.sleep(0.01)


def _create(client, text: str, name: str = "bank.sat.md") -> int:
    resp = upload(client, name, text)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


# --------------------------------------------------------------------------
# Whole-document run
# --------------------------------------------------------------------------


def test_document_normalize_applies_in_one_pass(client, monkeypatch):
    from app.repos import documents as docs_repo
    from app.satmd.parser import parse

    doc_id = _create(client, ANSWERED_SATMD)
    _patch_llm(monkeypatch, lambda p: {**p, "stem": p["stem"] + " (CB)"})

    resp = client.post(f"/api/documents/{doc_id}/normalize")
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "running"

    job = _wait_status(client, doc_id)
    assert job["status"] == "done", job
    assert (job["total"], job["applied"], job["unchanged"], job["kept"]) == (2, 2, 0, 0)
    assert job["done"] == 2
    assert job["errors"] == []

    qs = client.get(f"/api/documents/{doc_id}/questions").json()
    assert all(q["stem"].endswith("(CB)") for q in qs)
    assert [q["answer"] for q in qs] == ["B", "C"]        # answers untouched
    assert [q["source"] for q in qs] == ["p.1", None]     # citation untouched

    # the file on disk still parses and carries the same questions
    parsed = parse(docs_repo.read_satmd(doc_id))
    assert [q.ext_id for q in parsed.questions] == ["Q001", "Q002"]
    assert parsed.meta["title"] == "Answered Bank"
    assert parsed.questions[0].answer == "B"


def test_document_normalize_keeps_question_when_answer_would_change(client, monkeypatch):
    doc_id = _create(client, ANSWERED_SATMD)

    def broken(payload):
        out = {**payload, "stem": payload["stem"] + " (CB)"}
        if payload["answer"] == "B":
            out["answer"] = "D"
        return out

    _patch_llm(monkeypatch, broken)
    client.post(f"/api/documents/{doc_id}/normalize")
    job = _wait_status(client, doc_id)

    assert job["status"] == "done"
    assert (job["total"], job["applied"], job["kept"]) == (2, 1, 1)
    assert job["errors"] and job["errors"][0].startswith("#Q001:")

    qs = {q["ext_id"]: q for q in client.get(f"/api/documents/{doc_id}/questions").json()}
    assert qs["Q001"]["stem"] == "Which choice best completes the sentence?"
    assert qs["Q001"]["answer"] == "B"
    assert qs["Q002"]["stem"].endswith("(CB)")


def test_document_normalize_rejects_rewrite_that_would_change_answer_via_stem(
    client, monkeypatch
):
    """A stray `! answer:` line smuggled into the stem must not survive the write."""
    doc_id = _create(client, ANSWERED_SATMD)
    _patch_llm(
        monkeypatch,
        lambda p: {**p, "stem": p["stem"] + "\n! answer: D"},
    )

    client.post(f"/api/documents/{doc_id}/normalize")
    job = _wait_status(client, doc_id)

    assert job["applied"] == 0 and job["kept"] == 2
    assert all("stem did not survive" in e for e in job["errors"]), job["errors"]

    qs = client.get(f"/api/documents/{doc_id}/questions").json()
    assert [q["answer"] for q in qs] == ["B", "C"]


def test_document_normalize_skips_questions_without_answers(client, monkeypatch):
    doc_id = _create(client, NO_ANSWER_SATMD)
    calls = _patch_llm(monkeypatch, lambda p: p)

    client.post(f"/api/documents/{doc_id}/normalize")
    job = _wait_status(client, doc_id)

    assert job["status"] == "done"
    assert (job["applied"], job["kept"]) == (0, 1)
    assert calls == []                                     # no token spent


def test_document_normalize_requires_llm(client, monkeypatch):
    doc_id = _create(client, ANSWERED_SATMD)
    monkeypatch.setattr("app.llm.configured", lambda: False)

    resp = client.post(f"/api/documents/{doc_id}/normalize")
    assert resp.status_code == 409
    assert "Settings" in resp.json()["detail"]


def test_normalize_status_unknown_before_any_run(client):
    doc_id = _create(client, ANSWERED_SATMD)
    assert client.get(f"/api/documents/{doc_id}/normalize").status_code == 404


def test_normalize_status_unknown_document(client):
    assert client.get("/api/documents/99999/normalize").status_code == 404


# --------------------------------------------------------------------------
# Single-question API (kept for API compatibility)
# --------------------------------------------------------------------------


def test_single_question_accept_writes_back(client):
    """Batch 12's accept path raised AttributeError; it must now persist."""
    from app.repos import documents as docs_repo
    from app.satmd.parser import parse

    doc_id = _create(client, ANSWERED_SATMD)
    row = client.get(f"/api/documents/{doc_id}/questions").json()[0]

    payload = {
        "material": "The passage below was written in 1902.",
        "stem": "Which choice best completes the sentence? (edited)",
        "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
        "answer": "B",
        "source_ref": "p.1",
    }
    resp = client.post(
        f"/api/documents/{doc_id}/questions/{row['id']}/normalize/accept",
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == row["id"]

    qs = client.get(f"/api/documents/{doc_id}/questions").json()
    assert qs[0]["stem"].endswith("(edited)")
    assert qs[0]["answer"] == "B"
    assert qs[0]["source"] == "p.1"

    parsed = parse(docs_repo.read_satmd(doc_id))
    assert parsed.questions[0].stem.endswith("(edited)")
    assert parsed.questions[1].stem.startswith("What is the value")


def test_single_question_accept_rejects_changed_answer(client):
    doc_id = _create(client, ANSWERED_SATMD)
    row = client.get(f"/api/documents/{doc_id}/questions").json()[0]

    resp = client.post(
        f"/api/documents/{doc_id}/questions/{row['id']}/normalize/accept",
        json={
            "material": None,
            "stem": "Rewritten stem",
            "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
            "answer": "D",
            "source_ref": "",
        },
    )
    assert resp.status_code == 422

    qs = client.get(f"/api/documents/{doc_id}/questions").json()
    assert qs[0]["stem"] == "Which choice best completes the sentence?"


def test_single_question_normalize_shapes_options_as_dict(client, monkeypatch):
    """The list-vs-dict mix-up made this endpoint 500; it must reach the LLM."""
    doc_id = _create(client, ANSWERED_SATMD)
    row = client.get(f"/api/documents/{doc_id}/questions").json()[0]
    calls = _patch_llm(monkeypatch, lambda p: p)

    resp = client.post(f"/api/documents/{doc_id}/questions/{row['id']}/normalize")
    assert resp.status_code == 200, resp.text
    assert calls and list(calls[0]["options"]) == ["A", "B", "C", "D"]
    assert resp.json()["normalized"]["options"]["B"] == "two"
