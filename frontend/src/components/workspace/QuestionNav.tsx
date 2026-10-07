import type { ResultItem } from "../../api/client";

export type Filter = "all" | "correct" | "wrong";

function statusOf(item: ResultItem): "correct" | "wrong" | "ungraded" {
  return item.is_correct === true ? "correct" : item.is_correct === false ? "wrong" : "ungraded";
}

interface Props {
  visible: ResultItem[];
  filter: Filter;
  counts: Record<Filter, number>;
  selectedId: number | null;
  onFilter: (filter: Filter) => void;
  onSelect: (questionId: number) => void;
  onClose?: () => void;
}

/** Left pane: filter segmented control + a colour-coded question grid. */
export default function QuestionNav({
  visible,
  filter,
  counts,
  selectedId,
  onFilter,
  onSelect,
  onClose,
}: Props) {
  const tabs: { key: Filter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "correct", label: "Correct" },
    { key: "wrong", label: "Wrong" },
  ];

  return (
    <div id="qindex" className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between px-2 pt-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Questions
        </span>
        <span className="flex items-center gap-1">
          <span className="text-xs text-slate-400">{visible.length}</span>
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close question list"
              className="rounded-md px-1.5 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 lg:hidden"
            >
              ✕
            </button>
          )}
        </span>
      </div>

      <div className="mx-2 mt-2 flex gap-0.5 rounded-lg bg-slate-100 p-0.5" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={filter === tab.key}
            onClick={() => onFilter(tab.key)}
            title={`${tab.label} (${counts[tab.key]})`}
            className={`flex-1 rounded-md px-1.5 py-1 text-xs font-medium transition ${
              filter === tab.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {visible.length === 0 ? (
          <p className="px-1 py-2 text-xs text-slate-400">Nothing to show.</p>
        ) : (
          <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-10 lg:grid-cols-4">
            {visible.map((item) => {
              const status = statusOf(item);
              return (
                <button
                  key={item.question_id}
                  id={`qn-${item.question_id}`}
                  data-no={item.no}
                  data-status={status}
                  aria-label={`Question ${item.no} — ${status === "ungraded" ? "no answer key" : status}`}
                  aria-current={selectedId === item.question_id ? "true" : undefined}
                  title={`Question ${item.no}`}
                  onClick={() => onSelect(item.question_id)}
                  className={
                    "aspect-square rounded-md border text-sm font-medium transition-colors " +
                    (status === "correct"
                      ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                      : status === "wrong"
                        ? "border-red-300 bg-red-50 text-red-800 hover:bg-red-100"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-100") +
                    (selectedId === item.question_id ? " ring-2 ring-blue-500" : "")
                  }
                >
                  {item.no}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}