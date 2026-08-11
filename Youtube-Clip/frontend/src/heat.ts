// Map a normalized intensity (0..1) onto the heat spectrum: cool -> warm -> hot -> peak.
const STOPS: [number, [number, number, number]][] = [
  [0.0, [59, 130, 246]], // cool blue
  [0.45, [168, 85, 247]], // warm violet
  [0.75, [244, 63, 94]], // hot red
  [1.0, [251, 191, 36]], // peak amber
];

export function heatColor(score: number): string {
  const t = Math.min(1, Math.max(0, score));
  for (let i = 1; i < STOPS.length; i++) {
    const [p1, c1] = STOPS[i - 1];
    const [p2, c2] = STOPS[i];
    if (t <= p2) {
      const f = (t - p1) / (p2 - p1 || 1);
      const c = c1.map((v, k) => Math.round(v + (c2[k] - v) * f));
      return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
    }
  }
  return "rgb(251, 191, 36)";
}
