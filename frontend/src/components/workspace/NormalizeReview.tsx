import { useState } from "react";
import { api, type QuestionText } from "../../api/client";

interface Props {
  docId: number;
  questionId: number;
  onClose: () => void;
  onAccepted: () => void;
}

function diffHighlight(original: string, normalized: string): React.ReactNode {
  // For simplicity, just show both with color coding if different
  if (original === normalized) return <span className="text-slate-900">{original}</span>;

  return (
    <span className="relative">
      <span className="line-through text-red-500 text-sm">{original}</span>
      <span className="ml-1 text-emerald-600 font-medium">{normalized}</span>
    </span>
  );
}

export default function NormalizeReview({ docId, questionId, onClose, onAccepted }: Props) {
  const [state, setState] = useState<"loading" | "ready" | "saving">("loading");
  const [original, setOriginal] = useState<QuestionText | null>(null);
  const [normalized, setNormalized] = useState<QuestionText | null>(null);
  const [changed, setChanged] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);

  // Load normalization on mount
  const load = async () => {
    try {
      const res = await api.normalizeQuestion(docId, questionId);
      setOriginal(res.original);
      setNormalized(res.normalized);
      setChanged(res.changed);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setState("ready");
    }
  };

  // Initial load
  const mounted = useState(true)[0];
  if (mounted && state === "loading") {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useState(() => {
      load();
      return () => {};
    });
  }

  const handleAccept = async () => {
    if (!normalized) return;
    setState("saving");
    setErr(null);
    try {
      await api.acceptNormalization(docId, questionId, normalized);
      onAccepted();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setState("ready");
    }
  };

  const handleRegenerate = async () => {
    setState("loading");
    setErr(null);
    await load();
  };

  if (state === "loading") {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-3 border-blue-600 border-t-transparent mx-auto"></div>
          <p className="mt-2 text-sm text-slate-600">Generating normalization…</p>
        </div>
      </div>
    );
  }

  if (err) {
    return (
      <div className="p-4 rounded-lg bg-red-50 text-red-700">
        <p className="font-medium">Normalization failed</p>
        <p className="text-sm mt-1">{err}</p>
        <div className="mt-3 flex gap-2">
          <button onClick={handleRegenerate} className="rounded-lg border px-3 py-1.5 text-sm">
            Retry
          </button>
          <button onClick={onClose} className="rounded-lg border px-3 py-1.5 text-sm">
            Close
          </button>
        </div>
      </div>
    );
  }

  if (!original || !normalized) {
    return null;
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b px-3 py-2 shrink-0">
        <h2 className="text-lg font-semibold">Review Normalization</h2>
        <button onClick={onClose} className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100">
          ×
        </button>
      </header>

      {changed.length > 0 && (
        <div className="px-3 py-2 text-xs text-amber-700 bg-amber-50 border-b">
          Changed options: <span className="font-mono">{changed.join(", ")}</span>
        </div>
      )}

      <div className="flex-1 overflow-auto p-3 grid gap-4 md:grid-cols-2">
        {/* Original */}
        <section className="flex flex-col gap-2 rounded-lg border bg-red-50 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-red-700">Original</h3>
          {original.material && (
            <div className="text-sm text-slate-700 whitespace-pre-wrap border rounded p-2 bg-white">
              <span className="font-medium">Material: </span>
              {original.material}
            </div>
          )}
          <div className="text-sm text-slate-900 whitespace-pre-wrap border rounded p-2 bg-white">
            <span className="font-medium">Stem: </span>
            {diffHighlight(original.stem, normalized.stem)}
          </div>
          <div className="space-y-1">
            {(["A", "B", "C", "D"] as const).map((k) => (
              <div key={k} className="text-sm whitespace-pre-wrap border rounded p-2 bg-white">
                <span className="font-mono font-medium text-slate-600">{k}. </span>
                {diffHighlight(original.options[k], normalized.options[k])}
              </div>
            ))}
          </div>
          <div className="text-xs text-slate-500">Answer: <span className="font-mono">{original.answer}</span></div>
        </section>

        {/* Normalized */}
        <section className="flex flex-col gap-2 rounded-lg border bg-emerald-50 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
            Normalized <span className="font-normal text-xs text-slate-500">(editable)</span>
          </h3>
          {normalized.material && (
            <div className="space-y-1">
              <label className="text-xs text-slate-500">Material</label>
              <textarea
                value={normalized.material || ""}
                onChange={(e) => setNormalized({ ...normalized, material: e.target.value })}
                rows={3}
                className="w-full rounded border px-2 py-1 text-sm focus:border-blue-400 focus:outline-none"
              />
            </div>
          )}
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Stem</label>
            <textarea
              value={normalized.stem}
              onChange={(e) => setNormalized({ ...normalized, stem: e.target.value })}
              rows={3}
              className="w-full rounded border px-2 py-1 text-sm focus:border-blue-400 focus:outline-none"
            />
          </div>
          <div className="space-y-1">
            {(["A", "B", "C", "D"] as const).map((k) => (
              <div key={k} className="space-y-0.5">
                <label className="text-xs text-slate-500">Option {k}</label>
                <input
                  value={normalized.options[k]}
                  onChange={(e) =>
                    setNormalized({ ...normalized, options: { ...normalized.options, [k]: e.target.value } })
                  }
                  className="w-full rounded border px-2 py-1 text-sm focus:border-blue-400 focus:outline-none"
                />
              </div>
            ))}
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-500">Answer (must match original)</label>
            <select
              value={normalized.answer}
              onChange={(e) => setNormalized({ ...normalized, answer: e.target.value as "A" | "B" | "C" | "D" })}
              className="w-full rounded border px-2 py-1 text-sm focus:border-blue-400 focus:outline-none"
            >
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
            </select>
          </div>
        </section>
      </div>

      <footer className="flex items-center justify-end gap-2 border-t px-3 py-2 shrink-0">
        <button onClick={handleRegenerate} disabled={state === "saving"} className="rounded-lg border px-3 py-1.5 text-sm">
          Regenerate
        </button>
        <button onClick={onClose} disabled={state === "saving"} className="rounded-lg border px-3 py-1.5 text-sm">
          Cancel
        </button>
        <button
          onClick={handleAccept}
          disabled={state === "saving"}
          className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {state === "saving" ? "Saving…" : "Accept & Save"}
        </button>
      </footer>
    </div>
  );
}