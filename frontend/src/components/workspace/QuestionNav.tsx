import type { ResultItem } from "../../api/client";

export type Filter = "all" | "correct" | "wrong";

function statusOf(item: ResultItem): "correct" | "wrong" | "ungraded" {
  return item.is_correct === true ? "correct" : item.is_correct === false ? "wrong" : "ungraded";
}

interface Props {
  visible: ResultItem[];
  filter: Filter;
  counts: Record<"all" | "correct" | "wrong", number>;
  selectedId: number | null;
  onFilter: (filter: Filter) => void;
  onSelect: (questionId: number) => void;
  onClose?: () => void;
}

/** Left pane: filter tabs + a colour-coded question grid. */
export default function QuestionNav({
  visible,
  selectedId,
  onSelect,
}: {
  visible: import("../api/client").ResultItem[];
  selectedId: number | null;
  onSelect: (qid: number) => void;
}) {
  return null;
}