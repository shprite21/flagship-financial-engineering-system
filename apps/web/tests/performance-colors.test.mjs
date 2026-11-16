import test from 'node:test';
import assert from 'node:assert/strict';
import { performanceTone } from '../lib/performance-colors.ts';

test('P&L and return colors use numeric sign, with unavailable and zero neutral', () => {
  for (const key of ['pnl', 'Realized P&L', 'unrealized_profit', 'total_return', 'drawdown']) {
    assert.equal(performanceTone(key, 1), 'positive');
    assert.equal(performanceTone(key, -1), 'negative');
    for (const value of [0, -0, null, undefined, NaN, Infinity, '—']) assert.equal(performanceTone(key, value), undefined);
  }
  for (const key of ['skew', 'cash', 'weight', 'price']) assert.equal(performanceTone(key, -1), undefined);
});
