import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  api,
  ApiError,
  type ResultItem,
  type SessionDetail,
  type SubmitResult,
} from "../api/client";
import RichText from "../components/RichText";
import ReviewSidebar from "../components/ReviewSidebar";

type Filter = "all" | "correct" | "wrong";

function optionLetter(option: string): string {
  const m = /^([A-D])[.)]/.exec(option.trim());
  return m ? m[1] : "?";
}

function clock(total: number): string {
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

/** Elapsed seconds: client timer passed via ?t=, else started→finished. */
function elapsed(detail: SessionDetail, t: number): number | null {
  if (t > 0) return t;
  if (!detail.started_at || !detail.finished_at) return null;
  const start = Date.parse(detail.started_at.replace(" ", "T") + "Z");
  const end = Date.parse(detail.finished_at.replace(" ", "T") + "Z");
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, Math.round((end - start) / 1000));
}

export default function ResultPage() {
  const { sid } = useParams();
  const sessionId = Number(sid);
  const [searchParams] = useSearchParams();
  const t = Number(searchParams.get("t")) || 0;
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getSession(sessionId), api.regradeSession(sessionId)])
      .then(([d, r]) => {
        if (cancelled) return;
        setDetail(d);
        setResult(r);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : String(err)));
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const matchesFilter = (i: ResultItem) =>
    filter === "all"
      ? true
      : filter === "correct"
        ? i.is_correct === true
        : i.is_correct === false;

  // keep a question selected that is actually visible under the current filter
  useEffect(() => {
    if (!result) return;
    const ids = result.items.filter(matchesFilter).map((i) => i.question_id);
    setSelectedId((prev) => (prev !== null && ids.includes(prev) ? prev : (ids[0] ?? null)));
  }, [result, filter]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Select a question in the master-detail view and bring the pane into view. */
  const selectQuestion = (qid: number) => {
    setSelectedId(qid);
    window.setTimeout(
      () =>
        document
          .getElementById("qcontent")
          ?.scrollIntoView({ behavior: "smooth", block: "start" }),
      60,
    );
  };

  // ← / → move between questions (ignored while typing in the workspace)
  useEffect(() => {
    if (!result) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable)
        return;
      const ids = result.items.filter(matchesFilter).map((i) => i.question_id);
      const idx = selectedId === null ? -1 : ids.indexOf(selectedId);
      const target = e.key === "ArrowLeft" ? idx - 1 : idx + 1;
      if (target >= 0 && target < ids.length) {
        e.preventDefault();
        selectQuestion(ids[target]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-register each render so the closure sees fresh filter/selection

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800">
          {error}
        </div>
        <Link to="/" className="mt-4 inline-block text-blue-700 underline">
          Back to library
        </Link>
      </div>
    );
  }
  if (!detail || !result) {
    return <div className="mx-auto max-w-3xl px-4 py-10 text-slate-500">Loading…</div>;
  }

  const docId = detail.document_id;
  const pct = result.graded ? Math.round((result.correct / result.graded) * 100) : 0;
  const wrong = result.items.filter((i) => i.is_correct === false).length;
  const correct = result.items.filter((i) => i.is_correct === true).length;
  const secs = elapsed(detail, t);

  const visible = result.items.filter(matchesFilter);
  const selected = result.items.find((i) => i.question_id === selectedId) ?? null;
  const vIdx = visible.findIndex((i) => i.question_id === selectedId);
  const prevQ = vIdx > 0 ? visible[vIdx - 1] : null;
  const nextQ = vIdx >= 0 && vIdx < visible.length - 1 ? visible[vIdx + 1] : null;

  // pure statistics for the overview panel
  const wrongList = result.items.filter((i) => i.is_correct === false);
  const blank = result.items.filter((i) => i.answer !== null && !i.chosen).length;
  const statFor = (sec: "rw" | "math") => {
    const inSec = result.items.filter((i) => i.sec === sec);
    const gradedSec = inSec.filter((i) => i.answer !== null);
    return {
      total: inSec.length,
      graded: gradedSec.length,
      correct: gradedSec.filter((i) => i.is_correct === true).length,
    };
  };
  const rwStat = statFor("rw");
  const mathStat = statFor("math");

  const focusQuestion = (qid: number) => {
    setFilter("all");
    selectQuestion(qid);
  };

  const statusOf = (item: ResultItem): "correct" | "wrong" | "ungraded" =>
    item.is_correct === true ? "correct" : item.is_correct === false ? "wrong" : "ungraded";

  const tabs: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "All questions", count: result.items.length },
    { key: "correct", label: "Correct only", count: correct },
    { key: "wrong", label: "Wrong only", count: wrong },
  ];

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-8 lg:flex-row lg:items-start">
      <div className="min-w-0 flex-1">
      <section className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{detail.document.title}</h1>
            <p className="text-sm text-slate-600">
              {secs !== null && `${clock(secs)} · `}
              {result.total} questions · {result.graded} graded
            </p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold tracking-tight">
              {result.correct} <span className="text-slate-400">/ {result.graded}</span>
            </div>
            <div className="text-sm text-slate-600">
              {pct}% · {wrong} wrong
            </div>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <Link
            to={`/doc/${docId}/practice`}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
          >
            Practice again
          </Link>
          <Link to="/" className="rounded-lg border px-4 py-2 font-medium hover:bg-slate-50">
            Back to library
          </Link>
          <button
            onClick={() => setPanelOpen((p) => !p)}
            className="rounded-lg border px-4 py-2 font-medium hover:bg-slate-50"
          >
            {panelOpen ? "Hide panel" : "Show panel"}
          </button>
        </div>
      </section>

      {/* pure statistics — computed client-side, 0 token */}
      <section className="mt-4 rounded-xl border bg-white p-4" aria-label="Session statistics">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Score
            </div>
            <div className="mt-1 text-lg font-bold">{result.graded ? `${pct}%` : "–"}</div>
            <div className="text-xs text-slate-500">
              {result.graded
                ? `${correct} of ${result.graded} · ${blank} blank`
                : "no answer key"}
            </div>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Reading &amp; Writing
            </div>
            <div className="mt-1 text-lg font-bold">
              {rwStat.graded ? `${rwStat.correct} / ${rwStat.graded}` : "–"}
            </div>
            <div className="text-xs text-slate-500">{rwStat.total} questions</div>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Math</div>
            <div className="mt-1 text-lg font-bold">
              {mathStat.graded ? `${mathStat.correct} / ${mathStat.graded}` : "–"}
            </div>
            <div className="text-xs text-slate-500">{mathStat.total} questions</div>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Time</div>
            <div className="mt-1 text-lg font-bold">{secs !== null ? clock(secs) : "–"}</div>
            <div className="text-xs text-slate-500">elapsed</div>
          </div>
        </div>
        {wrongList.length > 0 && (
          <div className="mt-3 border-t pt-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Wrong answers
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {wrongList.map((i) => (
                <button
                  key={i.question_id}
                  onClick={() => focusQuestion(i.question_id)}
                  title={`Jump to question ${i.no}`}
                  className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                >
                  Q{i.no}: {i.chosen ?? "blank"} ✗ {i.answer}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {result.graded === 0 && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          This attempt has no answer key yet —{" "}
          <Link
            to={`/doc/${docId}/answers?session=${sessionId}`}
            className="font-semibold underline"
          >
            enter the answers now
          </Link>{" "}
          to grade it.
        </div>
      )}

      <div className="mt-6 flex gap-1 rounded-xl border bg-white p-1" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={filter === tab.key}
            onClick={() => setFilter(tab.key)}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
              filter === tab.key
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {tab.label} <span className="opacity-70">({tab.count})</span>
          </button>
        ))}
      </div>

      {/* master–detail: question index | current question (the workspace stays beside it) */}
      <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-start">
        <nav
          id="qindex"
          aria-label="Question index"
          className="w-full shrink-0 rounded-xl border bg-white p-2 lg:sticky lg:top-4 lg:w-40"
        >
          <div className="flex items-baseline justify-between px-1 pb-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Questions
            </span>
            <span className="text-xs text-slate-400">{visible.length}</span>
          </div>
          {visible.length === 0 ? (
            <p className="px-1 pb-1 text-xs text-slate-400">Nothing to show.</p>
          ) : (
            <div className="grid grid-cols-8 gap-1.5 sm:grid-cols-10 lg:grid-cols-4">
              {visible.map((item) => {
                const status = statusOf(item);
                const label =
                  status === "correct"
                    ? "correct"
                    : status === "wrong"
                      ? "wrong"
                      : "no answer key";
                const sel = selectedId === item.question_id;
                return (
                  <button
                    key={item.question_id}
                    id={`qn-${item.question_id}`}
                    data-no={item.no}
                    data-status={status}
                    aria-label={`Question ${item.no} — ${label}`}
                    aria-current={sel ? "true" : undefined}
                    title={`Question ${item.no} · ${label}`}
                    onClick={() => selectQuestion(item.question_id)}
                    className={`rounded-md border px-1 py-1.5 text-xs font-semibold transition ${
                      status === "correct"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : status === "wrong"
                          ? "border-red-200 bg-red-50 text-red-700"
                          : "border-slate-200 bg-slate-50 text-slate-500"
                    } ${sel ? "ring-2 ring-blue-500" : "hover:border-slate-400"}`}
                  >
                    {item.no}
                  </button>
                );
              })}
            </div>
          )}
        </nav>

        <div id="qcontent" className="min-w-0 flex-1">
          {selected === null ? (
            <div className="rounded-xl border bg-white px-4 py-8 text-center text-sm text-slate-500">
              {filter === "wrong" ? "Nothing wrong here — nice work." : "No questions to show."}
            </div>
          ) : (
            <article
              key={selected.question_id}
              id={`q-${selected.question_id}`}
              className="rounded-xl border bg-white p-5 shadow-sm"
            >
              <div className="mb-3 flex flex-wrap items-center gap-2 text-sm font-semibold">
                <span
                  className={`grid h-6 w-6 place-items-center rounded-full text-white ${
                    selected.is_correct === true
                      ? "bg-emerald-600"
                      : selected.is_correct === false
                        ? "bg-red-500"
                        : "bg-slate-400"
                  }`}
                  aria-hidden
                >
                  {selected.is_correct === true
                    ? "✓"
                    : selected.is_correct === false
                      ? "✗"
                      : "–"}
                </span>
                <span>Question {selected.no}</span>
                <span className="font-normal text-slate-500">
                  {selected.sec === "math" ? "Math" : "Reading & Writing"}
                  {selected.source ? ` · ${selected.source}` : ""}
                </span>
                <div className="ml-auto flex items-center gap-2">
                  <button
                    onClick={() => prevQ && selectQuestion(prevQ.question_id)}
                    disabled={!prevQ}
                    aria-label="Previous question"
                    title="Previous question (←)"
                    className="rounded-lg border px-3 py-1 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    ←
                  </button>
                  <span className="text-xs font-normal text-slate-400">
                    {vIdx + 1} / {visible.length}
                  </span>
                  <button
                    onClick={() => nextQ && selectQuestion(nextQ.question_id)}
                    disabled={!nextQ}
                    aria-label="Next question"
                    title="Next question (→)"
                    className="rounded-lg border px-3 py-1 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    →
                  </button>
                </div>
              </div>

              {selected.material && (
                <div className="mb-3 rounded-lg border bg-slate-50 p-3 text-sm">
                  <RichText text={selected.material} docId={docId} />
                </div>
              )}

              <div className="text-[15px]">
                <RichText text={selected.stem} docId={docId} />
              </div>

              <ul className="mt-3 space-y-2">
                {selected.options.map((option) => {
                  const letter = optionLetter(option);
                  const isAnswer = selected.answer === letter;
                  const isChosen = selected.chosen === letter;
                  const tone = isAnswer
                    ? "border-emerald-500 bg-emerald-50"
                    : isChosen
                      ? "border-red-400 bg-red-50"
                      : "border-slate-200";
                  return (
                    <li
                      key={letter}
                      className={`flex items-start gap-3 rounded-lg border px-3 py-2 text-sm ${tone}`}
                    >
                      <span className="font-semibold">{letter}</span>
                      <span className="flex-1">
                        <RichText text={option.replace(/^[A-D][.)]\s*/, "")} docId={docId} />
                      </span>
                      {isChosen && (
                        <span
                          className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
                            isAnswer ? "bg-emerald-600 text-white" : "bg-red-500 text-white"
                          }`}
                        >
                          your answer
                        </span>
                      )}
                      {isAnswer && !isChosen && (
                        <span className="shrink-0 rounded bg-emerald-600 px-1.5 py-0.5 text-xs font-medium text-white">
                          correct
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>

              {selected.answer === null && (
                <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  No answer key for this question — fill it in on the answer page.
                </p>
              )}
              {selected.is_correct === false && selected.explain && (
                <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
                  <div className="mb-1 font-semibold text-blue-900">Explanation</div>
                  <RichText text={selected.explain} docId={docId} />
                </div>
              )}
            </article>
          )}
        </div>
      </div>
      </div>

      {panelOpen && (
        <div className="w-full shrink-0 self-start lg:sticky lg:top-4 lg:w-auto">
          <ReviewSidebar
            docId={docId}
            item={selected}
            onClose={() => setPanelOpen(false)}
            onExplainSaved={(qid, content) =>
              setResult((r) =>
                r && {
                  ...r,
                  items: r.items.map((i) =>
                    i.question_id === qid ? { ...i, explain: content } : i,
                  ),
                },
              )
            }
          />
        </div>
      )}
    </div>
  );
}
