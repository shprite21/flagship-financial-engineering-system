import assert from 'node:assert/strict';
import { test } from 'node:test';
import { summarize } from './paper-receipt.mjs';

const snapshot = {
  source: 'alpaca_paper', simulated: true, liveOrderSubmission: false,
  receivedAt: '2025-01-06T16:00:00Z',
  orders: [
    { id: 'private-full-id', status: 'filled', side: 'buy', filled_qty: '1', filled_avg_price: '100',
      submitted_at: '2025-01-06T14:31:00Z', filled_at: '2025-01-06T14:31:01Z' },
    { id: 'private-part-id', status: 'canceled', side: 'sell', qty: '1', filled_qty: '0.5',
      filled_avg_price: '101', submitted_at: '2025-01-06T14:31:00Z' },
    { id: 'private-open-id', status: 'new', filled_qty: '0' },
  ],
};

test('counts orders with executed quantity and withholds raw identifiers', () => {
  const receipt = summarize(snapshot);
  assert.equal(receipt.fully_filled_orders, 1);
  assert.equal(receipt.other_orders_with_executed_quantity, 1);
  assert.equal(receipt.last_completed_order_utc_date_in_sample, '2025-01-06');
  assert.doesNotMatch(JSON.stringify(receipt), /private-|filled_avg_price/);
  assert.equal(summarize({ ...snapshot, orders: [] }).first_completed_order_utc_date_in_sample, null);
});

test('rejects inconsistent order records, synthetic sources and duplicated order rows', () => {
  for (const overrides of [{ filled_at: '2025-02-01T00:00:00Z' }, { filled_qty: '0' },
    { filled_avg_price: null }, { qty: '.5' }, { qty: '2' }, { status: '' },
    { submitted_at: '2025-01-06T14:31:00' }]) {
    assert.throws(() => summarize({ ...snapshot, orders: [{ ...snapshot.orders[0], ...overrides }] }));
  }
  assert.throws(() => summarize({ ...snapshot, source: 'synthetic' }));
  assert.throws(() => summarize({ ...snapshot, orders: [snapshot.orders[0], snapshot.orders[0]] }));
  assert.throws(() => summarize({
    ...snapshot, orders: [{ ...snapshot.orders[1], submitted_at: '2025-01-07T14:31:00Z' }],
  }));
});
