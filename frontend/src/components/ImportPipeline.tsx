import type { ImportJob, ImportPageReport } from "../api/client";

const STAGES = [
  { key: "detect", label: "Detect" },
  { key: "convert", label: "Convert" },
  { key: "validate", label: "Review" },
  { key: "commit", label: "Commit" },
];

const PAGE_LABELS: Record<string, string> = {
  text: "text layer",
  ocr_ok: "OCR",
  low_confidence: "OCR · low confidence",
  ocr_unavailable: "OCR unavailable",
  ocr_failed: "OCR failed",
  empty: "no text",
};

const AI_FALLBACK_STATUSES = ["ocr_unavailable", "ocr_failed", "low_confidence", "empty"];

function pageTone(status: string): string {
  switch (status) {
    case "text":
    case "ocr_ok":
      return "bg-emerald-100 text-emerald-800";
    case "low_confidence":
      return "bg-amber-100 text-amber-800";
    default:
      return "bg-red-100 text-red-800";
  }
}

function pageLabel(page: ImportPageReport): string {
  const label = PAGE_LABELS[page.status] ?? page.status;
  if (page.source && page.status !== "text") return `${label} (${page.source})`;
  return label;
}

interface Props {
  job: ImportJob;
  busy: boolean;
  onCommit: () => void;
  onCancel: () => void;
  onAiFallback: () => void;
}

export default function ImportPipeline({
  job,
  busy,
  onCommit,
  onCancel,
  onAiFallback,
}: Props) {
  const activeIndex = Math.max(
    0,
    STAGES.findIndex((s) => s.key === job.stage),
  );
  const failed = job.status === "failed";
  const cancelled = job.status === "cancelled";

  return (
    <section className="mt-6 rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            {failed ? "Import failed" : cancelled ? "Import cancelled" : "Import pipeline"}
          </h2>
          <p className="text-sm text-slate-500">
            {job.filename}
            {job.kind && ` · ${job.kind}`}
            {job.import_source && ` · source: ${job.import_source}`}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {job.status}
        </span>
      </div>

      <ol className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        {STAGES.map((stage, i) => {
          const done = job.status === "done" || i < activeIndex;
          const isActive = i === activeIndex && job.status !== "done";
          return (
            <li key={stage.key} className="flex items-center gap-2">
              <span
                className={
                  "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold " +
                  (done
                    ? "bg-emerald-600 text-white"
                    : isActive && failed
                      ? "bg-red-600 text-white"
                      : isActive
                        ? "bg-blue-600 text-white"
                        : "bg-slate-200 text-slate-500")
                }
              >
                {done ? "✓" : i + 1}
              </span>
              <span className={done || isActive ? "text-slate-900" : "text-slate-400"}>
                {stage.label}
              </span>
              {i < STAGES.length - 1 && <span className="text-slate-300">→</span>}
            </li>
          );
        })}
      </ol>

      {failed && job.error && (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {job.error}
        </p>
      )}

      {job.pages.length > 0 && (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-slate-700">
            Pages ({job.pages_done}/{job.pages_total})
          </h3>
          <ul className="mt-2 divide-y divide-slate-100 rounded-lg border">
            {job.pages.map((page) => (
              <li key={page.no} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span className="text-slate-600">Page {page.no}</span>
                <span className="flex items-center gap-2">
                  {page.confidence !== null && (
                    <span className="text-xs text-slate-400">
                      {(page.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${pageTone(page.status)}`}>
                    {pageLabel(page)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {job.status === "review" && (
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Stat label="Questions" value={String(job.question_count)} />
          <Stat label="Answers" value={job.kind === "satmd" ? "from file" : "external key"} />
          <Stat label="AI used" value={job.used_ai ? "yes" : "no (0 token)"} />
        </div>
      )}

      {job.warnings.length > 0 && (
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-amber-900">
          {job.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}

      {job.status === "review" && job.pages.some((p) => AI_FALLBACK_STATUSES.includes(p.status)) && (
        <div className="mt-4">
          <button
            onClick={onAiFallback}
            disabled={busy}
            className="rounded-lg bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50 flex items-center gap-2"
          >
            {busy ? "Running AI fallback…" : "Run AI fallback on unreadable pages"}
          </button>
          <p className="mt-1 text-xs text-slate-500">
            Uses the configured LLM to extract questions from pages with OCR issues
            ({job.pages.filter((p) => AI_FALLBACK_STATUSES.includes(p.status)).length} page{job.pages.filter((p) => AI_FALLBACK_STATUSES.includes(p.status)).length > 1 ? "s" : ""}).
          </p>
        </div>
      )}

      {job.status === "review" && (
        <div className="mt-5 flex flex-wrap gap-2">
          <button
            onClick={onCommit}
            disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {job.needs_review ? "Looks good — import" : "Import"}
          </button>
          <button
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border px-4 py-2 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          {job.needs_review && (
            <span className="self-center text-sm text-amber-700">
              Review the pages above before importing.
            </span>
          )}
        </div>
      )}

      {job.status === "done" && (
        <p className="mt-5 text-sm font-medium text-emerald-700">
          Imported {job.question_count} questions.
        </p>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-sm font-medium text-slate-800">{value}</div>
    </div>
  );
}