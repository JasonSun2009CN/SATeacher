import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type QuizQuestion, type StartResponse } from "../api/client";
import RichText from "../components/RichText";

const LETTERS = ["A", "B", "C", "D"];

function optionParts(option: string): { letter: string; text: string } {
  const m = /^([A-D])[.)]\s*([\s\S]*)$/.exec(option.trim());
  return m ? { letter: m[1], text: m[2] } : { letter: "?", text: option };
}

function clock(total: number): string {
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

export default function PracticePage() {
  const { id } = useParams();
  const docId = Number(id);
  const navigate = useNavigate();
  const [session, setSession] = useState<StartResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entered, setEntered] = useState(false);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [marked, setMarked] = useState<Set<number>>(new Set());
  const [seconds, setSeconds] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // React 18 StrictMode double-invokes effects in dev (setup -> cleanup ->
  // setup). The backend session is a real side effect that cleanup cannot
  // undo, so start it only once per document. The response is accepted only
  // while the component is mounted (aliveRef) and no newer document is in
  // flight (startedFor ref) — a StrictMode synthetic cleanup must NOT cancel
  // the single in-flight request.
  const startedFor = useRef<number | null>(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    setSession(null);
    setEntered(false);
    setIdx(0);
    setAnswers({});
    setMarked(new Set());
    setSeconds(0);
    setError(null);
    if (startedFor.current === docId) return undefined; // strict-mode re-run

    startedFor.current = docId;
    api
      .startSession(docId)
      .then((s) => {
        if (aliveRef.current && startedFor.current === docId) setSession(s);
      })
      .catch((err) => {
        if (aliveRef.current && startedFor.current === docId) setError(errText(err));
      });
    return () => {
      aliveRef.current = false;
    };
  }, [docId]);

  // leave fullscreen when the exam ends or the page unmounts
  useEffect(
    () => () => {
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    },
    [],
  );

  useEffect(() => {
    if (!session || !entered) return;
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, [session, entered]);

  const questions = session?.questions ?? [];
  const current: QuizQuestion | undefined = questions[idx];
  const answered = Object.keys(answers).length;
  const last = idx === questions.length - 1;

  function choose(qid: number, letter: string) {
    setAnswers((prev) => ({ ...prev, [qid]: letter }));
  }

  function toggleMark(qid: number) {
    setMarked((prev) => {
      const next = new Set(prev);
      if (next.has(qid)) next.delete(qid);
      else next.add(qid);
      return next;
    });
  }

  async function doSubmit() {
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submit(
        session.session_id,
        Object.fromEntries(Object.entries(answers).map(([k, v]) => [k, v])),
      );
      setConfirming(false);
      if (res.graded > 0) {
        // the key exists — straight to the graded results
        navigate(`/session/${res.session_id}/result?t=${seconds}`);
      } else {
        // no key in the source: record the attempt, then fill the key in
        navigate(`/doc/${docId}/answers?session=${res.session_id}`);
      }
    } catch (err) {
      setError(errText(err));
      setConfirming(false);
      setSubmitting(false);
    }
  }

  /** Leave mid-exam: the session stays in the document's history unfinished. */
  function leaveExam() {
    setLeaving(false);
    navigate("/");
  }

  async function enter() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      }
    } catch {
      // fullscreen may be unavailable (embedded view) — start anyway
    }
    setEntered(true);
  }

  // Bluebook-style shortcuts: A-D selects, arrows move.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!session || !entered || confirming || leaving) return;
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const q = questions[idx];
      if (!q) return;
      const key = e.key.toUpperCase();
      if (LETTERS.includes(key)) {
        choose(q.id, key);
      } else if (e.key === "ArrowRight") {
        setIdx((i) => Math.min(i + 1, questions.length - 1));
      } else if (e.key === "ArrowLeft") {
        setIdx((i) => Math.max(i - 1, 0));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (error && !session) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800">
          {error}
        </div>
        <Link to="/" className="mt-4 inline-block text-blue-700 underline">
          Back to exams
        </Link>
      </div>
    );
  }

  if (!session) {
    return <div className="mx-auto max-w-3xl px-4 py-10 text-slate-500">Loading…</div>;
  }

  if (!entered) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100 px-4">
        <div className="w-full max-w-md rounded-2xl border bg-white p-8 text-center shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Ready to begin
          </div>
          <h1 className="mt-2 text-2xl font-bold">{session.document.title}</h1>
          <p className="mt-2 text-sm text-slate-600">
            {session.questions.length} questions · the timer starts when you enter
          </p>
          <button
            onClick={enter}
            className="mt-6 w-full rounded-lg bg-blue-600 px-4 py-3 font-medium text-white hover:bg-blue-700"
          >
            Begin — enter fullscreen
          </button>
          <Link
            to={`/doc/${docId}/answers`}
            className="mt-4 inline-block text-sm text-blue-700 underline"
          >
            Enter answers first (optional)
          </Link>
          <Link to="/" className="mt-2 block text-sm text-slate-500 underline">
            Back to exams
          </Link>
        </div>
      </div>
    );
  }

  if (!current) {
    return <div className="mx-auto max-w-3xl px-4 py-10 text-slate-500">Loading…</div>;
  }

  const unanswered = questions.length - answered;
  const material = current.material;

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      <header className="sticky top-0 z-20 border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="min-w-0">
            <div className="truncate font-semibold">{session.document.title}</div>
            <div className="text-xs text-slate-500">
              {current.sec === "math" ? "Math" : "Section 1 · Reading & Writing"}
            </div>
          </div>
          <div className="text-sm text-slate-600">
            Question <span className="font-semibold text-slate-900">{idx + 1}</span> of{" "}
            {questions.length}
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-slate-100 px-2.5 py-1 font-mono text-sm tabular-nums">
              {clock(seconds)}
            </span>
            <button
              onClick={() => setLeaving(true)}
              className="rounded-lg border px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              Exit
            </button>
            <button
              onClick={() => setConfirming(true)}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Submit
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="mx-auto mt-3 max-w-6xl rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <div className={material ? "grid gap-4 lg:grid-cols-2" : "mx-auto max-w-3xl"}>
          {material && (
            <aside className="max-h-[70vh] overflow-y-auto rounded-xl border bg-white p-5">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Passage
              </div>
              <div className="text-[15px]">
                <RichText text={material} docId={docId} />
              </div>
            </aside>
          )}

          <section className={`rounded-xl border bg-white p-5 ${material ? "" : "p-6"}`}>
            <div className="mb-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
              <span>
                Question {current.no ?? idx + 1}
                {current.source ? ` · ${current.source}` : ""}
              </span>
              <button
                onClick={() => toggleMark(current.id)}
                className={`rounded px-2 py-1 normal-case tracking-normal ${
                  marked.has(current.id)
                    ? "bg-amber-100 text-amber-800"
                    : "text-slate-500 hover:bg-slate-100"
                }`}
              >
                {marked.has(current.id) ? "⚑ Marked" : "Mark for review"}
              </button>
            </div>

            <div className="text-[15px]">
              <RichText text={current.stem} docId={docId} />
            </div>

            <div className="mt-5 space-y-2.5">
              {current.options.map((option) => {
                const { letter, text } = optionParts(option);
                const selected = answers[current.id] === letter;
                return (
                  <button
                    key={letter}
                    onClick={() => choose(current.id, letter)}
                    aria-pressed={selected}
                    className={`flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition ${
                      selected
                        ? "border-blue-600 bg-blue-50 ring-1 ring-blue-600"
                        : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50"
                    }`}
                  >
                    <span
                      className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-sm font-semibold ${
                        selected
                          ? "border-blue-600 bg-blue-600 text-white"
                          : "border-slate-400 text-slate-700"
                      }`}
                    >
                      {letter}
                    </span>
                    <span className="min-w-0 flex-1 pt-0.5 text-[15px]">
                      <RichText text={text} docId={docId} />
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </main>

      <footer className="sticky bottom-0 z-20 border-t bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <button
            onClick={() => setIdx((i) => Math.max(i - 1, 0))}
            disabled={idx === 0}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            Previous
          </button>

          <nav className="flex flex-1 flex-wrap justify-center gap-1.5" aria-label="Question palette">
            {questions.map((q, i) => {
              const isAnswered = answers[q.id] !== undefined;
              const isMarked = marked.has(q.id);
              const isCurrent = i === idx;
              const tone = isMarked
                ? "border-amber-500 bg-amber-400 text-slate-900"
                : isAnswered
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-300 bg-white text-slate-700";
              return (
                <button
                  key={q.id}
                  onClick={() => setIdx(i)}
                  title={`Question ${q.no ?? i + 1}${isMarked ? " (marked)" : ""}`}
                  className={`grid h-8 w-8 place-items-center rounded-md border text-xs font-semibold transition ${tone} ${
                    isCurrent ? "ring-2 ring-slate-900 ring-offset-1" : ""
                  }`}
                >
                  {i + 1}
                </button>
              );
            })}
          </nav>

          <button
            onClick={() => setIdx((i) => Math.min(i + 1, questions.length - 1))}
            disabled={last}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </footer>

      {confirming && (
        <div className="fixed inset-0 z-30 grid place-items-center bg-slate-900/40 px-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold">Submit your answers?</h2>
            <p className="mt-2 text-sm text-slate-600">
              {answered} of {questions.length} answered
              {unanswered > 0 && `, ${unanswered} still blank`}. You can review every question
              afterwards.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setConfirming(false)}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50"
              >
                Keep working
              </button>
              <button
                onClick={doSubmit}
                disabled={submitting}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Grading…" : "Submit"}
              </button>
            </div>
          </div>
        </div>
      )}
      {leaving && (
        <div className="fixed inset-0 z-30 grid place-items-center bg-slate-900/40 px-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold">Leave the exam?</h2>
            <p className="mt-2 text-sm text-slate-600">
              This attempt will be left unfinished — your answers so far are not submitted and
              will not be graded. You can start a new attempt any time.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setLeaving(false)}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50"
              >
                Keep working
              </button>
              <button
                onClick={leaveExam}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                Leave exam
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
