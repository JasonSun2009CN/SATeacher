import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError, type DocumentSummary, type Question } from "../api/client";
import RichText from "../components/RichText";

const LETTERS = ["A", "B", "C", "D"] as const;

/**
 * Accepts "1-A 2-C", "1. A", "12B" or a bare letter string "ACBDA".
 * Returns answers keyed by the question's displayed number.
 */
export function parseBulk(text: string): Record<number, string> {
  const out: Record<number, string> = {};
  const numbered = [...text.matchAll(/(\d{1,3})\s*[-.):]?\s*([A-Da-d])/g)];
  if (numbered.length > 0) {
    for (const m of numbered) {
      const no = Number(m[1]);
      if (no >= 1 && no <= 200) out[no] = m[2].toUpperCase();
    }
    return out;
  }
  const letters = text.replace(/[^A-Da-d]/g, "").toUpperCase();
  for (let i = 0; i < letters.length; i++) out[i + 1] = letters[i];
  return out;
}

export default function AnswerKeyPage() {
  const { id } = useParams();
  const docId = Number(id);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  /** Set when the user just submitted an attempt that needs grading. */
  const pendingSession = searchParams.get("session");
  const [doc, setDoc] = useState<DocumentSummary | null>(null);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [bulk, setBulk] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getDocument(docId), api.getQuestions(docId)])
      .then(([d, qs]) => {
        if (cancelled) return;
        setDoc(d);
        setQuestions(qs);
        setAnswers(Object.fromEntries(qs.filter((q) => q.answer).map((q) => [q.ext_id, q.answer!])));
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : String(err)));
    return () => {
      cancelled = true;
    };
  }, [docId]);

  const filled = Object.keys(answers).length;
  const total = questions?.length ?? 0;

  function setAnswer(extId: string, letter: string) {
    setAnswers((prev) => {
      const next = { ...prev };
      if (next[extId] === letter) delete next[extId];
      else next[extId] = letter;
      return next;
    });
    setMessage(null);
  }

  function applyBulk() {
    if (!questions) return;
    const parsed = parseBulk(bulk);
    const next: Record<string, string> = { ...answers };
    let applied = 0;
    questions.forEach((q) => {
      const no = q.no ?? questions.indexOf(q) + 1;
      const letter = parsed[no];
      if (letter) {
        next[q.ext_id] = letter;
        applied += 1;
      }
    });
    if (applied === 0) {
      setError("Nothing recognized — expected something like 1-A 2-C 3-D, or ACBD…");
      return;
    }
    setError(null);
    setAnswers(next);
    setMessage(`Parsed ${applied} answer(s) from the pasted text.`);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.putAnswers(docId, answers);
      setDoc(updated);
      if (pendingSession && Object.keys(answers).length > 0) {
        // the stored attempt waits for this key — grade it and show results
        navigate(`/session/${pendingSession}/result`);
        return;
      }
      setMessage(`Saved ${updated.answered_count}/${updated.question_count} answers.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (error && !questions) {
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

  if (!doc || !questions) {
    return <div className="mx-auto max-w-3xl px-4 py-10 text-slate-500">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-blue-700 underline">
            ← Back to exams
          </Link>
          <h1 className="mt-1 text-2xl font-bold">Answer key · {doc.title}</h1>
          <p className="text-sm text-slate-600">
            {total} questions · {filled}/{total} filled
            {doc.answers_status !== "none" && ` · source had: ${doc.answers_status} answers`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={save}
            disabled={saving || filled === 0}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : pendingSession ? "Save & view results" : "Save answers"}
          </button>
          <Link
            to={`/doc/${doc.id}/practice`}
            className="rounded-lg border px-4 py-2 font-medium hover:bg-slate-50"
          >
            Practice
          </Link>
        </div>
      </div>

      {pendingSession && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          You just submitted an attempt — enter the answer key to grade it, then
          you'll see the results.
        </div>
      )}
      {message && (
        <div className="mt-4 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-900">
          {message}
        </div>
      )}
      {error && (
        <div className="mt-4 rounded-lg border border-red-300 bg-red-50 px-4 py-2.5 text-sm text-red-800">
          {error}
        </div>
      )}

      <section className="mt-6 rounded-xl border bg-white p-4">
        <h2 className="font-semibold">Bulk entry</h2>
        <p className="text-sm text-slate-600">
          Paste <code className="rounded bg-slate-100 px-1">1-A 2-C 3-D</code>,{" "}
          <code className="rounded bg-slate-100 px-1">1. A</code>, or just{" "}
          <code className="rounded bg-slate-100 px-1">ACBDA</code>.
        </p>
        <textarea
          value={bulk}
          onChange={(e) => setBulk(e.target.value)}
          rows={3}
          placeholder="1-A 2-C 3-D 4-A 5-B"
          className="mt-2 w-full rounded-lg border px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none"
        />
        <button
          onClick={applyBulk}
          className="mt-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
        >
          Apply to grid
        </button>
      </section>

      <section className="mt-6 grid gap-2 sm:grid-cols-2">
        {questions.map((q, i) => {
          const no = q.no ?? i + 1;
          const chosen = answers[q.ext_id];
          return (
            <div
              key={q.ext_id}
              className="flex items-center gap-3 rounded-lg border bg-white px-3 py-2"
            >
              <span
                className={`w-10 shrink-0 text-sm font-semibold ${chosen ? "text-slate-800" : "text-slate-400"}`}
              >
                {no}
              </span>
              <span className="min-w-0 flex-1 truncate text-xs text-slate-500" title={q.stem}>
                {q.stem}
              </span>
              <div className="flex shrink-0 gap-1">
                {LETTERS.map((letter) => (
                  <button
                    key={letter}
                    onClick={() => setAnswer(q.ext_id, letter)}
                    aria-pressed={chosen === letter}
                    className={`h-8 w-8 rounded-md border text-sm font-semibold transition ${
                      chosen === letter
                        ? "border-blue-600 bg-blue-600 text-white"
                        : "border-slate-300 hover:border-slate-400"
                    }`}
                  >
                    {letter}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </section>

      <section className="mt-6 rounded-xl border bg-white p-4">
        <h2 className="font-semibold">Preview</h2>
        <p className="text-sm text-slate-600">First question as the practice UI will render it.</p>
        <div className="mt-2 rounded-lg border bg-slate-50 p-3 text-sm">
          <RichText text={questions[0]?.stem ?? ""} docId={docId} />
        </div>
      </section>

      <div className="mt-6 flex gap-3">
        <button
          onClick={save}
          disabled={saving || filled === 0}
          className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : pendingSession ? "Save & view results" : "Save answers"}
        </button>
        {filled === total && total > 0 && (
          <Link
            to={`/doc/${doc.id}/practice`}
            className="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700"
          >
            All set — start practice
          </Link>
        )}
      </div>
    </div>
  );
}
