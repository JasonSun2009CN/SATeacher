import {
  useMemo,
  useRef,
  type ClipboardEvent as ReactClipboardEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { VocabColumn, WordGrid } from "../../api/client";

interface Props {
  grid: WordGrid;
  onChange: (grid: WordGrid) => void;
}

const MIN_WIDTH = 60;
const MAX_WIDTH = 800;
const DEFAULT_WIDTH = 180;
const MAX_COLUMNS = 12;
const MAX_ROWS = 500;

/** Deterministic, collision-free column id (`c1`, `c2`, …) — mirrors the backend. */
function makeColumnId(columns: VocabColumn[]): string {
  const used = new Set(columns.map((c) => c.id));
  let n = columns.length + 1;
  while (used.has(`c${n}`)) n += 1;
  return `c${n}`;
}

function makeRowId(rows: { id: string }[]): string {
  const used = new Set(rows.map((r) => r.id));
  let n = rows.length + 1;
  while (used.has(`r${n}`)) n += 1;
  return `r${n}`;
}

function hasActiveView(grid: WordGrid): boolean {
  return grid.view.sort !== null || Object.values(grid.view.filter).some((v) => v.trim() !== "");
}

/**
 * Batch-10 vocabulary grid (v2): stable row/column ids, resizable columns,
 * sort, per-column filter and Excel-style multi-cell paste — all in-house
 * (no new dependency). Pure presentation over a controlled {@link WordGrid}.
 */
export default function VocabGrid({ grid, onChange }: Props) {
  const refs = useRef(new Map<string, HTMLInputElement>());
  const cellKey = (rowId: string, colId: string) => `${rowId}::${colId}`;

  const sort = grid.view.sort;
  const activeFilters = Object.values(grid.view.filter).filter((v) => v.trim() !== "").length;

  const visible = useMemo(() => {
    let rows = grid.rows;
    const filters = Object.entries(grid.view.filter).filter(([, v]) => v.trim() !== "");
    if (filters.length) {
      rows = rows.filter((row) =>
        filters.every(([colId, needle]) =>
          (row.cells[colId] ?? "").toLowerCase().includes(needle.trim().toLowerCase()),
        ),
      );
    }
    if (grid.view.sort) {
      const dir = grid.view.sort.direction === "asc" ? 1 : -1;
      const key = grid.view.sort.columnId;
      rows = [...rows].sort(
        (a, b) =>
          dir *
          (a.cells[key] ?? "").localeCompare(b.cells[key] ?? "", undefined, {
            sensitivity: "base",
            numeric: true,
          }),
      );
    }
    return rows;
  }, [grid.rows, grid.view]);

  // ---- mutations ----------------------------------------------------------

  function setCell(rowId: string, colId: string, value: string) {
    onChange({
      ...grid,
      rows: grid.rows.map((r) =>
        r.id === rowId ? { ...r, cells: { ...r.cells, [colId]: value } } : r,
      ),
    });
  }

  function updateColumn(colId: string, patch: Partial<VocabColumn>) {
    onChange({
      ...grid,
      columns: grid.columns.map((c) => (c.id === colId ? { ...c, ...patch } : c)),
    });
  }

  function addRow() {
    if (grid.rows.length >= MAX_ROWS) return;
    const id = makeRowId(grid.rows);
    const cells = Object.fromEntries(grid.columns.map((c) => [c.id, ""]));
    onChange({ ...grid, rows: [...grid.rows, { id, cells }] });
  }

  function deleteRow(rowId: string) {
    onChange({ ...grid, rows: grid.rows.filter((r) => r.id !== rowId) });
  }

  function addColumn() {
    if (grid.columns.length >= MAX_COLUMNS) return;
    const id = makeColumnId(grid.columns);
    onChange({
      ...grid,
      columns: [
        ...grid.columns,
        { id, name: `Column ${grid.columns.length + 1}`, width: DEFAULT_WIDTH },
      ],
    });
  }

  function deleteColumn(colId: string) {
    if (grid.columns.length <= 1) return;
    const filter = { ...grid.view.filter };
    delete filter[colId];
    const nextSort = sort?.columnId === colId ? null : sort;
    onChange({
      ...grid,
      columns: grid.columns.filter((c) => c.id !== colId),
      view: { sort: nextSort, filter },
    });
  }

  function toggleSort(colId: string) {
    let next: WordGrid["view"]["sort"];
    if (!sort || sort.columnId !== colId) next = { columnId: colId, direction: "asc" };
    else if (sort.direction === "asc") next = { columnId: colId, direction: "desc" };
    else next = null;
    onChange({ ...grid, view: { ...grid.view, sort: next } });
  }

  function setFilter(colId: string, value: string) {
    onChange({
      ...grid,
      view: { ...grid.view, filter: { ...grid.view.filter, [colId]: value } },
    });
  }

  function resetView() {
    onChange({ ...grid, view: { sort: null, filter: {} } });
  }

  // ---- column resize ------------------------------------------------------

  function startResize(e: ReactPointerEvent, col: VocabColumn) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = col.width;
    let current = startW;
    const move = (ev: PointerEvent) => {
      const w = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startW + (ev.clientX - startX)));
      if (w !== current) {
        current = w;
        updateColumn(col.id, { width: w });
      }
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // ---- keyboard navigation + paste ---------------------------------------

  function focusCell(r: number, c: number) {
    const row = visible[r];
    const col = grid.columns[c];
    if (!row || !col) return;
    const el = refs.current.get(cellKey(row.id, col.id));
    if (el) {
      el.focus();
      el.select();
    }
  }

  function onCellKeyDown(e: ReactKeyboardEvent<HTMLInputElement>, r: number, c: number) {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      focusCell(r - 1, c);
    } else if (e.key === "ArrowDown" || e.key === "Enter") {
      e.preventDefault();
      focusCell(r + 1, c);
    }
  }

  function onPaste(e: ReactClipboardEvent<HTMLInputElement>, startR: number, startC: number) {
    const text = e.clipboardData.getData("text/plain");
    if (!text || (!text.includes("\t") && !text.includes("\n"))) return; // single value: default
    e.preventDefault();
    const lines = text.replace(/\r\n?/g, "\n").split("\n");
    if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
    applyPaste(startR, startC, lines.map((line) => line.split("\t")));
  }

  function applyPaste(startR: number, startC: number, matrix: string[][]) {
    // Columns first: widen the grid if the block overflows to the right.
    const width = Math.max(...matrix.map((m) => m.length), 1);
    const columns = [...grid.columns];
    while (columns.length < startC + width && columns.length < MAX_COLUMNS) {
      const id = makeColumnId(columns);
      columns.push({ id, name: `Column ${columns.length + 1}`, width: DEFAULT_WIDTH });
    }

    const rows = grid.rows.map((r) => ({ ...r, cells: { ...r.cells } }));
    const targetIds = visible.map((r) => r.id);

    // Grow rows only when the view is unfiltered/unsorted (Excel-like); with an
    // active view we clip to the rows currently on screen.
    if (!hasActiveView(grid)) {
      const needed = startR + matrix.length;
      while (targetIds.length < needed && rows.length < MAX_ROWS) {
        const id = makeRowId(rows);
        rows.push({ id, cells: Object.fromEntries(columns.map((c) => [c.id, ""])) });
        targetIds.push(id);
      }
    }

    const targetRows = new Map(rows.map((r) => [r.id, r]));
    for (let dr = 0; dr < matrix.length; dr++) {
      const rowId = visible[startR + dr]?.id ?? targetIds[startR + dr];
      const row = rowId ? targetRows.get(rowId) : undefined;
      if (!row) break;
      for (let dc = 0; dc < matrix[dr].length; dc++) {
        const col = columns[startC + dc];
        if (!col) break;
        row.cells[col.id] = matrix[dr][dc];
      }
    }
    onChange({ ...grid, columns, rows });
  }

  // ---- render -------------------------------------------------------------

  function sortGlyph(colId: string): string {
    if (sort?.columnId !== colId) return "↕";
    return sort.direction === "asc" ? "▲" : "▼";
  }

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="vocab-grid">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={addRow}
          disabled={grid.rows.length >= MAX_ROWS}
          className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
        >
          + Row
        </button>
        <button
          type="button"
          onClick={addColumn}
          disabled={grid.columns.length >= MAX_COLUMNS}
          className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
        >
          + Column
        </button>
        {(sort || activeFilters > 0) && (
          <button
            type="button"
            onClick={resetView}
            className="rounded-lg border px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Reset view
          </button>
        )}
        <span className="ml-auto text-xs text-slate-400" data-testid="vocab-count">
          {grid.rows.length} {grid.rows.length === 1 ? "word" : "words"}
          {visible.length !== grid.rows.length ? ` · ${visible.length} shown` : ""}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-lg border bg-white">
        <table className="border-collapse text-sm">
          <colgroup>
            {grid.columns.map((c) => (
              <col key={c.id} style={{ width: `${c.width}px` }} />
            ))}
            <col style={{ width: "34px" }} />
          </colgroup>
          <thead>
            <tr>
              {grid.columns.map((col) => (
                <th
                  key={col.id}
                  className="sticky top-0 z-10 border-b border-r border-slate-200 bg-slate-100 p-1 align-top"
                >
                  <div className="flex items-center gap-1">
                    <input
                      value={col.name}
                      onChange={(e) => updateColumn(col.id, { name: e.target.value })}
                      aria-label={`Column name`}
                      className="w-full min-w-0 rounded border border-transparent bg-transparent px-1 py-0.5 text-xs font-semibold hover:border-slate-300 focus:border-blue-400 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => toggleSort(col.id)}
                      title="Sort column"
                      aria-label={`Sort by ${col.name}`}
                      className="shrink-0 rounded px-1 text-xs text-slate-500 hover:bg-slate-200"
                    >
                      {sortGlyph(col.id)}
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteColumn(col.id)}
                      disabled={grid.columns.length <= 1}
                      title="Delete column"
                      aria-label={`Delete ${col.name}`}
                      className="shrink-0 rounded px-1 text-xs text-slate-400 hover:bg-red-100 hover:text-red-600 disabled:opacity-30"
                    >
                      ✕
                    </button>
                  </div>
                  <input
                    value={grid.view.filter[col.id] ?? ""}
                    onChange={(e) => setFilter(col.id, e.target.value)}
                    placeholder="Filter…"
                    aria-label={`Filter ${col.name}`}
                    className="mt-0.5 w-full rounded border border-slate-200 bg-white px-1 py-0.5 text-[11px] font-normal text-slate-600 focus:border-blue-400 focus:outline-none"
                  />
                  <div
                    role="separator"
                    aria-orientation="vertical"
                    aria-label={`Resize ${col.name}`}
                    onPointerDown={(e) => startResize(e, col)}
                    className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize touch-none hover:bg-blue-400/40"
                  />
                </th>
              ))}
              <th className="sticky top-0 z-10 border-b border-slate-200 bg-slate-100 p-1">
                <button
                  type="button"
                  onClick={addColumn}
                  disabled={grid.columns.length >= MAX_COLUMNS}
                  title="Add column"
                  className="rounded px-1.5 text-slate-500 hover:bg-slate-200 disabled:opacity-30"
                >
                  +
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row, r) => (
              <tr key={row.id} className="group">
                {grid.columns.map((col, c) => (
                  <td key={col.id} className="border-b border-r border-slate-200 p-0">
                    <input
                      ref={(el) => {
                        if (el) refs.current.set(cellKey(row.id, col.id), el);
                        else refs.current.delete(cellKey(row.id, col.id));
                      }}
                      value={row.cells[col.id] ?? ""}
                      onChange={(e) => setCell(row.id, col.id, e.target.value)}
                      onKeyDown={(e) => onCellKeyDown(e, r, c)}
                      onPaste={(e) => onPaste(e, r, c)}
                      aria-label={`${col.name} row ${r + 1}`}
                      className="w-full rounded-none border-0 bg-transparent px-2 py-1 text-xs focus:bg-blue-50 focus:outline-none focus:ring-1 focus:ring-inset focus:ring-blue-400"
                    />
                  </td>
                ))}
                <td className="border-b border-slate-200 p-0 text-center">
                  <button
                    type="button"
                    onClick={() => deleteRow(row.id)}
                    title="Delete row"
                    aria-label={`Delete row ${r + 1}`}
                    className="w-full px-1 text-xs text-slate-300 hover:bg-red-100 hover:text-red-600 group-hover:text-slate-400"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td
                  colSpan={grid.columns.length + 1}
                  className="px-2 py-4 text-center text-xs text-slate-400"
                >
                  {grid.rows.length === 0
                    ? "No words yet — add your first row."
                    : "No rows match the filter."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}