import os
import tempfile

os.environ.setdefault("SATEACHER_DATA", tempfile.mkdtemp(prefix="sateacher-test-"))

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from tests.fixtures import build_sat_docx, build_sat_pdf, build_scanned_pdf  # noqa: E402

MINI_SATMD = """---
satmd: 1
title: "Mini Bank"
source: "mini.md"
lang: en
answers: none
---

<!-- instructions ignored -->

:::q {#Q001 sec=rw no=1}
@stem
Which choice best completes the sentence?

- A. one
- B. two
- C. three
- D. four
:::

:::q {#Q002 sec=math no=2}
@stem
What is the value of $x$ if $x + 2 = 5$?

- A. 1
- B. 3
- C. 5
- D. 7
:::
"""


@pytest.fixture(scope="session")
def sat_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_sat_pdf(tmp_path_factory.mktemp("pdf") / "sat-sample.pdf")


@pytest.fixture(scope="session")
def sat_docx(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_sat_docx(tmp_path_factory.mktemp("docx") / "sat-sample.docx")


@pytest.fixture(scope="session")
def sat_scanned(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_scanned_pdf(tmp_path_factory.mktemp("scan") / "sat-scanned.pdf")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def upload(client, filename: str, content: bytes | str):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return client.post("/api/documents", files={"file": (filename, content, "application/octet-stream")})
