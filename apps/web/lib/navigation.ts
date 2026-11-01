/** Only allow same-site relative redirects after login (prevents open redirect). */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/dashboard";
  if (next.startsWith("/login")) return "/dashboard";
  return next;
}
