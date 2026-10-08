import { useRef, useEffect } from "react";

interface Tab {
  key: string;
  label: string;
  disabled?: boolean;
}

interface Props {
  tabs: Tab[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
  variant?: "line" | "enclosed" | "soft";
}

export function Tabs({ tabs, activeKey, onChange, className = "", variant = "line" }: Props) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    const idx = tabs.findIndex((t) => t.key === activeKey);
    if (idx >= 0) {
      tabRefs.current[idx]?.focus();
    }
  }, [activeKey, tabs]);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = index;
    if (e.key === "ArrowRight") {
      nextIndex = (index + 1) % tabs.length;
    } else if (e.key === "ArrowLeft") {
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    } else if (e.key === "Home") {
      nextIndex = 0;
    } else if (e.key === "End") {
      nextIndex = tabs.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    const nextTab = tabs[nextIndex];
    if (!nextTab.disabled) {
      onChange(nextTab.key);
      tabRefs.current[nextIndex]?.focus();
    }
  };

  const baseTab = "flex-1 px-4 py-2.5 text-sm font-medium text-center transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2";

  const variants = {
    line: "border-b-2 border-transparent text-slate-500 hover:text-slate-700 data-[active]:border-primary-600 data-[active]:text-primary-600",
    enclosed: "rounded-lg text-slate-500 hover:bg-slate-100 data-[active]:bg-primary-50 data-[active]:text-primary-700",
    soft: "rounded-lg text-slate-500 hover:bg-slate-100 data-[active]:bg-primary-100 data-[active]:text-primary-700",
  };

  return (
    <div className={`flex gap-1 ${className}`} role="tablist" aria-label="Tabs">
      {tabs.map((tab, index) => (
        <button
          ref={(el) => { tabRefs.current[index] = el; }}
          key={tab.key}
          role="tab"
          aria-selected={tab.key === activeKey}
          aria-controls={`${tab.key}-panel`}
          id={`${tab.key}-tab`}
          disabled={tab.disabled}
          onClick={() => !tab.disabled && onChange(tab.key)}
          onKeyDown={(e) => handleKeyDown(e, index)}
          className={`${baseTab} ${variants[variant]} ${tab.disabled ? "opacity-40 cursor-not-allowed" : ""}`}
          data-active={tab.key === activeKey}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}