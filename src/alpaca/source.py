"""Alpaca, as the lake's half of the plugin asks it (lake.Source).

Daily bars from SIP's consolidated history, past a free account's
restricted 15 minutes; live prices, quotes and a range of trades from SIP
where the key has it in real time, else from IEX, the one exchange a free
account sees, each row naming the exchange it is from. Which feeds the key
is entitled to is asked once, and again when the key changes; the
Connection page shows the answer. Should SIP refuse a live call the key was
taken to have (403), the key is taken not to have SIP in real time from then
on, and the call asked again of IEX: latest quotes and trades come from the
feed the key is entitled to, never SIP's on a free or a paper key.

A symbol Alpaca cannot take at all (a fund's code such as TCH4) it answers
with a 400 for the whole call, naming it: "invalid symbol: TCH4". That is
definitive: the symbol is kept as invalid, the call asked again without it,
and it is never asked of Alpaca again while the plugin runs; the lake
declines its subjects as not covered.
"""

from __future__ import annotations

import datetime as dt
import re
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import TypeVar

from . import convert
from .convert import DailyBar, Quoted, SourceQuote, SourceTrade
from .vendor import IEX, SIP, SYMBOLS_PER_CALL, Alpaca, Entitlements, VendorError

T = TypeVar("T")

#: Alpaca's answer to a symbol it cannot take, for the whole call (a 400).
INVALID_SYMBOL = re.compile(r"invalid symbol:\s*(\S+)", re.IGNORECASE)


def invalid_symbol(refused: VendorError, asked: Sequence[str]) -> str | None:
    """The symbol of `asked` that a 400 names as invalid, or None where it
    is another refusal or names none of them."""
    if refused.status != 400:
        return None
    found = INVALID_SYMBOL.search(refused.detail)
    if found is None:
        return None
    named = found.group(1).strip(",.;\"'").upper()
    return next((s for s in asked if s.upper() == named), None)


class AlpacaSource:
    """lake.Source on Alpaca's Market Data API."""

    def __init__(self, alpaca: Alpaca, synthetic: bool = False) -> None:
        self.alpaca = alpaca
        self.synthetic = synthetic
        self._entitled: Entitlements | None = None
        self._lock = threading.Lock()
        #: The symbols Alpaca answered are invalid: never asked again.
        self.invalid: set[str] = set()

    def entitlements(self, again: bool = False) -> Entitlements:
        """The feeds the key answered for, asked once (synthetic: IEX and SIP's
        history, as a free account has)."""
        with self._lock:
            if self._entitled is None or again:
                if self.synthetic:
                    self._entitled = Entitlements(answered=True, iex=True, sip_history=True)
                else:
                    self._entitled = self.alpaca.entitlements()
            return self._entitled

    @property
    def known(self) -> Entitlements | None:
        return self._entitled

    def _each_call(self, symbols: Sequence[str], ask: Callable[[list[str]], list[T]]) -> list[T]:
        """`ask` of `symbols`, a call's worth at a time, leaving out those
        Alpaca answered are invalid. A call refused for one of its symbols
        (400, "invalid symbol: X") keeps it as invalid and is asked again
        without it."""
        out: list[T] = []
        valid = [s for s in symbols if s not in self.invalid]
        for start in range(0, len(valid), SYMBOLS_PER_CALL):
            chunk = valid[start : start + SYMBOLS_PER_CALL]
            while chunk:
                try:
                    out.extend(ask(chunk))
                    break
                except VendorError as refused:
                    named = invalid_symbol(refused, chunk)
                    if named is None:
                        raise
                    with self._lock:
                        self.invalid.add(named)
                    chunk = [s for s in chunk if s != named]
        return out

    def daily(self, symbols: Sequence[str], first: dt.date, last: dt.date) -> list[DailyBar]:
        def ask(chunk: list[str]) -> list[DailyBar]:
            pages = self.alpaca.daily_bars(chunk, first.isoformat(), last.isoformat(), SIP)
            return [bar for page in pages for bar in convert.daily_bars(page)]

        return self._each_call(symbols, ask)

    @property
    def live_feed(self) -> str:
        """The feed live data comes from: SIP where the key has it in real
        time, else IEX (synthetic: IEX)."""
        return IEX if self.synthetic else self.entitlements().live_feed

    def _on_live_feed(self, ask: Callable[[str], T]) -> T:
        """`ask` of the live feed; where SIP refuses it (403), the key is
        taken not to have SIP in real time, and it is asked of IEX."""
        feed = self.live_feed
        try:
            return ask(feed)
        except VendorError as refused:
            if feed != SIP or refused.status != 403:
                raise
        with self._lock:
            if self._entitled is not None:
                self._entitled = replace(self._entitled, sip_live=False)
        return ask(IEX)

    def trades(self, symbols: Sequence[str], start_ns: int, end_ns: int) -> list[SourceTrade]:
        """The trades from `start_ns` to `end_ns`, from the live feed."""

        def ask(feed: str) -> list[SourceTrade]:
            def call(chunk: list[str]) -> list[SourceTrade]:
                pages = self.alpaca.trades(chunk, start_ns, end_ns, feed)
                return [trade for page in pages for trade in convert.trades_page(page)]

            return self._each_call(symbols, call)

        return self._on_live_feed(ask)

    def quotes(self, symbols: Sequence[str]) -> list[SourceQuote]:
        """The latest best bid and offer of each listing, from the live feed."""

        def ask(feed: str) -> list[SourceQuote]:
            def call(chunk: list[str]) -> list[SourceQuote]:
                return list(convert.latest_quote_rows(self.alpaca.latest_quotes(chunk, feed)))

            return self._each_call(symbols, call)

        return self._on_live_feed(ask)

    def live(self, symbols: Sequence[str]) -> list[Quoted]:
        def ask(feed: str) -> list[Quoted]:
            def call(chunk: list[str]) -> list[Quoted]:
                return [
                    *convert.latest_trades(self.alpaca.latest_trades(chunk, feed)),
                    *convert.latest_quotes(self.alpaca.latest_quotes(chunk, feed)),
                ]

            return self._each_call(symbols, call)

        return self._on_live_feed(ask)
