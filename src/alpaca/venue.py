"""Alpaca as the Trader's venue (meridian.roles.connectivity): its words to the contract's and
back, over its Trading API (broker.py). The one place Alpaca's order
vocabulary is read.

**What Alpaca takes** (`POST /v2/orders`, for US equities): `market`,
`limit`, `stop` and `stop_limit`, each `day` or `gtc`; and `ioc` and `fok`
for `market` and `limit`. Alpaca takes no good-till-date or good-till-time
order, so one is rejected `unsupported` before anything is sent. A sell is
`sell`, and a short sale too: Alpaca opens a short where a sell is more than
the account holds, and states no other side. The placement's ID is the
client order ID, which Alpaca holds unique on the account.

**A replace** is `PATCH /v2/orders/{id}`, its quantity, limit and time in
force; Alpaca answers a new order in the old one's place (`replaces`), and
lists the old one `replaced`, naming its successor (`replaced_by`). A 200
does not promise it: where the old order filled first, the replace is
rejected on the trade updates (`order_replace_rejected`).

**Its statuses** (Alpaca's "Orders at Alpaca"): working while `new`,
`partially_filled`, `accepted`, `pending_new`, `accepted_for_bidding`,
`pending_cancel`, `pending_replace`, `stopped` or `calculated`; `filled`;
`canceled`; `expired`; `rejected`; `suspended`; `done_for_day`; `replaced`.
Any other -- `held`, which Alpaca lists and does not describe, say -- is
outcome unknown, the status as reported.

**The environment its session reached** (contract v26, G1 question 5):
`environment` is read from the host the Trading API is called at,
`paper-api.alpaca.markets` `paper` and `api.alpaca.markets` `live`
(`meridian.reached_environment`), and the SDK's Trader publishes it on the
venue catalogue: the second key of the agents' demo-only guard, which
counts a connection demo only while the setting and this both say `paper`.
The simulated brokerage reaches no venue, so it reports `paper`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import meridian
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import connectivity
from meridian.roles.connectivity import (
    Asked,
    Catalogue,
    Change,
    VenueOrder,
    VenueRefused,
    VenueUnanswered,
)

from .broker import Broker, BrokerError, Unanswered
from .kinds import TRADING

SOURCE = "alpaca"
#: Alpaca's Trading API hosts, by the environment each is (contract v26).
LIVE_HOSTS = ("api.alpaca.markets",)
PAPER_HOSTS = ("paper-api.alpaca.markets",)
#: What the simulated brokerage reports: it reaches no venue.
PAPER = "paper"
#: How long the account's number is held before it is read again.
ACCOUNT_READ_AGAIN = timedelta(minutes=10)

STATUSES = {
    **{
        status: connectivity.WORKING
        for status in (
            "new",
            "partially_filled",
            "accepted",
            "pending_new",
            "accepted_for_bidding",
            "pending_cancel",
            "pending_replace",
            "stopped",
            "calculated",
        )
    },
    "filled": connectivity.FILLED,
    "canceled": connectivity.CANCELLED,
    "expired": connectivity.EXPIRED,
    "rejected": connectivity.REJECTED,
    "suspended": connectivity.SUSPENDED,
    "done_for_day": connectivity.DONE_FOR_DAY,
    "replaced": connectivity.REPLACED,
}
SIDES: dict[int, str] = {ops.SIDE_BUY: "buy", ops.SIDE_SELL: "sell", ops.SIDE_SELL_SHORT: "sell"}
#: The contract's side for each of Alpaca's words for one (an order's
#: `side`), for a fill on no placement (contract v23).
SIDES_SAID: dict[str, int] = {"buy": ops.SIDE_BUY, "sell": ops.SIDE_SELL}
ORDER_TYPES: dict[int, str] = {
    ops.ORDER_TYPE_MARKET: "market",
    ops.ORDER_TYPE_LIMIT: "limit",
    ops.ORDER_TYPE_STOP: "stop",
    ops.ORDER_TYPE_STOP_LIMIT: "stop_limit",
}
TIMES_IN_FORCE: dict[int, str] = {
    ops.TIME_IN_FORCE_DAY: "day",
    ops.TIME_IN_FORCE_GOOD_TILL_CANCELLED: "gtc",
    ops.TIME_IN_FORCE_IMMEDIATE_OR_CANCEL: "ioc",
    ops.TIME_IN_FORCE_FILL_OR_KILL: "fok",
}
_DAY_GTC = (ops.TIME_IN_FORCE_DAY, ops.TIME_IN_FORCE_GOOD_TILL_CANCELLED)
_ALL = (*_DAY_GTC, ops.TIME_IN_FORCE_IMMEDIATE_OR_CANCEL, ops.TIME_IN_FORCE_FILL_OR_KILL)
CATALOGUE: Catalogue = (
    (ops.ORDER_TYPE_MARKET, _ALL),
    (ops.ORDER_TYPE_LIMIT, _ALL),
    (ops.ORDER_TYPE_STOP, _DAY_GTC),
    (ops.ORDER_TYPE_STOP_LIMIT, _DAY_GTC),
)


def _text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def order_of(said: Any) -> VenueOrder:
    """One of Alpaca's order objects, as the Trader reads it."""
    held = said if isinstance(said, dict) else {}
    return VenueOrder(
        order_id=str(held.get("id") or ""),
        client_order_id=str(held.get("client_order_id") or ""),
        status=str(held.get("status") or ""),
        symbol=str(held.get("symbol") or ""),
        side=str(held.get("side") or ""),
        quantity=connectivity.number(held.get("qty")),
        filled=connectivity.number(held.get("filled_qty")) or Decimal(0),
        average=connectivity.number(held.get("filled_avg_price")),
        limit=connectivity.number(held.get("limit_price")),
        placed_at=connectivity.moment(held.get("submitted_at") or held.get("created_at")),
        updated_at=connectivity.moment(held.get("updated_at")),
        filled_at=connectivity.moment(held.get("filled_at")),
        replaced_by=str(held.get("replaced_by") or ""),
        replaces=str(held.get("replaces") or ""),
        reason=str(held.get("reason") or ""),
    )


class AlpacaVenue:
    """The Trader's venue: Alpaca's one account under the key."""

    statuses: dict[str, str] = STATUSES
    sides: dict[int, str] = SIDES
    sides_said: dict[str, int] = SIDES_SAID
    source: str = SOURCE

    def __init__(self, broker: Broker) -> None:
        self.broker = broker
        #: The environment the session reached (above).
        self.environment = (
            PAPER
            if broker.synthetic
            else meridian.reached_environment(broker.base, live=LIVE_HOSTS, paper=PAPER_HOSTS)
        )
        self._number = ""
        self._read_at: datetime | None = None

    def accounts(self) -> tuple[str, ...]:
        """The account the key reaches, by its number: read again at most
        every ten minutes."""
        now = self.broker.now()
        if self._number and self._read_at and now - self._read_at < ACCOUNT_READ_AGAIN:
            return (self._number,)
        answer = self._asking(self.broker.account)
        self._number = str((answer.value or {}).get("account_number") or "")
        self._read_at = now
        return (self._number,) if self._number else ()

    def catalogue(self, code: str) -> Catalogue:
        return CATALOGUE

    def _asking(self, work: Callable[[], Any]) -> Any:
        try:
            return work()
        except BrokerError as refused:
            raise VenueRefused(
                refused.code or str(refused.status), refused.text, refused.raw_key
            ) from None
        except Unanswered as lost:
            raise VenueUnanswered(str(lost), lost.raw_key) from None

    def place(self, code: str, asked: Asked) -> tuple[VenueOrder, str]:
        body: dict[str, Any] = {
            "symbol": asked.symbol,
            "qty": _text(asked.quantity),
            "side": SIDES[asked.side],
            "type": ORDER_TYPES[asked.order_type],
            "time_in_force": TIMES_IN_FORCE[asked.time_in_force],
            "client_order_id": asked.placement_id,
        }
        if asked.limit is not None and asked.order_type in (
            ops.ORDER_TYPE_LIMIT,
            ops.ORDER_TYPE_STOP_LIMIT,
        ):
            body["limit_price"] = _text(asked.limit)
        if asked.stop is not None and asked.order_type in (
            ops.ORDER_TYPE_STOP,
            ops.ORDER_TYPE_STOP_LIMIT,
        ):
            body["stop_price"] = _text(asked.stop)
        answer = self._asking(lambda: self.broker.place(body))
        return order_of(answer.value), answer.raw_key

    def orders(self, code: str) -> tuple[list[VenueOrder], str]:
        answer = self._asking(self.broker.orders)
        listed = answer.value if isinstance(answer.value, list) else []
        return [order_of(each) for each in listed], answer.raw_key

    def cancel(self, code: str, order_id: str) -> str:
        answer = self._asking(lambda: self.broker.cancel(order_id))
        return str(answer.raw_key)

    def not_replaceable(self, change: Change) -> str:
        if change.order_type not in ORDER_TYPES or change.side not in SIDES:
            return "Alpaca replaces the order types and sides it places"
        if change.time_in_force not in TIMES_IN_FORCE:
            return "Alpaca takes no such time in force"
        return ""

    def replace(
        self, code: str, order: VenueOrder | None, order_id: str, change: Change
    ) -> tuple[VenueOrder | None, str]:
        body: dict[str, Any] = {
            "qty": _text(change.quantity),
            "time_in_force": TIMES_IN_FORCE[change.time_in_force],
        }
        if change.limit is not None and change.order_type in (
            ops.ORDER_TYPE_LIMIT,
            ops.ORDER_TYPE_STOP_LIMIT,
        ):
            body["limit_price"] = _text(change.limit)
        if change.stop is not None and change.order_type in (
            ops.ORDER_TYPE_STOP,
            ops.ORDER_TYPE_STOP_LIMIT,
        ):
            body["stop_price"] = _text(change.stop)
        answer = self._asking(lambda: self.broker.replace(order_id, body))
        return order_of(answer.value), answer.raw_key

    def keep(self, name: str, record: dict[str, Any]) -> str:
        return self.broker.store.keep(
            TRADING,
            name,
            {"venue": SOURCE, "synthetic": self.broker.synthetic, **record},
            self.broker.now(),
        )


def update_of(said: Any) -> tuple[str, VenueOrder, connectivity.Fill | None]:
    """One of Alpaca's trade updates: its event, the order as it stands, and
    the fill as Alpaca stated it, where it is one."""
    held = said if isinstance(said, dict) else {}
    event = str(held.get("event") or "")
    record = order_of(held.get("order"))
    fill = None
    if event in ("fill", "partial_fill"):
        qty, price = connectivity.number(held.get("qty")), connectivity.number(held.get("price"))
        if qty is not None and price is not None:
            fill = connectivity.Fill(qty, price, connectivity.moment(held.get("timestamp")))
    return event, record, fill
