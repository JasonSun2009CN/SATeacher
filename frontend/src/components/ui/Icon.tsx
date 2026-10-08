import * as LucideIcons from "lucide-react";

/**
 * Type-safe icon wrapper. Usage:
 *   import { Icon, Home, Settings } from "@/components/ui/Icon";
 *   <Icon icon={Home} size={20} />
 *   <Icon icon="home" size={20} />  // also works with string key
 */
type IconName = keyof typeof LucideIcons;

interface Props {
  icon: LucideIcons.LucideIcon | IconName;
  size?: number;
  className?: string;
  "aria-label"?: string;
}

export function Icon({ icon, size = 20, className = "", "aria-label": ariaLabel }: Props) {
  const Component = typeof icon === "string"
    ? (LucideIcons as unknown as Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>>)[icon]
    : icon;
  if (!Component) {
    console.warn(`Icon "${icon}" not found in lucide-react`);
    return null;
  }
  return (
    <Component
      size={size}
      className={className}
      aria-hidden={!ariaLabel}
      aria-label={ariaLabel}
      strokeWidth={2}
    />
  );
}

// Re-export all lucide icons for convenient importing
export * from "lucide-react";