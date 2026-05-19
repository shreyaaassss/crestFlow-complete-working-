import { SVGProps } from "react";

export function Logo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Sleek letter 'C' (Crest) */}
      <path
        d="M17 6a9 9 0 1 0 0 12"
        stroke="var(--ink)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Rising trendline chart peak (Flow) */}
      <path
        d="M7 15l3-3 2.5 2.5L18 8"
        stroke="var(--link)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Peak dot */}
      <circle cx="18" cy="8" r="2" fill="var(--link)" />
    </svg>
  );
}
