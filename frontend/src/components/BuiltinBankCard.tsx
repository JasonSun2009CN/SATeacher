import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type BuiltinBank, type BuiltinUnit } from "../api/client";

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

interface Props {
  bank: BuiltinBank;
  /** Reload banks + library after a successful add. */
  onChanged: () => void;
}

/** "25年8月北美 · Routing A" -> date "25年8月北美", variant "Routing A". */
function splitTitle(title: string): { date: string; variant: string } {
  const at = title.indexOf(" · ");
  return at === -1
    ? { date: title, variant: "" }
    : { date: title.slice(0, at), variant: title.slice(at + 3) };
}

/**
 * Collapsed card for one shipped question bank; expands into date-grouped
 * modules with single Add buttons and an "Add all" batch action.
 */
export default function BuiltinBankCard({ bank, onChanged }: Props) {
  const [open, setOpen] = useState(false);
  const [busyUnit, setBusyUnit] = useState<string | null>(null);
  const [busyAll, setBusyAll] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalQuestions = bank.units.reduce((n, u) => n + u.questions, 0);
  const addedCount = bank.units.filter((u) => u.added).length;
  const allAdded = addedCount === bank.units.length;
  const busy = busyAll || busyUnit !== null;

  // group consecutive units that share the date part of their title
  const groups: { date: string; units: BuiltinUnit[] }[] = [];
  for (const unit of bank.units) {
    const { date } = splitTitle(unit.title);
    const last = groups[groups.length - 1];
    if (last && last.date === date) last.units.push(unit);
    else groups.push({ date, units: [unit] });
  }

  async function addUnit(unit: BuiltinUnit) {
    setBusyUnit(unit.id);
    setError(null);
    setFlash(null);
    try {
      await api.addBuiltinUnit(bank.id, unit.id);
      onChanged();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusyUnit(null);
    }
  }

  async function addAll() {
    setBusyAll(true);
    setError(null);
    setFlash(null);
    try {
      const res = await api.addBuiltinAll(bank.id);
      setFlash(
        res.added > 0
          ? `${res.added} modules added`
          : "Everything is already in your library",
      );
      onChanged();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusyAll(false);
    }
  }

  return (
    <section className="mt-6 rounded-xl border bg-white shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-bank={bank.id}
        className="flex w-full items-center justify-between gap-4 p-5 text-left hover:bg-slate-50"
      >
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">
            {bank.title}
            <span className="ml-2 align-middle rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
              built-in
            </span>
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {bank.units.length} modules · {totalQuestions} questions · answers
            included · offline (0 tokens)
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-sm text-slate-600">
            {addedCount}/{bank.units.length} in library
          </span>
          <span className="text-slate-400" aria-hidden>
            {open ? "▾" : "▸"}
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t px-5 py-4">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <button
              onClick={() => void addAll()}
              disabled={busy}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busyAll
                ? "Adding…"
                : allAdded
                  ? "All in library"
                  : "Add all"}
            </button>
            {flash && <span className="text-sm text-emerald-600">{flash}</span>}
            {error && <span className="text-sm text-red-600">{error}</span>}
          </div>

          <div className="space-y-4">
            {groups.map((group) => (
              <div key={group.date}>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {group.date}
                </h3>
                <ul className="mt-1.5 grid gap-1.5 sm:grid-cols-2">
                  {group.units.map((unit) => {
                    const { variant } = splitTitle(unit.title);
                    return (
                      <li
                        key={unit.id}
                        data-unit={unit.id}
                        className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {variant || unit.title}
                          </div>
                          <div className="text-xs text-slate-500">
                            {unit.questions} questions
                            {unit.module !== null && ` · Module ${unit.module}`}
                          </div>
                        </div>
                        {unit.added && unit.document_id !== null ? (
                          <Link
                            to={`/doc/${unit.document_id}/practice`}
                            title="Open in library"
                            className="shrink-0 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
                          >
                            ✓ In library
                          </Link>
                        ) : (
                          <button
                            onClick={() => void addUnit(unit)}
                            disabled={busy}
                            data-add-unit={unit.id}
                            className="shrink-0 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                          >
                            {busyUnit === unit.id ? "Adding…" : "Add"}
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
