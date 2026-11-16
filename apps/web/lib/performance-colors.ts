/** Display-only sign styling. Zero and unavailable values remain neutral. */
const comparisonColors = ['#60a5fa', '#f5f5f5', '#a78bfa', '#fbbf24', '#22d3ee', '#f472b6', '#fb923c', '#818cf8', '#a3e635'];

/** Comparison curves keep their identity color regardless of return sign. */
export function comparisonColor(index: number) {
  return comparisonColors[index] ?? `hsl(${(index * 137.508) % 360} 70% 68%)`;
}

export function isPerformanceValue(key: string, context = '') {
  return /pnl|p&l|profit|realized|return|drawdown/i.test(key)
    || (/attribution|regime_performance/i.test(context)
      && ['momentum', 'mean_reversion', 'statistical_arbitrage'].includes(key));
}

export function performanceTone(key: string, value: unknown, context = '') {
  if (!isPerformanceValue(key, context) || typeof value !== 'number' || !Number.isFinite(value) || value === 0) return undefined;
  return value > 0 ? 'positive' : 'negative';
}
