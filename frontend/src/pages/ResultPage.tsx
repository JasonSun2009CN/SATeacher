import { useEffect, useState } from "react";
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

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setResult(null);
    setError(null);
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

  return (
    <Workspace
      key={detail.document_id}
      detail={detail}
      result={result}
      t={t}
      sessionId={sessionId}
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