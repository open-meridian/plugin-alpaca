"""What the plugin records in the lake, and how it answers what the lake wants
(contracts v18 and v19, W10): from SDK 0.31.0 the SDK's
(`meridian.roles.data.listings`, ruling 213), this module keeping what is
Alpaca's alone -- its source's name, how far its consolidated history
reaches, and its trades' and quotes' conditions converted at the edge
(conditions.py). Alpaca's stock trades state no aggressor; its trade history
is read for a range and for the gap after a reconnect or a restart; a symbol
it answers it cannot take (its 400, "invalid symbol") is declined once for
the date and never asked again.
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

    def attributes(self, stated: Any) -> listings.Attributes:
        said = conditions.trade_attributes(stated.codes, stated.tape)
        return listings.Attributes(
            said.characteristics, said.consolidated, said.market_centre, said.unconverted
        )

    def quote_characteristics(
        self, stated: Any
    ) -> tuple[tuple[str, ...], tuple[ops.AsReported, ...]]:
        return conditions.quote_characteristics(stated.codes)
