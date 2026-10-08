import { ReactNode } from "react";
import { Button } from "./Button";

interface Props {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: {
    label: string;
    onClick: () => void;
    variant?: "primary" | "secondary";
  };
  className?: string;
}

export function EmptyState({ icon, title, description, action, className = "" }: Props) {
  return (
    <div className={`flex flex-col items-center text-center py-12 px-4 ${className}`}>
      {icon && <div className="mb-4 text-slate-300" aria-hidden="true">{icon}</div>}
      <h3 className="text-lg font-semibold text-slate-900 mb-1">{title}</h3>
      {description && <p className="text-slate-500 max-w-sm mx-auto mb-6">{description}</p>}
      {action && (
        <Button variant={action.variant || "primary"} onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}