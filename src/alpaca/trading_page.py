"""Connectivity's pages, from 0.7.0, each the same answer as its tool.

- Trading (`/admin/connections`, Manage; connectivity): `read_trading`.
  The key, set or not; the environment the account is in, said plainly --
  Paper (simulated money) or Live, or sample data; then each account the key
  reaches by its venue account code, read-only or with trading enabled, its
  catalogue and whether its ems mapped it here; and what is working, held
  back by a pause or a stop, or of unknown outcome. "Enable trading" on a
  read-only account, for the connectivity role's admin
  (`enable_trading`, checked by `check_enable_trading`, at
  `/admin/connections/enable-trading` as SnapTrade's): a new account is
  read-only until then. Counts and codes only: an admin page shows no
  account's data. From contract v26 it carries the agents' demo-only
  guard's second key beside the setting: the environment the session
  reached, read from Alpaca's host (venue.py), and the badge the two make
  (`meridian.connection_badge`).
- Raw records (`/raw`, Open and View; custody and connectivity): each kind
  kept, its window and what becomes of it past it, and a raw record followed
  from a fact's or a row's reference, shown to a person who may read an
  account mapped on this instance or linked by it; no tool of its own.
"""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

import meridian
from meridian.roles import connectivity, data
from meridian.roles.connectivity import TradingAsked, TradingEnabled

from .kinds import KINDS
from .page import current, pages
from .records import TradingRead
from .settings import SAID

TRADING = "/admin/connections"
ENABLE_TRADING = f"{TRADING}/enable-trading"
#: Connectivity's Trading page: the SDK's, with the connection's badge.
TEMPLATE = "trading.html"
#: How the template names the venue and how its orders are heard: the trade
#: updates stream.
SAID_HOW: dict[str, Any] = {
    "venue": "Alpaca",
    "updates_label": "Trade updates",
    "updates_none": "Not streaming",
}
RAW = "/raw"
CHECK = "/check"


def environment() -> str:
    config = current().config
    if config.sample_data:
        return "Sample data: a simulated brokerage, nothing sent to Alpaca"
    return SAID[config.environment]


def _reached() -> list[str]:
    trader = current().trader
    return list(trader.reached) if trader is not None else []


def session_environment() -> str:
    """The environment the session reached (venue.py): `live`, `paper`, or
    empty while there is no client to reach Alpaca with."""
    venue = current().venue
    return str(getattr(venue, "environment", "") or "") if venue is not None else ""


def trading_read() -> TradingRead:
    state = current()
    config = state.config
    reached = session_environment()
    held = connectivity.trading_read(
        state.trader,
        [
            data.Credential("API key ID", config.key_id_set),
            data.Credential("API secret key", config.secret_key_set),
        ],
        environment(),
        str(getattr(state.updates, "state", "") or ""),
    )
    return TradingRead(
        **{each.name: getattr(held, each.name) for each in fields(held)},
        reached_environment=reached,
        badge=meridian.connection_badge(config.environment_setting, reached) if reached else "",
        environment_to_save=config.environment_to_save,
    )


def _may_enable(request: meridian.Request) -> bool:
    return bool(request.caller.level_for("connectivity") == meridian.AccessLevel.ACCESS_LEVEL_ADMIN)


@pages.page(
    TRADING,
    "Trading",
    levels="admin",
    roles="connectivity",
    answers=TradingRead,
    name="read_trading",
    description=(
        "Connectivity's state at Alpaca: each credential, set or not (never a value); the "
        "environment, Paper (simulated money) or Live, or sample data; each account the key "
        "reaches by its venue account code, read-only or with trading enabled, the order "
        "types its catalogue offers and whether its ems mapped it here; how many placements "
        "are working, held back by a pause or a stop, or of unknown outcome; the last read "
        "of the orders and the trade updates stream's state; the environment the session "
        "reached and the connection's badge, Demo or Live. No account's data."
    ),
)
async def trading(request: meridian.Request) -> meridian.Response:
    return pages.answer(
        TEMPLATE, trading_read(), may_enable=_may_enable(request), enable=ENABLE_TRADING, **SAID_HOW
    )


def _asked(request: meridian.Request) -> str:
    asked: TradingAsked = request.params
    code = (asked.venue_account_code or "").strip()
    if code not in _reached():
        pages.refuse(
            "the key reaches no account under this venue account code",
            ("venue_account_code", "not reached"),
        )
    return code


@pages.route(
    ENABLE_TRADING,
    levels="admin",
    roles="connectivity",
    methods=["POST"],
    params=TradingAsked,
    answers=TradingEnabled,
    name="enable_trading",
    checked_by="check_enable_trading",
    description=(
        "Enable trading on an account the key reaches, by its venue account code: a new "
        "account is read-only until the connectivity role's admin enables it. Its catalogue "
        "is published at once."
    ),
)
async def enable_trading(request: meridian.Request) -> meridian.Response:
    code = _asked(request)
    trader = current().trader
    if trader is None:
        pages.refuse("this instance holds no connectivity role", ("venue_account_code", "no role"))
    if not trader.trading_on(code):
        await trader.enable(
            code,
            {
                "venue_account_code": code,
                "enabled_by": request.caller.subject,
                "environment": environment(),
            },
        )
    said = f"Trading enabled on {code} ({environment()})."
    if request.tool_name:
        return pages.answer(TEMPLATE, TradingEnabled(code, said))
    return pages.answer(
        TEMPLATE,
        trading_read(),
        may_enable=_may_enable(request),
        enable=ENABLE_TRADING,
        **SAID_HOW,
        notice=said,
    )


@pages.route(
    ENABLE_TRADING + CHECK,
    levels="admin",
    roles="connectivity",
    methods=["POST"],
    params=TradingAsked,
    answers=TradingEnabled,
    reads=True,
    name="check_enable_trading",
    description=(
        "Check enable_trading without enabling anything: whether the key reaches the account, "
        "and whether trading is enabled on it already."
    ),
)
async def check_enable_trading(request: meridian.Request) -> meridian.Response:
    code = _asked(request)
    trader = current().trader
    already = trader is not None and trader.trading_on(code)
    said = (
        f"Trading is enabled on {code} already."
        if already
        else f"Would enable trading on {code} ({environment()})."
    )
    return pages.answer(TEMPLATE, TradingEnabled(code, said))


def _may_read_mapped(request: meridian.Request) -> bool:
    """Whether the person may read an account mapped on this instance (the
    accounts connectivity's records are of) or linked by it (custody's)."""
    trader = current().trader
    scope = current().scope
    if any(link.account_id in request.caller.read_for("custody") for link in scope.links):
        return True
    if trader is None or scope.venue_account_map is None:
        return False
    allowed = request.caller.read_for("connectivity")
    return any(
        mapping.account_id in allowed
        for mapping in scope.venue_account_map.mappings
        if mapping.connectivity_instance_id == trader.me
    )


@pages.page(
    RAW,
    "Raw records",
    levels=["write", "read"],
    roles=["custody", "connectivity"],
    tool=False,
    why=(
        "Alpaca's answers as received, any JSON it sent, which no typed record holds; an "
        "agent reads what they came to with read_statements and read_account_activities, "
        "and in the book's placements and executions, each naming its raw record"
    ),
)
async def raw_records(request: meridian.Request) -> str:
    state = current()
    key = request.query.get("ref", "").strip()
    found: Any = None
    record: Any = None
    if key:
        finding = getattr(request.plugin, "find_record", None)
        found = finding(key.partition("#")[0]) if finding is not None else None
        held = state.store.get(key) if state.store is not None else None
        if held is not None and _may_read_mapped(request):
            record = json.dumps(held, indent=1, sort_keys=True)
    return pages.render(
        "raw_records.html",
        kinds=list(KINDS),
        stored=list(getattr(request.plugin, "stored", None) or []),
        past=state.values,
        key=key,
        found=found,
        record=record,
    )
