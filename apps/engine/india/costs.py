"""Versioned resident retail NSE equity fees; amounts are INR, rates are fractions.

Groww pricing verified 2026-10-17. Conservative whole-rupee STT rounding per leg;
contract-note aggregation can differ. Slippage includes spread, impact and latency.
"""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class Costs:
    version: str = 'groww-resident-nse-2026-10-17'
    brokerage_rate: float = .001
    brokerage_min: float = 5.
    brokerage_max: float = 20.
    exchange: float = .0000297
    sebi: float = .000001
    ipft: float = .000001
    gst: float = .18
    slippage_bps: float = 10.  # per side: 5 spread + 2 impact + 3 manual latency
    rounding_buffer: float = .10

    def leg(self, value, side, product='intraday'):
        if not math.isfinite(value) or value <= 0 or side not in ('buy', 'sell') or product not in ('intraday', 'delivery'):
            raise ValueError('Positive finite turnover, valid side and equity product required')
        brokerage = min(value*.025, self.brokerage_max, max(self.brokerage_min, value*self.brokerage_rate))
        exchange, sebi, ipft = (value*r for r in (self.exchange, self.sebi, self.ipft))
        stt_rate = .001 if product == 'delivery' else (.00025 if side == 'sell' else 0.)
        stt = math.ceil(value*stt_rate) if stt_rate else 0.
        stamp = value*(.00015 if product == 'delivery' else .00003) if side == 'buy' else 0.
        dp = (20. if value>=100 else 3.5) if product == 'delivery' and side == 'sell' else 0.  # conservative male rate
        gst = (brokerage+exchange+sebi+ipft+dp)*self.gst
        result = dict(brokerage=brokerage, exchange=exchange, sebi=sebi, ipft=ipft,
                      stt=stt, stamp=stamp, dp=dp, gst=gst, rounding=self.rounding_buffer)
        result['total'] = round(sum(result.values()), 4)
        return result

    def roundtrip(self, quantity, entry, exit_price, product='intraday'):
        if type(quantity) is not int or quantity <= 0:
            raise ValueError('Positive whole shares required')
        return self.leg(quantity*entry, 'buy', product)['total'] + self.leg(quantity*exit_price, 'sell', product)['total']

    def snapshot(self):
        return asdict(self)


def size_trade(entry, stop, cash=5000., risk=50., costs=None, product='intraday'):
    costs = costs or Costs()
    if not all(math.isfinite(v) for v in (entry, stop, cash, risk)) or not 0 < stop < entry or cash <= 0 or risk <= 0:
        return {'quantity': 0, 'reason': 'Invalid price, cash or remaining loss budget'}
    exit_stress = stop*(1-costs.slippage_bps/10000)
    # Entry is an executable limit, inclusive of entry spread/slippage allowance.
    for quantity in range(min(10000, int(cash/entry)), 0, -1):
        reserve = quantity*entry + costs.leg(quantity*entry, 'buy', product)['total']
        loss = quantity*(entry-exit_stress) + costs.roundtrip(quantity, entry, exit_stress, product)
        if reserve <= cash and loss <= risk:
            return {'quantity': quantity, 'reserved_cash': round(reserve, 4), 'planned_loss': round(loss, 4),
                    'estimated_fees': round(costs.roundtrip(quantity, entry, exit_stress, product), 4),
                    'stop_fill_assumption': exit_stress, 'reason': 'Within planned limits; gaps can exceed them'}
    return {'quantity': 0, 'reason': 'Whole-share cash or all-in planned loss constraint'}
