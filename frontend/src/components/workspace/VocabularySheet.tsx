import { useEffect, useState } from "react";
import { api, ApiError, type WordGrid } from "../../api/client";
import Splitter from "./Splitter";
import VocabGrid from "./VocabGrid";
import { ChevronDownIcon, MaximizeIcon } from "./icons";

interface Props {
  docId: number;
  open: boolean;
  height: number;
  onToggle: () => void;
  onResize: (deltaPx: number) => void;
  onMaximize: () => void;
  onResetHeight: () => void;
}

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

/**
 * Full-width bottom sheet holding the vocabulary grid.
 *
 * Batch 9 relocates the editor here (collapsible, resizable, persistent
 * height); batch 10 upgrades the grid itself to v2 (stable ids, widths,
 * sort/filter, paste) via {@link VocabGrid}.
 */
export default function VocabularySheet({
  docId,
  open,
  height,
  onToggle,
  onResize,
  onMaximize,
  onResetHeight,
}: Props) {
  const [grid, setGrid] = useState<WordGrid | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // load lazily the first time the sheet is opened
  useEffect(() => {
    if (!open || grid) return;
    let cancelled = false;
    api
      .getWords(docId)
      .then((g) => !cancelled && setGrid(g))
      .catch((e) => !cancelled && setErr(errText(e)));
    return () => {
      cancelled = true;
    };
  }, [open, grid, docId]);

  function mutate(next: WordGrid) {
    setGrid(next);
    setDirty(true);
    setMsg(null);
    setErr(null);
  }

  async function save(): Promise<boolean> {
    if (!grid) return true;
    setBusy(true);
    setErr(null);
    try {
      const saved = await api.putWords(docId, grid);
      setGrid(saved);
      setDirty(false);
      setMsg("Saved ✓");
      window.setTimeout(() => setMsg(null), 2000);
      return true;
    } catch (e) {
      setErr(errText(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function exportXlsxFile() {
    if (dirty && !(await save())) return;
    const a = document.createElement("a");
    a.href = api.wordsExportUrl(docId);
    a.click();
  }

  return (
    <section
      data-testid="vocab-sheet"
      aria-label="Vocabulary sheet"
      className="flex shrink-0 flex-col border-t bg-white"
      style={{ height: open ? height : 44 }}
    >
      {open && (
        <Splitter orientation="horizontal" label="Resize vocabulary sheet" onResize={onResize} onReset={onResetHeight} />
      )}
      <header className="flex h-11 shrink-0 items-center gap-2 px-3">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          <ChevronDownIcon
            size={16}
            className={"transition-transform " + (open ? "" : "-rotate-90")}
          />
          Vocabulary
        </button>
        {dirty && !busy && <span className="text-xs text-amber-600">unsaved changes</span>}
        {busy && <span className="text-xs text-slate-400">Saving…</span>}
        {msg && <span className="text-xs text-emerald-600">{msg}</span>}
        {err && !grid && <span className="text-xs text-red-600">{err}</span>}
        <div className="ml-auto flex items-center gap-2">
          {open && grid && (
            <>
              <button
                type="button"
                data-testid="vocab-save"
                onClick={() => void save()}
                disabled={!dirty || busy}
                className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
              >
                {busy ? "Saving…" : "Save"}
              </button>
              <button
                type="button"
                data-testid="vocab-export-xlsx"
                onClick={() => void exportXlsxFile()}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
              >
                Export .xlsx
              </button>
            </>
          )}
          {open && (
            <button
              type="button"
              onClick={onMaximize}
              title="Maximize vocabulary"
              aria-label="Maximize vocabulary"
              className="rounded-md border px-2 py-1 text-slate-500 hover:bg-slate-100"
            >
              <MaximizeIcon size={16} />
            </button>
          )}
        </div>
      </header>

      {open && (
        <div className="min-h-0 flex-1 px-3 pb-3">
          {grid ? (
            <VocabGrid grid={grid} onChange={mutate} />
          ) : (
            !err && <p className="text-sm text-slate-400">Loading vocabulary…</p>
          )}
          {err && (
            <p className="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">{err}</p>
          )}
        </div>
      )}
    </section>
  );
}