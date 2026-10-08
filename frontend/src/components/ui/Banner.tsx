import { ReactNode } from "react";

interface Props {
  variant?: "info" | "success" | "warning" | "danger";
  title?: string;
  children: ReactNode;
  className?: string;
}

const variantStyles = {
  info: "bg-primary-50 border-primary-200 text-primary-800",
  success: "bg-success-50 border-success-200 text-success-800",
  warning: "bg-warning-50 border-warning-200 text-warning-800",
  danger: "bg-danger-50 border-danger-200 text-danger-800",
};

export function Banner({
  variant = "info",
  title,
  children,
  className = "",
}: Props) {
  return (
    <div
      className={`flex gap-3 p-4 rounded-lg border ${variantStyles[variant]} ${className}`}
      role="alert"
    >
      <div className="flex-1">
        {title && <h4 className="font-semibold mb-1">{title}</h4>}
        <div className="text-sm">{children}</div>
      </div>
    </div>
  );
}