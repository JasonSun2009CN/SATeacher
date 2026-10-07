"""Optional server-side math rendering: TeX -> SVG via the MathJax Node bridge.

Export must never fail because of math. If Node or the bundled bridge is not
installed, every formula degrades to escaped plain text. Results are cached per
process, so repeated exports of the same formulas only shell out once.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

_BRIDGE_DIR = Path(__file__).resolve().parent / "mathjax"
_BRIDGE = _BRIDGE_DIR / "render.mjs"
_NODE = shutil.which("node")

_CACHE: dict[tuple[str, bool], str | None] = {}
_LOCK = threading.Lock()

# $$..$$  \[..\]  \(..\)  $..$   (remark-math compatible)
_MATH_RE = re.compile(
    r"\$\$(?P<block>.+?)\$\$"
    r"|\\\[(?P<bracket>.+?)\\\]"
    r"|\\\((?P<paren>.+?)\\\)"
    r"|\$(?P<inline>.+?)\$",
    re.DOTALL,
)


def available() -> bool:
    """True when Node + the installed MathJax bridge can render."""
    return bool(_NODE) and _BRIDGE.is_file() and (_BRIDGE_DIR / "node_modules").is_dir()


def split_math(text: str):
    """Yield ``("text", value)`` / ``("math", (tex, display))`` segments."""
    if not text:
        return
    pos = 0
    for match in _MATH_RE.finditer(text):
        if match.start() > pos:
            yield ("text", text[pos : match.start()])
        if match.group("block") is not None:
            yield ("math", (match.group("block").strip(), True))
        elif match.group("bracket") is not None:
            yield ("math", (match.group("bracket").strip(), True))
        elif match.group("paren") is not None:
            yield ("math", (match.group("paren").strip(), False))
        else:
            yield ("math", (match.group("inline").strip(), False))
        pos = match.end()
    if pos < len(text):
        yield ("text", text[pos:])


def collect_math(texts) -> list[tuple[str, bool]]:
    """Ordered, de-duplicated ``(tex, display)`` pairs found across ``texts``."""
    seen: list[tuple[str, bool]] = []
    for text in texts:
        for kind, value in split_math(text or ""):
            if kind == "math" and value not in seen:
                seen.append(value)
    return seen


def _render_batch(items: list[tuple[str, bool]]) -> list[str | None]:
    payload = json.dumps([{"tex": tex, "display": disp} for tex, disp in items])
    try:
        proc = subprocess.run(
            [_NODE, str(_BRIDGE)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_BRIDGE_DIR),
        )
    except (OSError, subprocess.SubprocessError):
        return [None] * len(items)
    if proc.returncode != 0:
        return [None] * len(items)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        return [None] * len(items)
    if not isinstance(out, list):
        return [None] * len(items)
    return [s if isinstance(s, str) and s else None for s in out]


def render(items: list[tuple[str, bool]]) -> dict[tuple[str, bool], str | None]:
    """Resolve ``(tex, display)`` -> SVG string (or None) for every item."""
    todo: list[tuple[str, bool]] = []
    with _LOCK:
        for item in items:
            if item not in _CACHE:
                todo.append(item)
    if todo:
        svgs = _render_batch(todo) if available() else [None] * len(todo)
        with _LOCK:
            for item, svg in zip(todo, svgs):
                _CACHE[item] = svg
    with _LOCK:
        return {item: _CACHE.get(item) for item in items}