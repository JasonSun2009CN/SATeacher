import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ResultItem, SessionDetail, SubmitResult } from "../../api/client";
import RichText from "../RichText";
import Inspector from "./Inspector";
import QuestionNav, { type Filter } from "./QuestionNav";
import Splitter from "./Splitter";
import VocabularySheet from "./VocabularySheet";
import { MenuIcon, PanelRightOpenIcon, PanelRightCloseIcon } from "./icons";
import { useMediaQuery } from "./useMediaQuery";
import { useWorkspaceLayout } from "./usePersistentLayout";

const NAV_MIN = 140;
const NAV_MAX = 320;
const INSPECTOR_MIN = 280;
const INSPECTOR_MAX = 620;
const SHEET_MIN = 120;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function optionLetter(option: string): string {
  const m = /^([A-D])[.)]/.exec(option.trim());
  return m ? m[1] : "?";
}

function clock(total: number): string {
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function elapsed(detail: SessionDetail, t: number): number | null {
  if (t > 0) return t;
  if (!detail.started_at || !detail.finished_at) return null;
  const start = Date.parse(detail.started_at.replace(" ", "T") + "Z");
  const end = Date.parse(detail.finished_at.replace(" ", "T") + "Z");
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, Math.round((end - start) / 1000));
}

interface Props {
  detail: SessionDetail;
  result: SubmitResult;
  t: number;
  onExplainSaved: (questionId: number, content: string) => void;
  sessionId: number;
  /** Refetch session questions (e.g. after a document-wide normalization). */
  onReload: () => void;
}

/**
 * Three-pane review workspace: question navigation (left), the question itself
 * (centre, the only scrolling content area) and a tabbed Study Inspector
 * (right), with a collapsible vocabulary sheet pinned along the bottom.
 */
export default function Workspace({ detail, result, t, onExplainSaved, sessionId, onReload }: Props) {
  const docId = detail.document_id;
  const [layout, setLayout] = useWorkspaceLayout(docId);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [mobileInspector, setMobileInspector] = useState(false);

  const isDesktop = useMediaQuery("(min-width: 1024px)");

  const matchesFilter = (i: ResultItem) =>
    filter === "all" ? true : filter === "correct" ? i.is_correct === true : i.is_correct === false;

  useEffect(() => {
    const ids = result.items.filter(matchesFilter).map((i) => i.question_id);
    setSelectedId((prev) => (prev !== null && ids.includes(prev) ? prev : (ids[0] ?? null)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, filter]);

  // keyboard ← / → navigation (ignored while typing)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
      const ids = result.items.filter(matchesFilter).map((i) => i.question_id);
      const idx = selectedId === null ? -1 : ids.indexOf(selectedId);
      const target = e.key === "ArrowLeft" ? idx - 1 : idx + 1;
      if (target >= 0 && target < ids.length) {
        e.preventDefault();
        setSelectedId(ids[target]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-register each render so the closure sees fresh filter/selection

  const visibleItems = result.items.filter(matchesFilter);
  const selected = result.items.find((i) => i.question_id === selectedId) ?? null;
  const vIdx = visibleItems.findIndex((i) => i.question_id === selectedId);
  const prevQ = vIdx > 0 ? visibleItems[vIdx - 1] : null;
  const nextQ = vIdx >= 0 && vIdx < visibleItems.length - 1 ? visibleItems[vIdx + 1] : null;

  const blank = result.items.filter((i) => i.answer !== null && !i.chosen).length;
  const wrong = result.items.filter((i) => i.is_correct === false).length;
  const correct = result.items.filter((i) => i.is_correct === true).length;
  const pct = result.graded ? Math.round((correct / result.graded) * 100) : 0;
  const secs = elapsed(detail, t);

  const statFor = (sec: "rw" | "math") => {
    const inSec = result.items.filter((i) => i.sec === sec);
    const gradedSec = inSec.filter((i) => i.answer !== null);
    return {
      total: inSec.length,
      graded: gradedSec.length,
      correct: gradedSec.filter((i) => i.is_correct === true).length,
    };
  };
  const rwStat = statFor("rw");
  const mathStat = statFor("math");

  const counts: Record<Filter, number> = { all: result.items.length, correct, wrong };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-100">
      {/* ---- top bar -------------------------------------------------------- */}
      <header className="flex shrink-0 items-center gap-2 border-b bg-white px-3 py-2">
        {!isDesktop && (
          <button
            onClick={() => setMobileNav(true)}
            aria-label="Open question list"
            className="rounded-lg border p-1.5 text-slate-600 hover:bg-slate-100"
          >
            <MenuIcon />
          </button>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-bold">{detail.document.title}</h1>
          <p className="truncate text-xs text-slate-500">
            {secs !== null && `${clock(secs)} · `}
            {result.total} questions · {result.graded} graded
          </p>
        </div>
        <div className="hidden text-right sm:block">
          <div className="text-xl font-bold tracking-tight">
            {correct} <span className="text-slate-400">/ {result.graded}</span>
          </div>
          <div className="text-xs text-slate-500">
            {result.graded ? `${pct}%` : "not graded"} · {wrong} wrong
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Link
            to={`/doc/${docId}/practice`}
            className="hidden rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 sm:block"
          >
            Practice again
          </Link>
          <Link
            to="/"
            className="hidden rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-slate-50 sm:block"
          >
            Exams
          </Link>
          {isDesktop ? (
            <button
              onClick={() => setLayout((l) => ({ ...l, inspectorOpen: !l.inspectorOpen }))}
              title={layout.inspectorOpen ? "Hide inspector" : "Show inspector"}
              aria-label={layout.inspectorOpen ? "Hide inspector" : "Show inspector"}
              className="rounded-lg border p-1.5 text-slate-600 hover:bg-slate-50"
            >
              {layout.inspectorOpen ? <PanelRightCloseIcon /> : <PanelRightOpenIcon />}
            </button>
          ) : (
            <button
              onClick={() => setMobileInspector(true)}
              title="Open inspector"
              aria-label="Open inspector"
              className="rounded-lg border p-1.5 text-slate-600 hover:bg-slate-50"
            >
              <PanelRightOpenIcon />
            </button>
          )}
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* ---- left: question navigation (desktop column) ---- */}
        {isDesktop && layout.navOpen && (
          <>
            <div
              data-testid="nav-pane"
              className="flex min-h-0 shrink-0 flex-col border-r bg-white"
              style={{ width: layout.navWidth }}
            >
              <QuestionNav
                visible={visibleItems}
                filter={filter}
                counts={counts}
                selectedId={selectedId}
                onFilter={setFilter}
                onSelect={setSelectedId}
              />
            </div>
            <Splitter
              orientation="vertical"
              label="Resize question list"
              onResize={(d) =>
                setLayout((l) => ({ ...l, navWidth: clamp(l.navWidth + d, NAV_MIN, NAV_MAX) }))
              }
              onReset={() => setLayout((l) => ({ ...l, navWidth: 176 }))}
            />
          </>
        )}

        {/* ---- centre: the only scrolling content + bottom sheet ---- */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <main className="min-h-0 flex-1 overflow-y-auto p-4">
            <section className="rounded-xl border bg-white p-4" aria-label="Session statistics">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat
                  label="Score"
                  value={result.graded ? `${pct}%` : "–"}
                  note={result.graded ? `${correct} of ${result.graded} · ${blank} blank` : "no answer key"}
                />
                <Stat
                  label="Reading & Writing"
                  value={rwStat.graded ? `${rwStat.correct} / ${rwStat.graded}` : "–"}
                  note={`${rwStat.total} questions`}
                />
                <Stat
                  label="Math"
                  value={mathStat.graded ? `${mathStat.correct} / ${mathStat.graded}` : "–"}
                  note={`${mathStat.total} questions`}
                />
                <Stat label="Time" value={secs !== null ? clock(secs) : "–"} note="elapsed" />
              </div>
              {wrong > 0 && (
                <div className="mt-3 border-t pt-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Wrong answers
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {result.items
                      .filter((i) => i.is_correct === false)
                      .map((i) => (
                        <button
                          key={i.question_id}
                          onClick={() => {
                            setFilter("all");
                            setSelectedId(i.question_id);
                          }}
                          className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                        >
                          Q{i.no}: {i.chosen ?? "blank"} ✗ {i.answer}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </section>

            {result.graded === 0 && (
              <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                This attempt has no answer key yet —{" "}
                <Link to={`/doc/${docId}/answers`} className="font-semibold underline">
                  enter the answers
                </Link>{" "}
                to grade it.
              </div>
            )}

            {selected ? (
              <article id="qcontent" className="mt-4 rounded-xl border bg-white p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={
                      "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold text-white " +
                      (selected.is_correct === true
                        ? "bg-emerald-600"
                        : selected.is_correct === false
                          ? "bg-red-500"
                          : "bg-slate-400")
                    }
                  >
                    {selected.is_correct === true ? "✓" : selected.is_correct === false ? "✗" : "–"}
                  </span>
                  <span className="font-semibold">Question {selected.no}</span>
                  <span className="text-sm text-slate-500">
                    {selected.sec === "math" ? "Math" : "Reading & Writing"}
                    {selected.source ? ` · ${selected.source}` : ""}
                  </span>
                  <div className="ml-auto flex items-center gap-2">
                    <button
                      onClick={() => prevQ && setSelectedId(prevQ.question_id)}
                      disabled={!prevQ}
                      aria-label="Previous question"
                      className="rounded-lg border px-3 py-1 text-sm hover:bg-slate-50 disabled:opacity-40"
                    >
                      ←
                    </button>
                    <span className="text-xs text-slate-400">
                      {vIdx >= 0 ? vIdx + 1 : 0} / {visibleItems.length}
                    </span>
                    <button
                      onClick={() => nextQ && setSelectedId(nextQ.question_id)}
                      disabled={!nextQ}
                      aria-label="Next question"
                      className="rounded-lg border px-3 py-1 text-sm hover:bg-slate-50 disabled:opacity-40"
                    >
                      →
                    </button>
                  </div>
                </div>

                {selected.material && (
                  <div className="mt-3 rounded-lg border bg-slate-50 p-3 text-sm">
                    <RichText text={selected.material} docId={docId} />
                  </div>
                )}
                <div className="mt-3 text-[15px]">
                  <RichText text={selected.stem} docId={docId} />
                </div>
                <ul className="mt-3 space-y-2">
                  {selected.options.map((option) => {
                    const letter = optionLetter(option);
                    const isAnswer = selected.answer === letter;
                    const isChosen = selected.chosen === letter;
                    const tone = isAnswer
                      ? "border-emerald-500 bg-emerald-50"
                      : isChosen
                        ? "border-red-400 bg-red-50"
                        : "border-slate-200";
                    return (
                      <li
                        key={letter}
                        className={`flex items-start gap-3 rounded-lg border px-3 py-2 text-sm ${tone}`}
                      >
                        <span className="font-semibold">{letter}</span>
                        <span className="flex-1">
                          <RichText text={option.replace(/^[A-D][.)]\s*/, "")} docId={docId} />
                        </span>
                        {isChosen && (
                          <span
                            className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
                              isAnswer ? "bg-emerald-600 text-white" : "bg-red-500 text-white"
                            }`}
                          >
                            your answer
                          </span>
                        )}
                        {isAnswer && !isChosen && (
                          <span className="shrink-0 rounded bg-emerald-600 px-1.5 py-0.5 text-xs font-medium text-white">
                            correct
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {selected.answer === null && (
                  <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                    No answer key for this question — fill it in on the{" "}
                    <Link to={`/doc/${docId}/answers`} className="underline">
                      answer page
                    </Link>
                    .
                  </p>
                )}
                {selected.is_correct === false && selected.explain && (
                  <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
                    <div className="mb-1 font-semibold text-blue-900">Explanation</div>
                    <RichText text={selected.explain} docId={docId} />
                  </div>
                )}
              </article>
            ) : (
              <p className="mt-4 rounded-xl border bg-white p-6 text-center text-sm text-slate-500">
                {filter === "wrong" ? "Nothing wrong here — nice work." : "No questions to show."}
              </p>
            )}
          </main>

          <VocabularySheet
            docId={docId}
            open={layout.sheetOpen}
            height={layout.sheetHeight}
            onToggle={() => setLayout((l) => ({ ...l, sheetOpen: !l.sheetOpen }))}
            onResize={(d) =>
              setLayout((l) => ({ ...l, sheetHeight: Math.max(SHEET_MIN, l.sheetHeight - d) }))
            }
            onMaximize={() =>
              setLayout((l) => ({
                ...l,
                sheetOpen: true,
                sheetHeight: Math.round(window.innerHeight * 0.7),
              }))
            }
            onResetHeight={() => setLayout((l) => ({ ...l, sheetHeight: 220 }))}
          />
        </div>

        {/* ---- right: Study Inspector (desktop column) ---- */}
        {isDesktop && layout.inspectorOpen && (
          <>
            <Splitter
              orientation="vertical"
              label="Resize inspector"
              onResize={(d) =>
                setLayout((l) => ({
                  ...l,
                  inspectorWidth: clamp(l.inspectorWidth - d, INSPECTOR_MIN, INSPECTOR_MAX),
                }))
              }
              onReset={() => setLayout((l) => ({ ...l, inspectorWidth: 340 }))}
            />
            <div
              data-testid="inspector-pane"
              className="flex min-h-0 shrink-0 flex-col border-l bg-white"
              style={{ width: layout.inspectorWidth }}
            >
              <Inspector
                docId={docId}
                item={selected}
                tab={layout.inspectorTab}
                onTab={(tab) => setLayout((l) => ({ ...l, inspectorTab: tab }))}
                onClose={() => setLayout((l) => ({ ...l, inspectorOpen: false }))}
                onExplainSaved={onExplainSaved}
                sessionId={sessionId}
                onReload={onReload}
              />
            </div>
          </>
        )}
      </div>

      {/* ---- mobile drawers ---- */}
      {!isDesktop && mobileNav && (
        <Drawer side="left" onClose={() => setMobileNav(false)}>
          <QuestionNav
            visible={visibleItems}
            filter={filter}
            counts={counts}
            selectedId={selectedId}
            onFilter={setFilter}
            onSelect={(qid) => {
              setSelectedId(qid);
              setMobileNav(false);
            }}
            onClose={() => setMobileNav(false)}
          />
        </Drawer>
      )}
      {!isDesktop && mobileInspector && (
        <Drawer side="right" onClose={() => setMobileInspector(false)}>
          <Inspector
            docId={docId}
            item={selected}
            tab={layout.inspectorTab}
            onTab={(tab) => setLayout((l) => ({ ...l, inspectorTab: tab }))}
            onClose={() => setMobileInspector(false)}
            onExplainSaved={onExplainSaved}
            sessionId={sessionId}
            onReload={onReload}
          />
        </Drawer>
      )}
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-bold">{value}</div>
      <div className="text-xs text-slate-500">{note}</div>
    </div>
  );
}

function Drawer({
  side,
  onClose,
  children,
}: {
  side: "left" | "right";
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/40"
      />
      <div
        className={
          "relative z-10 flex h-full w-[min(20rem,85vw)] flex-col bg-white shadow-xl " +
          (side === "left" ? "mr-auto" : "ml-auto")
        }
      >
        {children}
      </div>
    </div>
  );
}