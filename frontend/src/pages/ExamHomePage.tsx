import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type DocumentSummary } from "../api/client";

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

/**
 * Home screen: pick an exam and start it — nothing else.
 *
 * Import / Library / Settings are management tools, not part of taking a
 * test; they live behind the small "Manage" link in the corner (batch 17).
 */
export default function ExamHomePage() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDocuments()
      .then(setDocs)
      .catch((err) => setError(errText(err)));
  }, []);

  return (
    <div className="relative mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-4 py-12">
      <h1 className="text-center text-3xl font-bold tracking-tight">Select an exam</h1>
      <p className="mt-2 text-center text-sm text-slate-600">
        Answers are graded when you submit. The timer starts when you begin.
      </p>

      {error && (
        <div className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800">
          {error}
        </div>
      )}

      {docs === null && !error && (
        <p className="mt-8 text-center text-sm text-slate-500">Loading…</p>
      )}

      {docs?.length === 0 && (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center">
          <p className="text-sm text-slate-600">No exams yet.</p>
          <Link
            to="/manage"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Import an exam
          </Link>
        </div>
      )}

      {docs && docs.length > 0 && (
        <ul className="mt-8 space-y-3">
          {docs.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4"
            >
              <div className="min-w-0">
                <div className="truncate font-semibold text-slate-900">{doc.title}</div>
                <div className="mt-0.5 text-xs text-slate-500">
                  {doc.question_count} questions
                  {doc.needs_answers && doc.answered_count < doc.question_count
                    ? ` · answers ${doc.answered_count}/${doc.question_count}`
                    : ""}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {doc.needs_answers && doc.answered_count < doc.question_count && (
                  <Link
                    to={`/doc/${doc.id}/answers`}
                    className="text-sm text-blue-700 underline hover:text-blue-800"
                  >
                    Enter answers
                  </Link>
                )}
                <Link
                  to={`/doc/${doc.id}/practice`}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Start
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Unobtrusive way into the management screens (import/library/settings). */}
      <Link
        to="/manage"
        className="absolute bottom-4 right-4 text-xs text-slate-400 underline hover:text-slate-600"
      >
        Manage
      </Link>
    </div>
  );
}
