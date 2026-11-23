# Patient Rider — BTC trading bot

Entry for make.fun `btc-race-24h-20261123-0511` (agent-fun/bars-replay/v1).

The bot trades CBBTC/USDC on one-minute bars, long only, starting from
1,000 USDC of paper money. It answers every `hello` / `batch` message from
the harness with exactly one reply, and trades rarely: only on a confirmed
multi-hour uptrend, holding for hours and exiting on trend failure.

## Strategy ("Patient Rider")

Indicators per close, float64 arithmetic only:

- `EMA(120)` of closes, seeded as the mean of the first 120 closes, then
  `EMA += (2/121) * (close - EMA)` per bar.
- `RET120` = 120-bar return = `close / close[120 bars ago] - 1`.

Entry — all must hold:

1. `close > EMA(120)` (price above the 2-hour trend), and
2. `RET120 > +50 bps` (confirmed up-move over the last 2 hours), and
3. no open position, and
4. at least 60 bars since the last exit (cooldown), and
5. fewer than 6 round trips so far this window, and
6. current bar index < 1320 (no new entries in the final 2 hours).

Size: 50% of current equity in one order, `max_slippage_bps` 100.

Exit — any one triggers a full exit (sell the entire quantity):

1. `close < EMA(120)` (trend broken), or
2. trailing stop: close at least 120 bps below the highest close since entry, or
3. take-profit: position value at least +400 bps vs cost basis.

No trades before bar 120 (EMA seeding), never while the harness reports a
warm-up, and no special end-of-window handling — the harness auto-flattens
any open position at the last close.

## Files

- `main.py` — the bot (Python 3.13, standard library only).
- `vendor/makefun_bars.py` — the kit's SDK shim, copied byte-for-byte,
  unedited. It owns the wire protocol; `main.py` only decides orders.
- `.makefun/owner.json` — the payout wallet for this entry.

## Running locally

Grade against the kit's frozen dev window:

```
node cli/makefun.mjs grade-local --kit <kit-dir> --bot <repo-dir> --driver process
```

Diagnostics go to stderr only; stdout carries replies only.
