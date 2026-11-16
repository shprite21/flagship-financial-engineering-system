// Read-only report of completed orders visible in an authenticated paper account.
import { pathToFileURL } from 'node:url';
import { AlpacaPaperAdapter } from '../../apps/gateway/alpaca-paper.mjs';

function timestamp(value) {
  if (typeof value !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(value)) {
    throw new Error('Paper order is missing a timezone-qualified timestamp.');
  }
  const instant = Date.parse(value);
  if (!Number.isFinite(instant)) throw new Error('Invalid paper order timestamp.');
  return instant;
}

function quantity(value) {
  if (!['string', 'number'].includes(typeof value) || String(value).trim() === '') {
    throw new Error('Missing paper order quantity or price.');
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) throw new Error('Invalid paper order quantity or price.');
  return numeric;
}

export function summarize(snapshot) {
  if (snapshot.source !== 'alpaca_paper' || snapshot.simulated !== true ||
      snapshot.liveOrderSubmission !== false || !Array.isArray(snapshot.orders) ||
      snapshot.orders.length > 100) {
    throw new Error('Expected the paper adapter snapshot for up to 100 recent orders.');
  }
  const received = timestamp(snapshot.receivedAt);
  const ids = new Set();
  const dates = [];
  let otherOrdersWithExecutions = 0;
  for (const order of snapshot.orders) {
    if (typeof order.id !== 'string' || !order.id || ids.has(order.id)) {
      throw new Error('A paper order has a missing or duplicated identifier.');
    }
    ids.add(order.id);
    const filled = quantity(order.filled_qty);
    if (typeof order.status !== 'string' || !order.status.trim()) {
      throw new Error('Paper order is missing its execution status.');
    }
    if (order.status === 'filled' && !filled) throw new Error('Filled order has zero executed quantity.');
    if (!filled) continue;
    // Notional orders may omit the requested share quantity.
    if (order.qty != null) {
      const requested = quantity(order.qty);
      if (filled > requested || (order.status === 'filled' && filled !== requested)) {
        throw new Error('Executed quantity disagrees with the order quantity.');
      }
    }
    if (quantity(order.filled_avg_price) <= 0 || !['buy', 'sell'].includes(order.side)) {
      throw new Error('Executed paper quantity lacks a positive price or a valid side.');
    }
    const submitted = timestamp(order.submitted_at);
    if (submitted > received) throw new Error('Order submission is later than the snapshot.');
    // Alpaca can retain nonzero executed quantity on partially filled or
    // subsequently cancelled orders. Their last execution time is unknown here.
    if (order.status !== 'filled') {
      otherOrdersWithExecutions++;
      continue;
    }
    const completed = timestamp(order.filled_at);
    if (completed < submitted || completed > received) throw new Error('Inconsistent paper order timestamps.');
    dates.push(new Date(completed).toISOString().slice(0, 10));
  }
  dates.sort();
  return {
    schema: 1,
    source: 'Alpaca paper API via authenticated read-only adapter',
    received_at: new Date(received).toISOString(),
    scope: 'Latest 100 account orders, including orders from other strategies or manual trading',
    orders_examined: ids.size,
    fully_filled_orders: dates.length,
    other_orders_with_executed_quantity: otherOrdersWithExecutions,
    first_completed_order_utc_date_in_sample: dates[0] ?? null,
    last_completed_order_utc_date_in_sample: dates.at(-1) ?? null,
    strategy_attribution: 'unverified',
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const adapter = new AlpacaPaperAdapter();
    await adapter.connect({});
    const snapshot = await adapter.snapshot();
    process.stdout.write(JSON.stringify(summarize(snapshot), null, 2) + '\n');
  } catch (error) {
    process.stderr.write(error.message + '\n');
    process.exitCode = 1;
  }
}
