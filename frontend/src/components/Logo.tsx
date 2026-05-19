import { SVGProps } from "react";

export function Logo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <defs>
        <linearGradient id="flowGradient" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="var(--link)" />
          <stop offset="100%" stopColor="oklch(0.7 0.15 255)" />
        </linearGradient>
      </defs>
      
      {/* Sleek, dynamic letter 'C' */}
      <path
        d="M17.5 5.5A9.5 9.5 0 1 0 17.5 18.5"
        stroke="var(--ink)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      
      {/* Sharp, vibrant rising trendline */}
      <path
        d="M6 16l3.5-4 2.5 2.5L18.5 7.5"
        stroke="url(#flowGradient)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Peak highlight dot */}
      <circle cx="18.5" cy="7.5" r="2.5" fill="url(#flowGradient)" />
    </svg>
  );
}
