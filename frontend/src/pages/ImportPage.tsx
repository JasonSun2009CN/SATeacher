import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type DocumentSummary } from "../api/client";

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

export default function ImportPage() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<DocumentSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setDocs(await api.listDocuments());
    } catch (err) {
      setError(errText(err));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    setImported(null);
    try {
      setImported(await api.importDocument(file));
      await refresh();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(doc: DocumentSummary) {
    if (!window.confirm(`Delete "${doc.title}" and its ${doc.question_count} questions?`)) return;
    try {
      await api.deleteDocument(doc.id);
      if (imported?.id === doc.id) setImported(null);
      await refresh();
    } catch (err) {
      setError(errText(err));
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">SATeacher</h1>
          <p className="mt-1 text-slate-600">
            Import a question bank (PDF or <code className="rounded bg-slate-200 px-1">.sat.md</code>),
            fill in the answers, then practice in a Bluebook-style UI.
          </p>
        </div>
        <Link
          to="/settings"
          className="shrink-0 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          title="LLM API settings"
        >
          ⚙ Settings
        </Link>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800">
          {error}
        </div>
      )}

      <section className="rounded-xl border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Import a document</h2>
        <p className="mt-1 text-sm text-slate-600">
          PDFs are converted locally to SAT-MD — no tokens, no cloud. Questions must be numbered
          ({"1."}, {"2."}, …) with four options each.
        </p>
        <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {busy ? "Importing…" : "Choose file"}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.md,.markdown"
            className="hidden"
            disabled={busy}
            onChange={onFile}
          />
        </label>
        {busy && <span className="ml-3 text-sm text-slate-500">Converting…</span>}
      </section>

      {imported && (
        <section className="mt-6 rounded-xl border border-emerald-300 bg-emerald-50 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-emerald-900">{imported.title}</h2>
              <p className="text-sm text-emerald-800">
                {imported.question_count} questions imported from {imported.source_filename} ·
                answers: {imported.answers_status}
                {imported.needs_answers && ` · ${imported.answered_count}/${imported.question_count} filled`}
              </p>
            </div>
            <div className="flex gap-2">
              {imported.needs_answers && (
                <Link
                  to={`/doc/${imported.id}/answers`}
                  className="rounded-lg bg-amber-500 px-4 py-2 font-medium text-white hover:bg-amber-600"
                >
                  Enter answers
                </Link>
              )}
              <Link
                to={`/doc/${imported.id}/practice`}
                className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
              >
                Start practice
              </Link>
            </div>
          </div>
          {imported.warnings && imported.warnings.length > 0 && (
            <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-amber-900">
              {imported.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Library</h2>
        {docs === null && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
        {docs?.length === 0 && (
          <p className="mt-3 text-sm text-slate-500">Nothing imported yet.</p>
        )}
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {docs?.map((doc) => (
            <article key={doc.id} className="rounded-xl border bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{doc.title}</h3>
                  <p className="text-sm text-slate-500">
                    {doc.source_filename} · {doc.question_count} questions ·{" "}
                    {doc.answered_count}/{doc.question_count} answers
                    {doc.needs_answers && (
                      <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
                        needs answers
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                <Link
                  to={`/doc/${doc.id}/practice`}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 font-medium text-white hover:bg-blue-700"
                >
                  Practice
                </Link>
                <Link
                  to={`/doc/${doc.id}/answers`}
                  className="rounded-lg border px-3 py-1.5 font-medium hover:bg-slate-50"
                >
                  Answers
                </Link>
                <button
                  onClick={() => onDelete(doc)}
                  className="rounded-lg border border-red-200 px-3 py-1.5 font-medium text-red-700 hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
