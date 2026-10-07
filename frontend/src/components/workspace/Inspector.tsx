import { useEffect, useState } from "react";
import { api, ApiError, type ResultItem } from "../../api/client";

export type InspectorTab = "explain" | "ai" | "export";

interface Props {
  docId: number;
  item: ResultItem | null;
  tab: InspectorTab;
  onTab: (tab: InspectorTab) => void;
  onClose: () => void;
  onExplainSaved: (questionId: number, content: string) => void;
}

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

const TABS: { key: InspectorTab; label: string }[] = [
  { key: "explain", label: "Explanation" },
  { key: "ai", label: "AI Tutor" },
  { key: "export", label: "Export" },
];

/** Right pane: a fixed, tabbed study inspector (not an accordion). */
export default function Inspector({ docId, item, tab, onTab, onClose, onExplainSaved }: Props) {
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [explainErr, setExplainErr] = useState<string | null>(null);

  const [aiText, setAiText] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiErr, setAiErr] = useState<string | null>(null);

  useEffect(() => {
    setDraft(item?.explain ?? "");
    setDirty(false);
    setSavedFlash(false);
    setExplainErr(null);
    setAiText(null);
    setAiErr(null);
  }, [item?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveExplain() {
    if (!item) return;
    setSaving(true);
    setExplainErr(null);
    try {
      await api.saveExplain(docId, item.question_id, draft);
      setDirty(false);
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
      onExplainSaved(item.question_id, draft);
    } catch (err) {
      setExplainErr(errText(err));
    } finally {
      setSaving(false);
    }
  }

  async function askAI() {
    if (!item) return;
    setAiBusy(true);
    setAiErr(null);
    setAiText(null);
    try {
      const res = await api.askAI(docId, item.question_id);
      setAiText(res.text);
    } catch (err) {
      setAiErr(errText(err));
    } finally {
      setAiBusy(false);
    }
  }

  return (
    <aside data-testid="inspector" className="flex h-full min-h-0 flex-col bg-white">
      <header className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Study Inspector
          </div>
          <div className="truncate text-sm font-semibold">
            {item
              ? `Question ${item.no} · ${item.sec === "math" ? "Math" : "Reading & Writing"}`
              : "Select a question"}
          </div>
        </div>
        <button
          onClick={onClose}
          title="Hide inspector"
          aria-label="Hide inspector"
          className="rounded-md border px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
        >
          »
        </button>
      </header>

      <div className="flex border-b" role="tablist" aria-label="Inspector sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => onTab(t.key)}
            className={`flex-1 border-b-2 px-2 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "explain" && (
          <div>
            {!item ? (
              <p className="text-sm text-slate-500">Select a question in the list.</p>
            ) : (
              <>
                <textarea
                  value={draft}
                  onChange={(e) => {
                    setDraft(e.target.value);
                    setDirty(true);
                    setExplainErr(null);
                  }}
                  rows={10}
                  placeholder="Why is the correct answer right? Write it in your own words…"
                  className="w-full rounded-lg border bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                />
                <div className="mt-2 flex items-center gap-2">
                  <button
                    onClick={() => void saveExplain()}
                    disabled={!dirty || saving}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
                  >
                    {saving ? "Saving…" : "Save"}
                  </button>
                  {savedFlash && <span className="text-sm text-emerald-600">Saved ✓</span>}
                  {dirty && !saving && <span className="text-xs text-amber-600">unsaved changes</span>}
                </div>
                {explainErr && (
                  <p className="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">
                    {explainErr}
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {tab === "ai" && (
          <div>
            {!item ? (
              <p className="text-sm text-slate-500">Select a question in the list.</p>
            ) : item.answer === null ? (
              <p className="rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
                No answer key for this question — enter the answers first.
              </p>
            ) : (
              <>
                <p className="mb-2 text-xs text-slate-500">
                  Context: this question + its correct answer only. Uses your configured model —
                  this may consume tokens.
                </p>
                <button
                  onClick={() => void askAI()}
                  disabled={aiBusy}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {aiBusy ? "Thinking…" : aiText ? "Regenerate" : "Explain with AI"}
                </button>
                {aiErr && (
                  <p className="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">{aiErr}</p>
                )}
                {aiText && (
                  <div className="mt-2 whitespace-pre-wrap rounded-lg border bg-white p-3 text-sm">
                    {aiText}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {tab === "export" && (
          <div>
            <p className="text-xs text-slate-500">
              Questions, answers and saved explanations as a document. This export uses no tokens.
            </p>
            <div className="mt-3 flex gap-2">
              {(["pdf", "docx"] as const).map((fmt) => (
                <a
                  key={fmt}
                  href={api.exportUrl(docId, fmt)}
                  download
                  className="rounded-lg border bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-100"
                >
                  Export .{fmt}
                </a>
              ))}
            </div>
            <div className="mt-4 border-t pt-3">
              <p className="text-xs text-slate-500">Vocabulary sheet (bottom panel).</p>
              <a
                href={api.wordsExportUrl(docId)}
                className="mt-2 inline-block rounded-lg border bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-100"
              >
                Export vocabulary .xlsx
              </a>
            </div>
            {dirty && (
              <p className="mt-3 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
                Unsaved explanation drafts are never included — save first.
              </p>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}