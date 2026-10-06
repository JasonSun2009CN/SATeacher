import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  ApiError,
  type BuiltinBank,
  type DocumentSummary,
  type ImportJob,
} from "../api/client";
import BuiltinBankCard from "../components/BuiltinBankCard";
import ImportPipeline from "../components/ImportPipeline";
import LibraryList from "../components/LibraryList";
import SatMdTemplate from "../components/SatMdTemplate";

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

export default function ImportPage() {
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [banks, setBanks] = useState<BuiltinBank[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [imported, setImported] = useState<DocumentSummary | null>(null);
  const [ocr, setOcr] = useState<string[] | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDocs(await api.listDocuments());
    } catch (err) {
      setError(errText(err));
    }
  }, []);

  const refreshBanks = useCallback(async () => {
    try {
      setBanks(await api.listBanks());
    } catch (err) {
      // the bank list is optional furniture — don't block the import page
      console.warn("builtin banks unavailable:", err);
    }
  }, []);

  /** After adding built-in modules: reload flags + the library in one pass. */
  const refreshAll = useCallback(async () => {
    await Promise.all([refresh(), refreshBanks()]);
  }, [refresh, refreshBanks]);

  useEffect(() => {
    void refresh();
    void refreshBanks();
    api
      .health()
      .then((h) => setOcr(h.ocr))
      .catch(() => setOcr(null)); // health is furniture; never block the page
  }, [refresh, refreshBanks]);

  async function startImport(file: File) {
    setBusy(true);
    setError(null);
    setJob(null);
    setImported(null);
    try {
      let created = await api.createImport(file);
      // Clean conversions skip the review screen (0 token, no ambiguity).
      if (created.status === "review" && !created.needs_review) {
        created = await api.commitImport(created.id);
      }
      setJob(created);
      if (created.status === "done" && created.document_id) {
        setImported(await api.getDocument(created.document_id));
        await refresh();
      }
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) void startImport(file);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void startImport(file);
  }

  async function onCommit() {
    if (!job) return;
    setBusy(true);
    try {
      const done = await api.commitImport(job.id);
      setJob(done);
      if (done.document_id) {
        setImported(await api.getDocument(done.document_id));
        await refresh();
      }
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function onCancelJob() {
    if (!job) return;
    try {
      await api.cancelImport(job.id);
    } catch (err) {
      console.warn("cancel failed:", err);
    }
    setJob(null);
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
            Import a question bank (PDF, Word <code className="rounded bg-slate-200 px-1">.docx</code>, or{" "}
            <code className="rounded bg-slate-200 px-1">.sat.md</code>),
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
          PDFs and Word <code className="rounded bg-slate-200 px-1">.docx</code> files are converted
          locally to SAT-MD — no tokens, no cloud. Questions must be numbered
          ({"1."}, {"2."}, …) with four options each.
        </p>
        {ocr !== null &&
          (ocr.length > 0 ? (
            <p className="mt-2 text-sm text-slate-500">
              Scanned PDFs are read locally with OCR ({ocr.join(", ")}).
            </p>
          ) : (
            <p className="mt-2 text-sm text-amber-700">
              Scanned (image-only) PDFs need OCR: install{" "}
              <code className="rounded bg-amber-100 px-1">tesseract</code> on any OS, or{" "}
              <code className="rounded bg-amber-100 px-1">pyobjc-framework-Vision</code> on macOS.
            </p>
          ))}

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={
            "mt-4 flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors " +
            (dragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50")
          }
        >
          <p className="text-sm text-slate-600">
            Drag a file here, or{" "}
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="font-medium text-blue-700 underline hover:text-blue-800 disabled:opacity-50"
            >
              choose a file
            </button>
            .
          </p>
          <p className="mt-1 text-xs text-slate-400">PDF · DOCX · .md · .markdown · .sat.md</p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.md,.markdown"
            className="hidden"
            disabled={busy}
            onChange={onFile}
          />
          {busy && <p className="mt-3 text-sm text-slate-500">Converting…</p>}
        </div>

        <SatMdTemplate />
      </section>

      {job && (
        <ImportPipeline
          job={job}
          busy={busy}
          onCommit={onCommit}
          onCancel={onCancelJob}
        />
      )}

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
        </section>
      )}

      {banks && banks.length > 0 && (
        <div>
          {banks.map((bank) => (
            <BuiltinBankCard key={bank.id} bank={bank} onChanged={() => void refreshAll()} />
          ))}
        </div>
      )}

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Library</h2>
        {docs === null && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
        {docs?.length === 0 && (
          <p className="mt-3 text-sm text-slate-500">Nothing imported yet.</p>
        )}
        <div className="mt-3">
          {docs && docs.length > 0 && (
            <LibraryList docs={docs} importedId={imported?.id ?? null} onDelete={onDelete} />
          )}
        </div>
      </section>
    </div>
  );
}