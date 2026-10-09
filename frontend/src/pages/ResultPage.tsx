import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError, type SessionDetail, type SubmitResult } from "../api/client";
import Workspace from "../components/workspace/Workspace";

/** Loads the session then hands off to the three-pane review workspace. */
export default function ResultPage() {
  const { sid } = useParams();
  const sessionId = Number(sid);
  const [searchParams] = useSearchParams();
  const t = Number(searchParams.get("t")) || 0;
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** ``reset`` blanks the view first (initial load); a silent reload just swaps
   *  the data in place, so the workspace does not unmount mid-review. */
  const load = useCallback(
    (reset: boolean, signal?: { cancelled: boolean }) => {
      if (reset) {
        setDetail(null);
        setResult(null);
        setError(null);
      }
      Promise.all([api.getSession(sessionId), api.regradeSession(sessionId)])
        .then(([d, r]) => {
          if (signal?.cancelled) return;
          setDetail(d);
          setResult(r);
        })
        .catch(
          (err) => !signal?.cancelled && setError(err instanceof ApiError ? err.message : String(err)),
        );
    },
    [sessionId],
  );

  useEffect(() => {
    const signal = { cancelled: false };
    load(true, signal);
    return () => {
      signal.cancelled = true;
    };
  }, [load]);

  if (error) {
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
  if (!detail || !result) {
    return <div className="mx-auto max-w-3xl px-4 py-10 text-slate-500">Loading…</div>;
  }

  return (
    <Workspace
      key={detail.document_id}
      detail={detail}
      result={result}
      t={t}
      sessionId={sessionId}
      onReload={() => load(false)}
      onExplainSaved={(questionId, content) =>
        setResult((r) =>
          r && {
            ...r,
            items: r.items.map((i) => (i.question_id === questionId ? { ...i, explain: content } : i)),
          },
        )
      }
    />
  );
}