import type { SVGProps } from "react";

/**
 * Small inline icon set for the workspace shell — no icon dependency.
 * All icons share a 24px viewBox and inherit `currentColor`, so they scale
 * with the surrounding text and stay crisp at any size.
 */
type IconProps = React.SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 20, children, ...rest }: Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

type Props = {
  children: React.ReactNode;
} & React.SVGProps<SVGSVGElement>;

export function PanelRightOpenIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <rect width="18" height="18" x="3" y="3" rx="2" />
      <path d="M15 3v18" />
      <path d="m10 15-3-3 3-3" />
    </Svg>
  );
}

export function PanelRightCloseIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <rect width="18" height="18" x="3" y="3" rx="2" />
      <path d="M15 3v18" />
      <path d="m8 9 3 3-3 3" />
    </Svg>
  );
}

export function MenuIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </Svg>
  );
}

export function ChevronLeftIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <path d="m15 18-6-6 6-6" />
    </Svg>
  );
}

export function ChevronRightIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <path d="m9 18 6-6-6-6" />
    </Svg>
  );
}

export function CloseIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </Svg>
  );
}

export function ChevronDownIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <path d="m6 9 6 6 6-6" />
    </Svg>
  );
}

export function MaximizeIcon({ ...rest }: React.SVGProps<SVGSVGElement>) {
  return (
    <Svg {...rest}>
      <path d="M8 3H5a2 2 0 0 0-2 2v3" />
      <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
      <path d="M3 16v3a2 2 0 0 0 2 2h3" />
      <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
    </Svg>
  );
}