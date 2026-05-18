import { SVGProps } from "react";

export function Logo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        d="M19 8L12 4L5 8v8l7 4 7-4"
        stroke="var(--ink)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M3 12c3-3 6-3 9 0s6 3 9 0"
        stroke="var(--link)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
