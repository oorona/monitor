import type { CSSProperties } from "react";
const paths: Record<string, string> = {
  pulse: "M3 12h4l3-8 4 16 3-8h4",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  arrow: "M5 12h14m-6-6 6 6-6 6",
  clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  database:
    "M3 6c0-5 18-5 18 0s-18 5-18 0v12c0 5 18 5 18 0V6M3 12c0 5 18 5 18 0",
  workflow: "M9 3h6v6H9zM2 16h6v6H2zM16 16h6v6h-6zM12 9v4M5 16v-3h14v3",
  settings: "M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6",
  check: "M5 12l4 4L19 6",
  alert: "M12 3 2 21h20L12 3zM12 9v5m0 3v1",
  star: "m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z",
  folder: "M3 7V4h7l2 3h9v14H3z",
  close: "m6 6 12 12M6 18 18 6",
  chevron: "m9 5 7 7-7 7",
};
export function Icon({
  name,
  size = 18,
  className = "",
  style,
}: {
  name: string;
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      style={style}
    >
      <path d={paths[name] || paths.grid} />
    </svg>
  );
}
