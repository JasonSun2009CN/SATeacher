#!/usr/bin/env python3
"""Build a built-in question bank from an SAT PDF collection.

Splits the source PDF into per-module segments (TOC/divider driven), runs
each segment through the deterministic converter, attaches the answer key
found at the tail of the PDF, and writes the result under

    backend/app/builtin/<bank-id>/manifest.json
    backend/app/builtin/<bank-id>/<unit-id>/doc.sat.md
    backend/app/builtin/<bank-id>/<unit-id>/assets/*.png

Usage:
    scripts/build_builtin.py <source.pdf> <bank-id> "<display title>"

Everything here is offline and token-free; the app later serves the
pre-built satmd files as one-click library additions.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.convert.pdf import ConvertError, convert_pdf  # noqa: E402
from app.satmd.parser import SatMdError, parse, set_answer  # noqa: E402

VARIANT_RE = re.compile(r"^(Routing|Harder)\s+([A-Z])$")
DATE_RE = re.compile(r"^\d{2}年\s*\d{1,2}月")
MODULE_RE = re.compile(r"Section 1, Module (\d+)")
DIVIDER_MAX_LEN = 150          # divider pages are tiny headers
REGION_IDS = {"北美": "us", "亚太": "apac"}

# Bluebook running header on content pages: "August 23, 2025 (US)" etc.
# This is the authoritative exam identity — the source PDF's TOC has been
# found to contain scrambled rows (12月 block), dividers/content never disagree.
CONTENT_DATE_RE = re.compile(r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s*\(([^)]+)\)")
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}
REGION_BY_TAG = {"US": "北美", "International": "亚太"}


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def die(msg: str) -> None:
    print(f"BUILD FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# divider pages (unit boundaries) and table of contents
# --------------------------------------------------------------------------

def find_dividers(doc: pymupdf.Document) -> list[int]:
    out = []
    for i in range(doc.page_count):
        text = nfkc(doc[i].get_text()).strip()
        if len(text) < DIVIDER_MAX_LEN and ("合集" in text or text.startswith("答案")):
            out.append(i)
    return out


def parse_toc(doc: pymupdf.Document, pages: range) -> list[dict]:
    """Return [{date, variant, page}] in document order (NFKC-normalised).

    The trailing answer-table entry has variant "答案".
    """
    entries: list[dict] = []
    for pno in pages:
        lines = [l.strip() for l in nfkc(doc[pno].get_text()).splitlines() if l.strip()]
        date: str | None = None
        for i, line in enumerate(lines):
            if DATE_RE.match(line):
                date = line
                continue
            if i + 1 >= len(lines) or not lines[i + 1].isdigit():
                continue
            page = int(lines[i + 1])
            if line == "答案":
                entries.append({"date": None, "variant": "答案", "page": page})
            elif date and VARIANT_RE.match(line):
                entries.append({"date": date, "variant": line, "page": page})
    if not entries:
        die("no TOC entries found before the first divider")
    if entries[-1]["variant"] != "答案":
        die("TOC has no trailing 答案 entry — unexpected layout")
    return entries


def unit_date_label(doc: pymupdf.Document, start: int, end: int, fallback: str | None) -> str:
    """Authoritative exam identity from the Bluebook running header.

    e.g. "August 23, 2025 (US)" -> "25年8月北美". Majority vote across pages;
    unknown month/region tokens fail loudly rather than guessing.
    """
    votes: Counter[tuple[int, int, str]] = Counter()
    for pno in range(start, end + 1):
        for m in CONTENT_DATE_RE.finditer(nfkc(doc[pno].get_text())):
            month_name, _day, year, tag = m.groups()
            if month_name not in MONTHS:
                die(f"p{pno+1}: unknown month in exam date {m.group(0)!r}")
            if tag not in REGION_BY_TAG:
                die(f"p{pno+1}: unknown region tag in exam date {m.group(0)!r}")
            votes[(int(year) % 100, MONTHS[month_name], REGION_BY_TAG[tag])] += 1
    if not votes:
        if fallback:
            return fallback
        die(f"no exam date found on pages {start + 1}-{end + 1}")
    (yy, mm, region), _n = votes.most_common(1)[0]
    if len(votes) > 1:
        print(f"  note: mixed exam dates on pp{start + 1}-{end + 1}: {dict(votes)}")
    return f"{yy}年{mm}月{region}"


def align_units(entries: list[dict], dividers: list[int], doc: pymupdf.Document) -> list[dict]:
    """Validate divider positions against the TOC, then derive unit identity.

    Position check: every divider's printed page number must equal the TOC
    entry's page (held for all 45 dividers). Identity: the divider's variant
    line (has the A/B/C letter) + the content pages' English exam date.
    The source TOC is known to have scrambled rows in the 12月 block, so a
    TOC/content disagreement is reported but content wins.
    """
    if len(dividers) != len(entries):
        die(
            f"divider count {len(dividers)} != TOC entries {len(entries)}; "
            f"dividers(0-based)={dividers}"
        )
    units = []
    for k, e in enumerate(entries):
        lines = [
            l.strip()
            for l in nfkc(doc[dividers[k]].get_text()).splitlines()
            if l.strip()
        ]
        nums = [l for l in lines if l.isdigit()]
        if not nums or int(nums[-1]) != e["page"]:
            die(
                f"divider p{dividers[k]+1} printed number "
                f"{nums[-1] if nums else '?'} != TOC page {e['page']} (order drift)"
            )
        if e["variant"] == "答案":
            if "答案" not in lines:
                die(f"divider p{dividers[k]+1} should be 答案, got: {lines}")
            continue
        start = dividers[k] + 1
        end = (dividers[k + 1] if k + 1 < len(dividers) else doc.page_count) - 1
        if start > end:
            die(f"unit {e} has empty page range")
        variant_lines = [l for l in lines if VARIANT_RE.match(l)]
        if not variant_lines:
            die(f"divider p{dividers[k]+1} has no variant line: {lines}")
        variant = variant_lines[0]
        date = unit_date_label(doc, start, end, fallback=e["date"])
        if (date, variant) != (e["date"], e["variant"]):
            print(
                f"  note: pp{start + 1}-{end + 1} TOC says {e['date']} · {e['variant']}, "
                f"content/divider say {date} · {variant} -> using content"
            )
        units.append(
            {"date": date, "variant": variant, "pdf_start": start, "pdf_end": end}
        )
    return units


# --------------------------------------------------------------------------
# answer key (tail pages): label-anchored, coordinate based
# --------------------------------------------------------------------------

def parse_answer_key(doc: pymupdf.Document, start: int, end: int) -> dict[tuple[str, str], dict[int, str]]:
    keys: dict[tuple[str, str], dict[int, str]] = {}
    for pno in range(start, end + 1):
        page = doc[pno]
        # (x0, y0, x1, y1, word) with NFKC-normalised word text
        words = [(w[0], w[1], w[2], w[3], nfkc(w[4])) for w in page.get_text("words")]
        dates = [w for w in words if "年" in w[4] and "月" in w[4]]
        labels = []
        for j, w in enumerate(words):
            if w[4] in ("Routing", "Harder") and j + 1 < len(words):
                nxt = words[j + 1]
                if len(nxt[4]) == 1 and nxt[4].isalpha() and abs(nxt[1] - w[1]) < 6:
                    labels.append({
                        "variant": f"{w[4]} {nxt[4]}",
                        "y": (w[1] + nxt[1]) / 2,
                        "cx": (w[0] + nxt[2]) / 2,
                    })
        if not labels:
            continue
        # group labels into rows (same table header line)
        labels.sort(key=lambda l: l["y"])
        rows: list[list[dict]] = []
        for lab in labels:
            if rows and abs(lab["y"] - rows[-1][0]["y"]) < 8:
                rows[-1].append(lab)
            else:
                rows.append([lab])

        page_date: str | None = None
        for ri, lab_row in enumerate(rows):
            row_top = lab_row[0]["y"]
            # date title: nearest date word above this row
            above = [d for d in dates if d[1] < row_top]
            if above:
                page_date = max(above, key=lambda d: d[1])[4]
            if page_date is None:
                die(f"p{pno+1}: answer table without a date title above it")

            band_top = row_top + 4
            band_bottom = rows[ri + 1][0]["y"] - 4 if ri + 1 < len(rows) else page.rect.height
            in_band = [w for w in words if band_top <= w[1] <= band_bottom]
            pairs = _pair_numbers_letters(in_band)
            for lab in lab_row:
                others = [l for l in lab_row if l is not lab]
                mine = [
                    (no, let)
                    for no, let, px in pairs
                    if all(abs(px - lab["cx"]) <= abs(px - o["cx"]) for o in others)
                ]
                table = dict(mine)
                if len(mine) != 27 or set(table) != set(range(1, 28)):
                    die(
                        f"p{pno+1} {page_date} {lab['variant']}: expected answers 1..27, "
                        f"got {sorted(table)} ({len(table)} entries, {len(mine)} pairs)"
                    )
                if any(v not in "ABCD" for v in table.values()):
                    die(f"p{pno+1} {page_date} {lab['variant']}: bad letters {table}")
                key = (nfkc(page_date), lab["variant"])
                if key in keys:
                    die(f"duplicate answer table {key}")
                keys[key] = table
    return keys


def _pair_numbers_letters(words: list[tuple]) -> list[tuple[int, str, float]]:
    """Group by line (y), then walk x order pairing digits with A-D letters."""
    cands = [
        w
        for w in words
        if (re.fullmatch(r"\d{1,2}", w[4]) and 1 <= int(w[4]) <= 27)
        or (len(w[4]) == 1 and w[4] in "ABCD")
    ]
    cands.sort(key=lambda w: (w[1], w[0]))
    out: list[tuple[int, str, float]] = []
    row: list[tuple] = []
    for w in cands:
        if row and w[1] - row[-1][1] > 4:
            out.extend(_pair_row(row))
            row = []
        row.append(w)
    out.extend(_pair_row(row))
    return out


def _pair_row(row: list[tuple]) -> list[tuple[int, str, float]]:
    row.sort(key=lambda w: w[0])                   # left to right
    out: list[tuple[int, str, float]] = []
    i = 0
    while i + 1 < len(row):
        a, b = row[i], row[i + 1]
        if re.fullmatch(r"\d{1,2}", a[4]) and b[4] in "ABCD":
            out.append((int(a[4]), b[4], (a[0] + b[2]) / 2))
            i += 2
        elif a[4] in "ABCD" and re.fullmatch(r"\d{1,2}", b[4]):
            out.append((int(b[4]), a[4], (a[0] + b[2]) / 2))
            i += 2
        else:
            i += 1
    return out


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def slug_unit(date: str, variant: str) -> str:
    m = re.match(r"(\d{2})年\s*(\d{1,2})月\s*(.+)", date)
    if not m:
        return re.sub(r"[^a-z0-9]+", "-", f"{date}-{variant}".lower()).strip("-")
    yy, mm, region = m.groups()
    reg = REGION_IDS.get(region.strip(), "cn")
    vid = re.sub(r"[^a-z0-9]+", "-", variant.lower()).strip("-")
    return f"{yy}{int(mm):02d}-{reg}-{vid}"


def detect_module(doc: pymupdf.Document, start: int, end: int) -> int | None:
    counts: Counter[int] = Counter()
    for pno in range(start, end + 1):
        for m in MODULE_RE.finditer(nfkc(doc[pno].get_text())):
            counts[int(m.group(1))] += 1
    return counts.most_common(1)[0][0] if counts else None


def build(pdf: Path, bank_id: str, bank_title: str, out_root: Path) -> int:
    doc = pymupdf.open(pdf)
    dividers = find_dividers(doc)
    if not dividers:
        die("no divider pages found — unsupported source layout")
    entries = parse_toc(doc, range(0, dividers[0]))
    units = align_units(entries, dividers, doc)

    a_start = dividers[-1] + 1
    a_end = doc.page_count - 1
    print(f"TOC: {len(units)} units · answer pages p{a_start+1}-p{a_end+1}")
    keys = parse_answer_key(doc, a_start, a_end)
    print(f"answer key tables parsed: {len(keys)}")

    missing = [
        (u["date"], u["variant"]) for u in units if (u["date"], u["variant"]) not in keys
    ]
    if missing:
        die(f"no answer table for units: {missing}")

    bank_dir = out_root / bank_id
    if bank_dir.exists():
        shutil.rmtree(bank_dir)
    bank_dir.mkdir(parents=True)

    report = []
    failures = []
    shortfall = 0  # questions absent from incomplete source units (warned below)
    with tempfile.TemporaryDirectory(prefix="builtin-") as tmpdir:
        for u in units:
            title = f"{u['date']} · {u['variant']}"
            unit_id = slug_unit(u["date"], u["variant"])
            if any(r["id"] == unit_id for r in report):
                failures.append(f"{title}: duplicate unit id {unit_id}")
                continue
            module = detect_module(doc, u["pdf_start"], u["pdf_end"])
            want_module = 1 if u["variant"].startswith("Routing") else 2
            if module is not None and module != want_module:
                failures.append(
                    f"{title}: content header says Module {module}, "
                    f"variant {u['variant']} implies Module {want_module}"
                )
                continue
            try:
                seg = pymupdf.open()
                seg.insert_pdf(doc, from_page=u["pdf_start"], to_page=u["pdf_end"])
                seg_path = Path(tmpdir) / f"{unit_id}.pdf"
                seg.save(seg_path)
                seg.close()
                conv = convert_pdf(seg_path, title=title)
            except ConvertError as exc:
                failures.append(f"{title}: ConvertError: {exc}")
                continue

            key = keys[(u["date"], u["variant"])]
            try:
                first = parse(conv.satmd)
            except SatMdError as exc:
                failures.append(f"{title}: converted satmd invalid: {exc}")
                continue
            nos = [q.no for q in first.questions]
            if len(first.questions) != conv.question_count or any(n is None for n in nos):
                failures.append(f"{title}: converter produced unnumbered questions")
                continue
            if sorted(nos) != list(range(1, len(nos) + 1)):
                failures.append(f"{title}: question numbers not contiguous 1..N: {sorted(nos)}")
                continue
            missing_no = sorted(set(nos) - set(key))
            if missing_no:
                failures.append(f"{title}: answer key missing entries {missing_no}")
                continue
            if len(nos) < 27:
                # Source defect (verified: no numbering gaps, so 1..N still aligns).
                shortfall += 27 - len(nos)
                print(
                    f"  warn {title}: source unit has {len(nos)} of 27 questions — "
                    "publishing as-is"
                )
            satmd = conv.satmd
            try:
                for q in first.questions:
                    satmd = set_answer(satmd, q.ext_id, key[q.no])
            except (KeyError, ValueError) as exc:
                failures.append(f"{title}: answer injection failed: {exc}")
                continue
            satmd = re.sub(r"(?m)^answers: none$", "answers: external", satmd, count=1)
            satmd = re.sub(r'(?m)^source: ".*"$', f'source: "{pdf.name}"', satmd, count=1)

            try:
                parsed = parse(satmd)
            except SatMdError as exc:
                failures.append(f"{title}: generated satmd invalid: {exc}")
                continue
            if len(parsed.questions) != conv.question_count:
                failures.append(
                    f"{title}: parse got {len(parsed.questions)} != convert {conv.question_count}"
                )
                continue
            if parsed.meta.get("answers") != "external":
                failures.append(f"{title}: front matter answers != external")
                continue
            if any(not q.answer for q in parsed.questions):
                failures.append(f"{title}: some questions ended up without an answer")
                continue

            unit_dir = bank_dir / unit_id
            unit_dir.mkdir()
            (unit_dir / "doc.sat.md").write_text(satmd, encoding="utf-8")
            if conv.assets:
                (unit_dir / "assets").mkdir()
                for name, data in conv.assets.items():
                    (unit_dir / "assets" / name).write_bytes(data)

            answered = sum(1 for q in parsed.questions if q.answer)
            report.append({
                "id": unit_id,
                "title": title,
                "module": module,
                "questions": len(parsed.questions),
                "answers": answered,
                "assets": len(conv.assets),
                "warnings": len(conv.warnings),
            })
            print(
                f"  ok  {unit_id:<26} {title:<30} M{module} "
                f"{len(parsed.questions):>2}q {answered:>2}a "
                f"{len(conv.assets)}img warn={len(conv.warnings)}"
            )

    manifest = {
        "id": bank_id,
        "title": bank_title,
        "source": pdf.name,
        "units": [
            {k: r[k] for k in ("id", "title", "module", "questions", "answers", "assets")}
            for r in report
        ],
    }
    (bank_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    total_q = sum(r["questions"] for r in report)
    total_a = sum(r["answers"] for r in report)
    print(
        f"\n{len(report)}/{len(units)} units built · {total_q} questions · "
        f"{total_a} answers · {sum(r['assets'] for r in report)} images"
    )
    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
    ok = (
        not failures
        and len(report) == len(units)
        and total_q == 27 * len(units) - shortfall  # known source defects excluded
        and total_a == total_q
    )
    print(f"{'OK' if ok else 'INCOMPLETE'} -> {bank_dir}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("bank_id")
    ap.add_argument("title")
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO / "backend" / "app" / "builtin",
        help="output root (default: backend/app/builtin)",
    )
    args = ap.parse_args()
    if not args.pdf.is_file():
        die(f"no such file: {args.pdf}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.bank_id):
        die(f"bank id must be lowercase slug, got {args.bank_id!r}")
    return build(args.pdf, args.bank_id, args.title, args.out)


if __name__ == "__main__":
    sys.exit(main())
