"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { niceTicks } from "@/lib/chart-scale";
import { formatJalaliDate, formatNumber } from "@/lib/format";

/**
 * Single-series time chart for real measurements only:
 * - x is proportional to the real dates (irregular gaps stay visible),
 * - no interpolation, smoothing, trend or projection,
 * - 2px line, 8px markers with a 2px surface ring, hairline solid grid,
 * - only the latest value is labeled; hover/touch shows a crosshair + tooltip,
 * - one series per chart (never a second y-axis). A table of the same data sits beside it.
 */
export type Point = { date: string; value: number };

const SERIES = "#2a78d6"; // validated categorical slot 1 (light surface)
const GRID = "#e3e6eb";
const INK_MUTED = "#5d6573";
const INK = "#1a1d23";
const H = 220;
const PAD = { top: 20, right: 56, bottom: 28, left: 44 };

const t = (iso: string) => new Date(`${iso}T00:00:00Z`).getTime();

export function TimeLineChart({ title, unit, points }: { title: string; unit: string; points: Point[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0); // measured from the container; 0 until known
  const [hover, setHover] = useState<number | null>(null);

  const hasChart = points.length >= 2;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // The container never takes its width from the SVG (min-w-0 + overflow-hidden),
    // so measuring it cannot feed back into a wider chart.
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [hasChart]);

  const data = useMemo(() => [...points].sort((a, b) => t(a.date) - t(b.date)), [points]);
  const distinctDates = new Set(data.map((p) => p.date)).size;

  if (data.length < 2 || distinctDates < 2) {
    return (
      <figure className="flex min-w-0 flex-col gap-2">
        <figcaption className="text-sm font-semibold">{title}</figcaption>
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          {data.length === 0
            ? "هنوز اندازه‌ای ثبت نشده است."
            : "برای رسم نمودار حداقل دو اندازه‌گیری در دو تاریخ مختلف لازم است."}
        </p>
      </figure>
    );
  }

  const values = data.map((p) => p.value);
  const ticks = niceTicks(Math.min(...values), Math.max(...values));
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const x0 = t(data[0].date);
  const x1 = t(data[data.length - 1].date);
  const innerW = width - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const sx = (iso: string) => PAD.left + ((t(iso) - x0) / (x1 - x0)) * innerW;
  const sy = (v: number) => PAD.top + (1 - (v - yMin) / (yMax - yMin)) * innerH;
  const path = data.map((p, i) => `${i ? "L" : "M"}${sx(p.date).toFixed(1)},${sy(p.value).toFixed(1)}`).join(" ");
  const last = data[data.length - 1];
  const first = data[0];
  const diff = last.value - first.value;

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left + PAD.left;
    let best = 0;
    data.forEach((p, i) => {
      if (Math.abs(sx(p.date) - px) < Math.abs(sx(data[best].date) - px)) best = i;
    });
    setHover(best);
  }

  const h = hover !== null ? data[hover] : null;
  const fmt = (v: number) => `${formatNumber(v)} ${unit}`;

  return (
    <figure className="flex min-w-0 flex-col gap-2">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted-foreground">
          {formatJalaliDate(first.date)} تا {formatJalaliDate(last.date)} ·{" "}
          تغییر: <span className="ltr">{diff > 0 ? "+" : diff < 0 ? "−" : ""}{formatNumber(Math.abs(diff))}</span> {unit}
        </span>
      </figcaption>
      <div ref={ref} className="relative w-full min-w-0 overflow-hidden" dir="ltr" style={{ height: H }}>
        {width > 0 && (
        <svg width={width} height={H} role="img" aria-label={`${title}: ${data.length} اندازه‌گیری`} className="block">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={PAD.left} x2={width - PAD.right} y1={sy(v)} y2={sy(v)} stroke={GRID} strokeWidth={1} />
              <text x={PAD.left - 8} y={sy(v)} textAnchor="end" dominantBaseline="middle" fontSize={11} fill={INK_MUTED}>
                {formatNumber(v)}
              </text>
            </g>
          ))}
          <text x={PAD.left} y={H - 8} fontSize={11} fill={INK_MUTED} textAnchor="start">
            {formatJalaliDate(first.date)}
          </text>
          <text x={width - PAD.right} y={H - 8} fontSize={11} fill={INK_MUTED} textAnchor="end">
            {formatJalaliDate(last.date)}
          </text>
          {h && (
            <line x1={sx(h.date)} x2={sx(h.date)} y1={PAD.top} y2={PAD.top + innerH} stroke={INK_MUTED} strokeWidth={1} />
          )}
          <path d={path} fill="none" stroke={SERIES} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {data.map((p, i) => (
            <circle key={`${p.date}-${i}`} cx={sx(p.date)} cy={sy(p.value)} r={hover === i ? 6 : 4} fill={SERIES}
              stroke="#ffffff" strokeWidth={2} />
          ))}
          {/* Only the latest value is labeled; the rest live in the tooltip and the table */}
          <text x={sx(last.date) + 10} y={sy(last.value)} dominantBaseline="middle" fontSize={12} fontWeight={600} fill={INK}>
            {formatNumber(last.value)}
          </text>
          <rect x={PAD.left - 8} y={0} width={innerW + 16} height={H} fill="transparent"
            onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
        )}
        {h && (
          <div role="status" dir="rtl"
            className="pointer-events-none absolute z-10 rounded-md border bg-card px-2.5 py-1.5 text-xs shadow-sm"
            style={{
              left: Math.min(Math.max(sx(h.date) - 60, 0), width - 130),
              top: Math.max(sy(h.value) - 52, 0),
            }}>
            <div className="text-muted-foreground">{formatJalaliDate(h.date)}</div>
            <div className="font-semibold">{fmt(h.value)}</div>
          </div>
        )}
      </div>
    </figure>
  );
}
