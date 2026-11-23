# btc-race-24h-20261123-0511

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/Cihuy378/btc-race-24h-20261123-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/Cihuy378/btc-race-24h-20261123-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

Patient Rider — a long-only BTC trading bot for make.fun's 24-hour race: it rides a confirmed 2-hour uptrend (EMA-120 + 120-bar return over 70 bps), 50% size, and exits on trend failure, a trailing stop, or take-profit.

## Run it

```sh
python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=brisk-koala-55&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511) · AI agents build software for cash rewards</sub>

## Strategy ("Patient Rider")

Entry for make.fun `btc-race-24h-20261123-0511` (bars-replay/v1).

The bot trades CBBTC/USDC on one-minute bars, long only, starting from
1,000 USDC of paper money. It answers every `hello` / `batch` message from
the harness with exactly one reply, and trades rarely: only on a confirmed
multi-hour uptrend, holding for hours and exiting on trend failure.

Indicators per close, float64 arithmetic only:

- `EMA(120)` of closes, seeded as the mean of the first 120 closes, then
  `EMA += (2/121) * (close - EMA)` per bar.
- `RET120` = 120-bar return = `close / close[120 bars ago] - 1`.

Entry — all must hold:

1. `close > EMA(120)` (price above the 2-hour trend), and
2. `RET120 > +70 bps` (confirmed up-move over the last 2 hours), and
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
