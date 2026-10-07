import { useEffect, useState } from "react";
import { api, ApiError, type WordGrid } from "../../api/client";
import Splitter from "./Splitter";
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
 * Full-width bottom sheet holding the vocabulary table.
 *
 * Batch 9 relocates the existing inline editor here (collapsible, resizable,
 * persistent height); the grid itself is upgraded to v2 in a later batch.
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

  function setCell(ri: number, ci: number, value: string) {
    if (!grid) return;
    const rows = grid.rows.map((row, r) =>
      r === ri ? row.map((cell, c) => (c === ci ? value : cell)) : row,
    );
    mutate({ ...grid, rows });
  }

  function addRow() {
    if (!grid) return;
    mutate({ ...grid, rows: [...grid.rows, new Array(grid.headers.length).fill("")] });
  }

  function delRow(ri: number) {
    if (!grid) return;
    mutate({ ...grid, rows: grid.rows.filter((_r, i) => i !== ri) });
  }

  function addColumn() {
    if (!grid) return;
    mutate({
      headers: [...grid.headers, `Column ${grid.headers.length + 1}`],
      rows: grid.rows.map((row) => [...row, ""]),
    });
  }

  function delColumn(ci: number) {
    if (!grid || grid.headers.length <= 1) return;
    mutate({
      headers: grid.headers.filter((_h, i) => i !== ci),
      rows: grid.rows.map((row) => row.filter((_c, i) => i !== ci)),
    });
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
        {grid && (
          <span className="text-xs text-slate-400">
            {grid.rows.length} {grid.rows.length === 1 ? "word" : "words"}
          </span>
        )}
        {dirty && !busy && <span className="text-xs text-amber-600">unsaved changes</span>}
        {busy && <span className="text-xs text-slate-400">Saving…</span>}
        {msg && <span className="text-xs text-emerald-600">{msg}</span>}
        {err && !grid && <span className="text-xs text-red-600">{err}</span>}
        <div className="ml-auto flex items-center gap-1">
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
        <div className="min-h-0 flex-1 overflow-auto px-3 pb-3">
          {grid ? (
            <>
              <div className="overflow-x-auto rounded-lg border bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-slate-100">
                      {grid.headers.map((h, ci) => (
                        <th key={ci} className="min-w-[8rem] p-1 font-semibold">
                          <div className="flex items-center gap-1">
                            <input
                              value={h}
                              onChange={(e) =>
                                mutate({
                                  ...grid,
                                  headers: grid.headers.map((x, i) =>
                                    i === ci ? e.target.value : x,
                                  ),
                                })
                              }
                              className="w-full rounded border bg-transparent px-1 py-0.5 text-xs font-semibold focus:border-blue-400 focus:outline-none"
                            />
                            <button
                              onClick={() => delColumn(ci)}
                              title="Delete column"
                              className="shrink-0 rounded px-1 text-xs text-slate-400 hover:bg-red-100 hover:text-red-600"
                            >
                              ✕
                            </button>
                          </div>
                        </th>
                      ))}
                      <th className="w-8 p-1">
                        <button
                          onClick={addColumn}
                          title="Add column"
                          className="rounded px-1.5 text-slate-500 hover:bg-slate-200"
                        >
                          +
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {grid.rows.map((row, ri) => (
                      <tr key={ri} className="border-b last:border-0">
                        {grid.headers.map((_h, ci) => (
                          <td key={ci} className="p-1">
                            <input
                              value={row[ci] ?? ""}
                              onChange={(e) => setCell(ri, ci, e.target.value)}
                              className="w-full rounded border border-transparent bg-transparent px-1 py-1 text-xs hover:border-slate-200 focus:border-blue-400 focus:outline-none"
                            />
                          </td>
                        ))}
                        <td className="p-1 text-center">
                          <button
                            onClick={() => delRow(ri)}
                            title="Delete row"
                            className="rounded px-1 text-xs text-slate-400 hover:bg-red-100 hover:text-red-600"
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                    {grid.rows.length === 0 && (
                      <tr>
                        <td
                          colSpan={grid.headers.length + 1}
                          className="px-2 py-3 text-center text-xs text-slate-400"
                        >
                          No words yet — add your first row.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  onClick={addRow}
                  className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-100"
                >
                  + Row
                </button>
                <button
                  onClick={() => void save()}
                  disabled={!dirty || busy}
                  className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
                >
                  {busy ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={() => void exportXlsxFile()}
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
                >
                  Export .xlsx
                </button>
              </div>
              {err && (
                <p className="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">{err}</p>
              )}
            </>
          ) : (
            !err && <p className="text-sm text-slate-400">Loading vocabulary…</p>
          )}
        </div>
      )}
    </section>
  );
}