import { createContext, useContext, useState, ReactNode, useCallback, useEffect } from "react";
import { Button } from "./Button";

type ToastVariant = "info" | "success" | "warning" | "danger";

interface Toast {
  id: string;
  variant: ToastVariant;
  title?: string;
  message: string;
  duration?: number;
  action?: { label: string; onClick: () => void };
}

interface ToastContextValue {
  show: (toast: Omit<Toast, "id">) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((toast: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).slice(2, 10);
    const newToast = { ...toast, id };
    setToasts((prev) => [...prev, newToast]);
    return id;
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ show, dismiss }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  const variantStyles = {
    info: "bg-primary-600 text-white",
    success: "bg-success-600 text-white",
    warning: "bg-warning-600 text-white",
    danger: "bg-danger-600 text-white",
  };

  return (
    <div
      className="fixed bottom-4 right-4 z-[800] flex flex-col gap-2 pointer-events-none"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} variantStyles={variantStyles} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({
  toast,
  variantStyles,
  onDismiss,
}: {
  toast: Toast;
  variantStyles: Record<ToastVariant, string>;
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    if (toast.duration === 0) return;
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration ?? 5000);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-xl shadow-xl min-w-[280px] max-w-md pointer-events-auto animate-slide-in ${variantStyles[toast.variant]}`}
      role="alert"
    >
      <div className="flex-1">
        {toast.title && <p className="font-semibold mb-1">{toast.title}</p>}
        <p className="text-sm opacity-90">{toast.message}</p>
        {toast.action && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 text-white hover:bg-white/20"
            onClick={() => {
              toast.action?.onClick();
              onDismiss(toast.id);
            }}
          >
            {toast.action.label}
          </Button>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-white/70 hover:text-white transition-opacity"
        aria-label="Dismiss"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}