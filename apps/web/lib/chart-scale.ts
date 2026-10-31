/** Round axis ticks covering [min, max] (1/2/2.5/5 × 10^n steps). */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) {
    const d = Math.abs(min) * 0.05 || 1;
    min -= d;
    max += d;
  }
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const start = Math.floor(min / step) * step;
  const ticks = [Number(start.toFixed(6))];
  // keep adding steps until the top tick reaches the maximum (never cut off data)
  while (ticks[ticks.length - 1] < max) ticks.push(Number((ticks[ticks.length - 1] + step).toFixed(6)));
  if (ticks.length === 1) ticks.push(Number((start + step).toFixed(6)));
  return ticks;
}
