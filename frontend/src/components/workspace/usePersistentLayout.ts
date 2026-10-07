import { useCallback, useEffect, useRef, useState } from "react";

/**
 * `useState` that transparently mirrors its value into `localStorage`.
 *
 * Object defaults are merged with the stored value so a new layout field
 * added in a later release falls back to its default instead of becoming
 * `undefined`. Reads never throw (private mode / corrupt JSON → defaults).
 */
export function usePersistentState<T>(
  key: string,
  initial: T,
): [T, (updater: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => read(key, initial));

  // When the key changes (e.g. a different document), re-read from storage.
  const keyRef = useRef(key);
  useEffect(() => {
    if (keyRef.current === key) return;
    keyRef.current = key;
    setValue(read(key, initial));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const update = useCallback((updater: T | ((prev: T) => T)) => {
    setValue((prev) => {
      const next =
        typeof updater === "function" ? (updater as (p: T) => T)(prev) : updater;
      write(keyRef.current, next);
      return next;
    });
  }, []);

  return [value, update];
}

function read<T>(key: string, initial: T): T {
  if (typeof window === "undefined") return initial;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return initial;
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      !Array.isArray(parsed) &&
      initial &&
      typeof initial === "object" &&
      !Array.isArray(initial)
    ) {
      return { ...(initial as object), ...(parsed as object) } as T;
    }
    return parsed as T;
  } catch {
    return initial;
  }
}

function write<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable or full — the in-memory value is still correct */
  }
}

/** Persistent layout for the review workspace, scoped to one document. */
export interface WorkspaceLayout {
  navOpen: boolean;
  inspectorOpen: boolean;
  navWidth: number;
  inspectorWidth: number;
  sheetOpen: boolean;
  sheetHeight: number;
  inspectorTab: "explain" | "ai" | "export";
}

export const DEFAULT_LAYOUT: WorkspaceLayout = {
  navOpen: true,
  inspectorOpen: true,
  navWidth: 176,
  inspectorWidth: 340,
  sheetOpen: true,
  sheetHeight: 220,
  inspectorTab: "explain",
};

export function useWorkspaceLayout(docId: number) {
  return usePersistentState<WorkspaceLayout>(
    `sateacher.workspace.${docId}`,
    DEFAULT_LAYOUT,
  );
}