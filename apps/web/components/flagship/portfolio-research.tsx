'use client';

import './research-layout.css';
import { lazy, Suspense } from 'react';

const StrategyResearch = lazy(() => import('./research-workspace'));

export default function PortfolioResearch() {
  return (
    <section className="portfolio-research min-w-0" aria-labelledby="portfolio-research-title">
      <Suspense fallback={<div className="empty">Loading research workspace…</div>}>
        <StrategyResearch />
      </Suspense>
    </section>
  );
}
