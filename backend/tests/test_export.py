"""Batch-4 exports: questions + answers + explanations as md / csv / json."""

from __future__ import annotations

import csv
import io
import json

from tests.conftest import MINI_SATMD, upload

EXPLAIN = 'Because x + 2 = 5, so x = 3; watch the "quotes", too.'


def _doc_with_explain(client) -> int:
    resp = upload(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["id"]
    questions = client.get(f"/api/documents/{doc_id}/questions").json()
    client.put(
        f"/api/documents/{doc_id}/answers", json={"answers": {"Q001": "B", "Q002": "D"}}
    )
    ok = client.put(
        f"/api/documents/{doc_id}/questions/{questions[1]['id']}/explain",
        json={"content": EXPLAIN},
    )
    assert ok.status_code == 200, ok.text
    return doc_id


def test_export_json(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/json")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    assert ".json" in resp.headers["content-disposition"]

    data = json.loads(resp.content)
    assert data["title"] == "Mini Bank"
    assert len(data["questions"]) == 2
    q1, q2 = data["questions"]
    assert q1["answer"] == "B"
    assert q1["options"] == {"A": "one", "B": "two", "C": "three", "D": "four"}
    assert q1["explain"] is None
    assert q2["answer"] == "D"
    assert q2["explain"] == EXPLAIN
    assert q2["stem"].startswith("What is the value")


def test_export_csv_roundtrip(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert ".csv" in resp.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8"))))
    assert rows[0] == [
        "no", "sec", "source", "material", "stem", "A", "B", "C", "D", "answer", "explain",
    ]
    assert len(rows) == 3
    assert rows[1][0] == "1" and rows[1][9] == "B"
    # commas and quotes in explanations survive CSV quoting
    assert rows[2][10] == EXPLAIN
    assert rows[2][8] == "7"          # option D text


def test_export_markdown(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert ".md" in resp.headers["content-disposition"]

    text = resp.content.decode("utf-8")
    assert text.startswith("# Mini Bank")
    assert "## Question 1 · Reading & Writing" in text
    assert "**Answer:** B" in text
    assert "**Answer:** D" in text
    assert "**Explanation:**" in text
    assert EXPLAIN in text
    assert "- A. one" in text
    assert text.count("## Question") == 2


def test_export_validation(client) -> None:
    doc_id = _doc_with_explain(client)
    assert client.get(f"/api/documents/{doc_id}/export/pdf").status_code == 400
    assert client.get("/api/documents/999999/export/json").status_code == 404
