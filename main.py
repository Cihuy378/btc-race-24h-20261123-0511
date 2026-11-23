"""Patient Rider — a BTC trading bot for make.fun btc-race-24h-20261123-0511.

Protocol: agent-fun/bars-replay/v1. The harness sends one ``hello`` message,
then one ``batch`` per minute (1,440 bars), then ``done``. This bot answers
every batch with exactly one reply echoing its seq, carrying zero or one
orders. All diagnostics go to stderr; stdout carries replies only.

Strategy (trend-following, 50% size, long only):

* EMA(120) of closes, seeded as the mean of the first 120 closes, then
  EMA += (2/121) * (close - EMA) on every bar after that.
* RET120 = close / close[120 bars ago] - 1.

Enter when ALL hold: close above EMA(120), RET120 above +70 bps (A1: a
70 bp confirmation bar instead of 50 bp, after the primary 50 bp bar
scored below zero on this race's dev window), no open position, at least
60 bars since the last exit, fewer than 6 round trips so far, and the
current bar index below 1320. One buy of 50% of equity,
max_slippage_bps 100.

Exit the whole position when ANY holds: close below EMA(120); close at
least 120 bps below the highest close since entry (trailing stop); or the
position value at least +400 bps above its cost basis (take-profit).

No trades before bar 120 (the EMA needs its seed), never while the harness
reports a warm-up, and no new entries in the final two hours. The harness
auto-flattens anything still held at the last close.

Determinism: float64 arithmetic (+ - * /) only. No wall clock, no network,
no environment reads, no unseeded randomness. Standard library only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

EMA_PERIOD = 120
EMA_ALPHA_NUM = 2.0
EMA_ALPHA_DEN = 121.0
ENTRY_RET_BPS = 70
# A1 fallback (STRATEGY.md section 4): a 70 bp confirmation bar instead of
# 50 bp, for fewer, higher-conviction entries. The primary 50 bp bar scored
# below zero on this race's dev window, so this revision tries 70 bp.
COOLDOWN_BARS = 60
MAX_ROUND_TRIPS = 6
LAST_ENTRY_BAR = 1320
SIZE_BPS = 5000
MIN_NOTIONAL_UNITS = 1000000
MAX_SLIPPAGE_BPS = 100
TRAIL_BPS = 120
TAKE_PROFIT_BPS = 400
BPS_DEN = 10000.0


def _log(message):
    print(message, file=sys.stderr, flush=True)


class Rider:
    """The strategy state. One instance lives for the whole run."""

    def __init__(self):
        self.closes = []
        self.ema = None
        self.in_position = False
        self.entry_high = None
        self.last_exit_bar = -1000000
        self.round_trips = 0
        self.pending_buy_bar = None

    def _bar_index(self):
        return len(self.closes) - 1

    def _note_fill(self, state, close):
        """Sync position tracking with the account the harness reports."""
        holding = state.positions.get(SYMBOL)
        if holding is not None and not self.in_position:
            self.in_position = True
            self.entry_high = close
            self.pending_buy_bar = None
            _log("entered position: bar %d close %d qty %d cost %d"
                 % (self._bar_index(), close, holding.qty, holding.cost))
        elif holding is not None and self.in_position:
            if close > self.entry_high:
                self.entry_high = close
        elif holding is None and self.in_position:
            self.in_position = False
            self.entry_high = None
            self.last_exit_bar = self._bar_index()
            self.round_trips += 1
            _log("exited position: bar %d round trips %d"
                 % (self._bar_index(), self.round_trips))

    def _maybe_exit(self, state, close):
        """Return a full-exit sell order if any exit rule fires, else None."""
        holding = state.positions.get(SYMBOL)
        if holding is None:
            return None
        reason = None
        if close < self.ema:
            reason = "below-ema"
        elif close < self.entry_high * (1.0 - TRAIL_BPS / BPS_DEN):
            reason = "trailing-stop"
        elif state.value(SYMBOL, holding.qty) >= holding.cost * (1.0 + TAKE_PROFIT_BPS / BPS_DEN):
            reason = "take-profit"
        if reason is None:
            return None
        _log("exit %s: bar %d close %d ema %.2f high %d"
             % (reason, self._bar_index(), close, self.ema, self.entry_high))
        return {"side": "sell", "symbol": SYMBOL, "qty": holding.qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS}

    def _maybe_enter(self, state, close):
        """Return a 50%-of-equity buy order if every entry rule holds."""
        if self.in_position:
            return None
        if self.pending_buy_bar is not None:
            return None
        bar_index = self._bar_index()
        if bar_index >= LAST_ENTRY_BAR:
            return None
        if bar_index - self.last_exit_bar < COOLDOWN_BARS:
            return None
        if self.round_trips >= MAX_ROUND_TRIPS:
            return None
        if close <= self.ema:
            return None
        ret120 = close / self.closes[bar_index - EMA_PERIOD] - 1.0
        if ret120 <= ENTRY_RET_BPS / BPS_DEN:
            return None
        notional = state.equity * SIZE_BPS // 10000
        if notional > state.cash:
            notional = state.cash
        if notional < MIN_NOTIONAL_UNITS:
            return None
        _log("entry: bar %d close %d ema %.2f ret120 %.5f notional %d"
             % (bar_index, close, self.ema, ret120, notional))
        self.pending_buy_bar = bar_index
        return {"side": "buy", "symbol": SYMBOL,
                "notional_quote_units": notional,
                "max_slippage_bps": MAX_SLIPPAGE_BPS}

    def on_batch(self, state, batch):
        """Decide the orders for one batch. Returns a list (possibly empty)."""
        bar = None
        for candidate in batch.get("bars", []):
            if candidate.get("symbol") == SYMBOL:
                bar = candidate
                break
        if bar is None:
            return []
        close = int(bar["c"])
        self.closes.append(close)
        if len(self.closes) == EMA_PERIOD:
            total = 0.0
            for value in self.closes:
                total += value
            self.ema = total / EMA_PERIOD
        elif len(self.closes) > EMA_PERIOD:
            self.ema += (EMA_ALPHA_NUM / EMA_ALPHA_DEN) * (close - self.ema)
        if state.warming_up:
            return []
        if self.ema is None or len(self.closes) <= EMA_PERIOD:
            return []
        if self.pending_buy_bar is not None and self._bar_index() - self.pending_buy_bar > 1:
            self.pending_buy_bar = None
        self._note_fill(state, close)
        exit_order = self._maybe_exit(state, close)
        if exit_order is not None:
            return [exit_order]
        enter_order = self._maybe_enter(state, close)
        if enter_order is not None:
            return [enter_order]
        return []


RIDER = Rider()


def on_batch(state, batch):
    return RIDER.on_batch(state, batch)


makefun_bars.run(on_batch)
