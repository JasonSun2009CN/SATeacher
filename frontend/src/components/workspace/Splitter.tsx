import { useRef } from "react";

interface Props {
  /** "vertical" resizes left/right (a vertical bar); "horizontal" resizes up/down. */
  orientation?: "vertical" | "horizontal";
  /** Called with the pixel delta since the last event (may be negative). */
  onResize: (deltaPx: number) => void;
  /** Double-click handler — usually resets to the default size. */
  onReset?: () => void;
  label: string;
  /** Step size for keyboard arrow resizing. */
  step?: number;
}

/**
 * Accessible drag handle between workspace panes.
 *
 * `role="separator"` + `aria-orientation`, draggable via Pointer Events
 * (mouse/touch/pen), and resizable with the arrow keys. `touch-action: none`
 * keeps the browser from scrolling while dragging.
 */
export default function Splitter({
  orientation = "vertical",
  onResize,
  onReset,
  label,
  step = 16,
}: Props) {
  const dragging = useRef(false);
  const last = useRef(0);
  const vertical = orientation === "vertical";

  function position(e: { clientX: number; clientY: number }): number {
    return vertical ? e.clientX : e.clientY;
  }

  return (
    <div
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      tabIndex={0}
      data-testid={`splitter-${orientation}`}
      onPointerDown={(e) => {
        dragging.current = true;
        last.current = position(e);
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!dragging.current) return;
        const now = position(e);
        const delta = now - last.current;
        last.current = now;
        if (delta !== 0) onResize(delta);
      }}
      onPointerUp={(e) => {
        dragging.current = false;
        e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onPointerCancel={() => {
        dragging.current = false;
      }}
      onDoubleClick={() => onReset?.()}
      onKeyDown={(e) => {
        const back = vertical ? "ArrowLeft" : "ArrowUp";
        const fwd = vertical ? "ArrowRight" : "ArrowDown";
        if (e.key === back) {
          e.preventDefault();
          onResize(-step);
        } else if (e.key === fwd) {
          e.preventDefault();
          onResize(step);
        } else if (e.key === "Enter" && onReset) {
          e.preventDefault();
          onReset();
        }
      }}
      className={
        "group relative z-10 shrink-0 " +
        (vertical
          ? "w-1.5 cursor-col-resize touch-none"
          : "h-1.5 cursor-row-resize touch-none")
      }
    >
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-slate-200 transition-colors group-hover:bg-blue-400 group-focus-visible:bg-blue-500" />
    </div>
  );
}