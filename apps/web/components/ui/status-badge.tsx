type Props = { ok: boolean | null; label: string };

/** Status shown with text + icon shape, not color alone. */
export function StatusBadge({ ok, label }: Props) {
  const state = ok === null ? "در حال بررسی" : ok ? "برقرار" : "قطع";
  const symbol = ok === null ? "…" : ok ? "✓" : "✕";
  const tone =
    ok === null ? "text-muted border-border" : ok ? "text-success border-success/40" : "text-danger border-danger/40";
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm ${tone}`}>
      <span aria-hidden>{symbol}</span>
      {label}: {state}
    </span>
  );
}
