import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type NormalizeJob } from "../../api/client";

interface Props {
  docId: number;
  /** Refetch the session's questions after a finished run (no page reload). */
  onReload?: () => void;
}

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

const POLL_MS = 400;
const POLL_LIMIT = 3000; // ~20 min; a run is one LLM call per question

/**
 * Whole-document normalization, run in the background: one click, no
 * per-question accept/reject. Questions that fail validation keep their
 * original text and are listed when the run finishes.
 */
export default function NormalizeAllPanel({ docId, onReload }: Props) {
  const [job, setJob] = useState<NormalizeJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [reloaded, setReloaded] = useState(false);
  const timerRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  // A finished run triggers exactly one refresh, no matter how the tab was left.
  useEffect(() => {
    if (job?.status === "done" && !reloaded) {
      setReloaded(true);
      onReload?.();
    }
  }, [job, reloaded, onReload]);

  const poll = useCallback(
    async (attempt = 0) => {
      try {
        const next = await api.getNormalizeJob(docId);
        setJob(next);
        if (next.status === "running") {
          if (attempt >= POLL_LIMIT) {
            setErr("Normalization is taking too long — check Settings and try again.");
            return;
          }
          timerRef.current = window.setTimeout(() => void poll(attempt + 1), POLL_MS);
        }
      } catch (pollErr) {
        setErr(errText(pollErr));
      }
    },
    [docId],
  );

  const start = useCallback(async () => {
    setBusy(true);
    setErr(null);
    setReloaded(false);
    try {
      const started = await api.normalizeDocument(docId);
      setJob(started);
      if (started.status === "running") {
        timerRef.current = window.setTimeout(() => void poll(), POLL_MS);
      }
    } catch (startErr) {
      setErr(errText(startErr));
    } finally {
      setBusy(false);
    }
  }, [docId, poll]);

  const running = job?.status === "running";
  const failed = job?.status === "failed";
  const done = job?.status === "done";
  const pct = job && job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        Rewrites every question in College Board style — fixes OCR artifacts and garbled
        text. Answers, materials, options and citations stay unchanged. Runs in the
        background with one AI call per question; questions that fail validation keep
        their original text.
      </p>

      <button
        type="button"
        onClick={() => void start()}
        disabled={busy || running}
        className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {running ? "Normalizing…" : "Normalize whole document"}
      </button>

      {running && (
        <div>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={job?.total || 0}
            aria-valuenow={job?.done || 0}
            aria-label="Normalization progress"
            className="h-2 w-full overflow-hidden rounded bg-slate-200"
          >
            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {job?.done ?? 0} / {job?.total ?? 0} questions
          </p>
        </div>
      )}

      {done && (
        <p className="rounded bg-emerald-50 px-2 py-1.5 text-xs text-emerald-800">
          Applied {job?.applied ?? 0} of {job?.total ?? 0} questions
          {(job?.unchanged ?? 0) > 0 ? ` · ${job?.unchanged} already clean` : ""}
          {(job?.kept ?? 0) > 0 ? ` · ${job?.kept} kept original` : ""}.
        </p>
      )}

      {(failed || (done && (job?.kept ?? 0) > 0)) && (
        <ul className="max-h-48 space-y-1 overflow-y-auto rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
          {failed && <li>{job?.error ?? "Unknown error"}</li>}
          {done &&
            (job?.errors ?? []).map((message) => <li key={message}>{message}</li>)}
        </ul>
      )}

      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  );
}
