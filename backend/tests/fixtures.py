"""Build a small SAT-like PDF used by the converter tests.

Covers: instructions before Q1, section headings, multi-paragraph material,
wrapped lines, wrapped options, one-line and two-per-line options, an embedded
bitmap, a vector figure, and an answer key on the last page.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

W, H = 612, 792


def _bitmap() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40))
    for y in range(40):
        for x in range(60):
            pix.set_pixel(x, y, (40 + x * 3, 90 + y * 3, 160))
    return pix.tobytes("png")


def build_sat_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    p1 = doc.new_page(width=W, height=H)
    p1.insert_text((60, 50), "SAT Practice Test — Sample", fontsize=16)
    p1.insert_text((60, 70), "Instructions: Choose the best answer for each question.",
                   fontsize=11)
    p1.insert_text((60, 95), "Section 1: Reading and Writing", fontsize=13)

    # Q1 — multi-paragraph material, question, one option per line
    p1.insert_text((60, 125), "1. Despite the committee's reservations about the cost, the new policy was",
                   fontsize=10)
    p1.insert_text((60, 140), "adopted without amendment. Critics called the decision premature, but",
                   fontsize=10)
    p1.insert_text((60, 155), "supporters insisted that the available data justified action.", fontsize=10)
    p1.insert_text((60, 180), "The author's attitude toward the committee is best described as",
                   fontsize=10)
    for i, opt in enumerate(["A. dismissive", "B. cautiously optimistic",
                             "C. indifferent", "D. hostile"]):
        p1.insert_text((80, 195 + i * 15), opt, fontsize=10)

    # Q2 — a wrapped option line
    p1.insert_text((60, 275), "2. The scientist's findings were considered ___ by her peers.",
                   fontsize=10)
    p1.insert_text((80, 290), "A. unprecedented", fontsize=10)
    p1.insert_text((80, 305), "B. well established and widely cited in the", fontsize=10)
    p1.insert_text((80, 317), "field for nearly a decade", fontsize=10)
    p1.insert_text((80, 332), "C. poorly funded", fontsize=10)
    p1.insert_text((80, 347), "D. overly cautious", fontsize=10)

    # Q3 — embedded bitmap between the stem and the options
    p1.insert_text((60, 375), "3. Based on the graph, how many students chose option B?", fontsize=10)
    p1.insert_image(pymupdf.Rect(80, 385, 240, 445), stream=_bitmap())
    for i, opt in enumerate(["A. 12", "B. 18", "C. 24", "D. 30"]):
        p1.insert_text((80, 465 + i * 15), opt, fontsize=10)

    # Section 2 — Math
    p1.insert_text((60, 560), "Section 2: Math", fontsize=13)

    # Q4 — vector figure (axes) + all four options on one line
    p1.insert_text((60, 585), "4. If 3x + 5 = 20, what is the value of x?", fontsize=10)
    p1.draw_line((80, 630), (300, 630), color=(0, 0, 0), width=1)      # x axis
    p1.draw_line((80, 630), (80, 580), color=(0, 0, 0), width=1)      # y axis
    p1.draw_line((80, 630), (300, 605), color=(0.6, 0.1, 0.1), width=1)
    for t in range(0, 6):
        p1.draw_line((80 + t * 40, 630), (80 + t * 40, 624), color=(0, 0, 0), width=1)
    p1.insert_text((80, 655), "(A) 3     (B) 5     (C) 8     (D) 15", fontsize=10)

    # Q5 — two options per line
    p1.insert_text((60, 685), "5. What is the area of a rectangle with length 8 and width 5?",
                   fontsize=10)
    p1.insert_text((80, 700), "A. 13     B. 40", fontsize=10)
    p1.insert_text((80, 715), "C. 26     D. 60", fontsize=10)

    p2 = doc.new_page(width=W, height=H)
    p2.insert_text((60, 50), "Answer Key", fontsize=13)
    p2.insert_text((60, 80), "1. A   2. C   3. B   4. D   5. A", fontsize=11)

    doc.save(path)
    doc.close()
    return path


def build_numberless_pdf(path: Path) -> Path:
    """A PDF whose questions are not numbered — must be rejected cleanly."""
    doc = pymupdf.open()
    page = doc.new_page(width=W, height=H)
    page.insert_text((60, 50), "No numbering here", fontsize=14)
    page.insert_text((60, 80), "Which of the following is true?", fontsize=10)
    for i, opt in enumerate(["A. one", "B. two", "C. three", "D. four"]):
        page.insert_text((80, 100 + i * 15), opt, fontsize=10)
    doc.save(path)
    doc.close()
    return path


BW, BH = 610, 790          # Bluebook-style page geometry


def _bluebook_row(page, no: int, top: float, passage: tuple[str, ...],
                  stem: tuple[str, ...], options: dict[str, tuple[str, str | None]]) -> None:
    """One two-column row: passage left, badge + stem + options right."""
    for i, line in enumerate(passage):
        page.insert_text((57, top + 8 + i * 15), line, fontsize=10)
    page.insert_text((319, top + 20), f" {no}", fontsize=11)         # detached badge (own baseline+size)
    for i, line in enumerate(stem):
        page.insert_text((319, top + 40 + i * 15), line, fontsize=10)
    y = top + 40 + len(stem) * 15 + 16
    for letter, (first, cont) in options.items():
        page.insert_text((327, y), f"{letter} {first}", fontsize=10)
        if cont:
            page.insert_text((347, y + 12), cont, fontsize=10)
            y += 12
        y += 18


def build_bluebook_pdf(path: Path) -> Path:
    """Bluebook two-column export mimicking real exam-scrap PDFs.

    Detached digit badges in the right column, lowercase options with an
    indented continuation line, page chrome (header, footer date, book page
    numbers), a stray mid-right digit that must not become a question, and an
    interior bitmap figure in the left column.
    """
    doc = pymupdf.open()
    rows = {
        1: (("Like all hummingbirds feed on nectar daily",),
            ("Which choice completes the text with the most logical",),
            {"a": ("elusive", None),
             "b": ("well established and widely cited in the", "field for nearly a decade"),
             "c": ("indifferent", None), "d": ("hostile", None)}),
        2: (("Emerging bioacoustics tools track wildlife",),
            ("Which choice completes the text with the most logical",),
            {"a": ("attributed", None), "b": ("underpinned", None),
             "c": ("surmounted", None), "d": ("subjugated", None)}),
        3: (("As scholarship, the volume breaks new ground",),
            ("The author's attitude toward the volume is best described",),
            {"a": ("admiring", None), "b": ("skeptical", None),
             "c": ("neutral", None), "d": ("baffled", None)}),
        4: (("The ______ of leaf-vein architectures matters",),
            ("Which choice completes the text with the most logical",),
            {"a": ("multifariousness", None), "b": ("obstinacy", None),
             "c": ("entanglement", None), "d": ("terseness", None)}),
    }

    def content_page(page, page_nos: tuple[int, int]) -> None:
        page.insert_text((57, 50), "Section 1, Module 2: Reading and Writing", fontsize=12)
        _bluebook_row(page, page_nos[0], 90, *rows[page_nos[0]])
        _bluebook_row(page, page_nos[1], 410, *rows[page_nos[1]])
        page.insert_text((299, 723), str(40 + page_nos[0]), fontsize=10)   # book page no.
        page.insert_text((454, 722), "September 13, 2025 (US)", fontsize=9)

    p1 = doc.new_page(width=BW, height=BH)
    content_page(p1, (1, 2))
    # stray standalone digit in the right column between the two rows:
    # a candidate badge whose row has no options — must be skipped, not break Q2
    p1.insert_text((400, 355), "42", fontsize=10)

    p2 = doc.new_page(width=BW, height=BH)
    content_page(p2, (3, 4))
    # interior bitmap figure inside row 2's left column (Q4 material)
    p2.insert_image(pymupdf.Rect(60, 445, 170, 495), stream=_bitmap())

    doc.save(path)
    doc.close()
    return path
