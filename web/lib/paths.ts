const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function path(p: string): string {
  if (!p.startsWith("/")) return p;
  return `${BASE}${p}`;
}
