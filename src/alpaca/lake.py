"""What the plugin records in the lake, and how it answers what the lake wants
(contracts v18 and v19, W10): from SDK 0.31.0 the SDK's
(`meridian.roles.data.listings`, ruling 213), this module keeping what is
Alpaca's alone -- its source's name, how far its consolidated history
reaches, and its trades' and quotes' conditions converted at the edge
(conditions.py). Alpaca's stock trades state no aggressor; its trade history
is read for a range and for the gap after a reconnect or a restart; a symbol
it answers it cannot take (its 400, "invalid symbol") is declined once for
the date and never asked again.

**The edge, done here for now** (from 0.14.0; contract v28, rulings 424
and 518): each live price, quote and trade recorded unasked or for a
standing want has its feed delay recorded (`roles.Latency.aged`, the
`edge` hop) and is judged by the SDK's quality checks
(`quality.EdgeChecks`), as the SDK's `Wants.record` does for the other
feeds. TEMPORARY: the SDK's listings feed records neither in 0.33.1; this
glue goes when its listings feed takes them over (queued as SDK 0.33.2).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data import listings
from meridian.roles.data.listings import (
    BAR,
    DAILY,
    LIVE,
    LIVE_CADENCE_SECONDS,
    LIVE_KINDS,
    PRICE,
    QUOTE,
    TRADE,
    TRADES,
    Counts,
    Forming,
    Listings,
    Source,
    Standing,
    row_key,
)
from meridian.roles.data.quality import EdgeChecks

from . import conditions
from .convert import SOURCE

__all__ = [
    "BAR", "DAILY", "LIVE", "LIVE_CADENCE_SECONDS", "LIVE_KINDS", "PRICE", "QUOTE", "TRADE",
    "TRADES", "Counts", "Forming", "Lake", "Products", "Source", "Standing", "row_key",
]  # fmt: skip

#: The earliest day the source's consolidated history reaches.
HISTORY_FROM = dt.date(2016, 1, 1)

#: Which listing each subject is, kept in the plugin's storage.
Products = Listings


class Lake(listings.Feed):
    """Alpaca's listings in the lake: the SDK's feed, Alpaca's conditions."""

    source_name = SOURCE
    history_from = HISTORY_FROM

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        #: The plugin's `roles.Latency`, where it keeps one: each live row's
        #: age at the edge recorded (the feed delay); and the edge's checks.
        self.latency: Any = None
        self.quality = EdgeChecks(clock_ns=self.clock_ns)

    async def _record(self, key: str, data_type: str, rows: Any, want_id: str) -> None:
        """Live rows recorded unasked or for a standing want, their age at
        the edge recorded and judged by the SDK's checks first; rows pulled
        for a read as they are. TEMPORARY until the SDK's listings feed does
        it (SDK 0.33.2)."""
        standing = not want_id or want_id in self.standing
        if standing and key in (LIVE, TRADES) and data_type in (PRICE, QUOTE, TRADE):
            rows = list(rows)
            if self.latency is not None:
                for row in rows:
                    self.latency.aged(self.dataset(key), "AGE_HOP_EDGE", row)
            rows = self.quality.judged(key, rows)
        await super()._record(key, data_type, rows, want_id)

    def attributes(self, stated: Any) -> listings.Attributes:
        said = conditions.trade_attributes(stated.codes, stated.tape)
        return listings.Attributes(
            said.characteristics, said.consolidated, said.market_centre, said.unconverted
        )

    def quote_characteristics(
        self, stated: Any
    ) -> tuple[tuple[str, ...], tuple[ops.AsReported, ...]]:
        return conditions.quote_characteristics(stated.codes)
