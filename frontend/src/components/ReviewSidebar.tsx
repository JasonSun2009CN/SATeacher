import { useEffect, useState } from "react";
import { api, ApiError, type ResultItem, type WordGrid } from "../api/client";

type Section = "explain" | "words" | "ai" | "export";

interface Props {
  docId: number;
  item: ResultItem | null;
  onClose: () => void;
  onExplainSaved: (questionId: number, content: string) => void;
}

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

function SectionToggle({
  label,
  open,
  onClick,
}: {
  label: string;
  open: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-expanded={open}
      className="flex w-full items-center gap-2 rounded-md bg-slate-200/70 px-2.5 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-700 hover:bg-slate-200"
    >
      <span className="text-slate-500">{open ? "▾" : "▸"}</span>
      {label}
    </button>
  );
}

/**
 * IDE-style collapsible workspace for the results page:
 * hand-written explanations, the vocabulary table, and the AI answer panel.
 */
export default function ReviewSidebar({ docId, item, onClose, onExplainSaved }: Props) {
  const [open, setOpen] = useState<Section | null>("explain");

  // ---- explanations -------------------------------------------------------
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [explainErr, setExplainErr] = useState<string | null>(null);

  // ---- vocabulary grid ----------------------------------------------------
  const [grid, setGrid] = useState<WordGrid | null>(null);
  const [gridDirty, setGridDirty] = useState(false);
  const [gridBusy, setGridBusy] = useState(false);
  const [gridMsg, setGridMsg] = useState<string | null>(null);
  const [gridErr, setGridErr] = useState<string | null>(null);

  // ---- AI answer ----------------------------------------------------------
  const [aiText, setAiText] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiErr, setAiErr] = useState<string | null>(null);

  // reset per-question state when the selection changes
  useEffect(() => {
    setDraft(item?.explain ?? "");
    setDirty(false);
    setSavedFlash(false);
    setExplainErr(null);
    setAiText(null);
    setAiErr(null);
  }, [item?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function toggle(section: Section) {
    setOpen((prev) => (prev === section ? null : section));
    if (section === "words" && !grid) {
      try {
        setGrid(await api.getWords(docId));
      } catch (err) {
        setGridErr(errText(err));
      }
    }
  }

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

  // ---- grid helpers -------------------------------------------------------
  function mutate(next: WordGrid) {
    setGrid(next);
    setGridDirty(true);
    setGridMsg(null);
    setGridErr(null);
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

  async function saveGrid(): Promise<boolean> {
    if (!grid) return true;
    setGridBusy(true);
    setGridErr(null);
    try {
      const saved = await api.putWords(docId, grid);
      setGrid(saved);
      setGridDirty(false);
      setGridMsg("Saved ✓");
      window.setTimeout(() => setGridMsg(null), 2000);
      return true;
    } catch (err) {
      setGridErr(errText(err));
      return false;
    } finally {
      setGridBusy(false);
    }
  }

  async function exportXlsx() {
    if (gridDirty && !(await saveGrid())) return;
    const a = document.createElement("a");
    a.href = api.wordsExportUrl(docId);
    a.click();
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
    <aside className="w-full shrink-0 lg:w-[24rem]">
      <div className="rounded-xl border bg-slate-50 shadow-sm">
        <header className="flex items-center justify-between border-b bg-white px-3 py-2">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Workspace
            </div>
            <div className="truncate text-sm font-semibold">
              {item ? `Question ${item.no} · ${item.sec === "math" ? "Math" : "Reading & Writing"}` : "Select a question"}
            </div>
          </div>
          <button
            onClick={onClose}
            title="Hide panel"
            className="rounded-md border px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            «
          </button>
        </header>

        <div className="space-y-2 p-3">
          {/* ---- hand-written explanation ---- */}
          <section className="rounded-md">
            <SectionToggle
              label="Explanation"
              open={open === "explain"}
              onClick={() => void toggle("explain")}
            />
            {open === "explain" && (
              <div className="mt-2">
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
                      rows={7}
                      placeholder="Why is the correct answer right? Write it in your own words…"
                      className="w-full rounded-lg border bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
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
                      {dirty && !saving && (
                        <span className="text-xs text-amber-600">unsaved changes</span>
                      )}
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
          </section>

          {/* ---- vocabulary table ---- */}
          <section className="rounded-md">
            <SectionToggle
              label="Vocabulary"
              open={open === "words"}
              onClick={() => void toggle("words")}
            />
            {open === "words" && (
              <div className="mt-2">
                {gridErr && !grid && (
                  <p className="rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">{gridErr}</p>
                )}
                {grid && (
                  <>
                    <div className="overflow-x-auto rounded-lg border bg-white">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-slate-100">
                            {grid.headers.map((h, ci) => (
                              <th key={ci} className="min-w-[7rem] p-1 font-semibold">
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
                        onClick={() => void saveGrid()}
                        disabled={!gridDirty || gridBusy}
                        className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
                      >
                        {gridBusy ? "Saving…" : "Save"}
                      </button>
                      <button
                        onClick={() => void exportXlsx()}
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
                      >
                        Export .xlsx
                      </button>
                      {gridMsg && <span className="text-sm text-emerald-600">{gridMsg}</span>}
                      {gridDirty && !gridBusy && (
                        <span className="text-xs text-amber-600">unsaved changes</span>
                      )}
                    </div>
                    {gridErr && (
                      <p className="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">
                        {gridErr}
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
          </section>

          {/* ---- AI answer ---- */}
          <section className="rounded-md">
            <SectionToggle label="AI Answer" open={open === "ai"} onClick={() => void toggle("ai")} />
            {open === "ai" && (
              <div className="mt-2">
                {!item ? (
                  <p className="text-sm text-slate-500">Select a question in the list.</p>
                ) : item.answer === null ? (
                  <p className="rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
                    No answer key for this question — enter the answers first.
                  </p>
                ) : (
                  <>
                    <p className="mb-2 text-xs text-slate-500">
                      Context: this question + its correct answer only.
                    </p>
                    <button
                      onClick={() => void askAI()}
                      disabled={aiBusy}
                      className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {aiBusy ? "Thinking…" : aiText ? "Regenerate" : "Explain with AI"}
                    </button>
                    {aiErr && (
                      <p className="mt-2 rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">
                        {aiErr}
                      </p>
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
          </section>

          {/* ---- export ---- */}
          <section className="rounded-md">
            <SectionToggle
              label="Export"
              open={open === "export"}
              onClick={() => void toggle("export")}
            />
            {open === "export" && (
              <div className="mt-2">
                <p className="text-xs text-slate-500">
                  Questions, answers and explanations as a document (no AI involved).
                </p>
                <div className="mt-2 flex gap-2">
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
                {dirty && (
                  <p className="mt-2 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
                    Save the explanation first — unsaved changes are not included.
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </aside>
  );
}
