"""Alpaca's connectivity work run against the suites' recorder: the plugin's
SDK Trader (meridian.roles.connectivity) over its own venue adapter (venue.py) and Trading API
client (broker.py), speaking to the simulated brokerage
(synthetic_broker.py); only the sidecar is stood in for by the recorder.

Shared by the connectivity suite's test, the trading tests and the custody
suite's `asks-for-a-settlement-date`. SIMULATED ONLY: nothing here reaches
Alpaca, its paper trading API or any brokerage.
"""

from __future__ import annotations

import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.connectivity import Venue, testing
from meridian.roles.connectivity.testing import ACCOUNT, CALENDAR, INSTRUMENT, NOW, asking, clock
from meridian.suites import Recorder

from alpaca.broker import PAPER_BASE, Broker
from alpaca.kinds import Store
from alpaca.synthetic_broker import ACCOUNT_NUMBER, SyntheticBroker
from alpaca.updates import SyntheticUpdates
from alpaca.vendor import RateLimiter
from alpaca.venue import AlpacaVenue

__all__ = ["ACCOUNT", "CALENDAR", "INSTRUMENT", "NOW", "asking", "clock"]

Producer = Callable[[Recorder], Awaitable[None]]

CODE = ACCOUNT_NUMBER


def placement(pid: str = "PLC-01JAE00000000000000000001", **kw: Any) -> ops.Placement:
    """A placement to this plugin's instance, in its account."""
    kw.setdefault("instance", "alpaca")
    kw.setdefault("code", CODE)
    return testing.placement(pid, **kw)


def scope(*codes: str, instance: str = "alpaca") -> Any:
    return testing.scope(*codes, instance=instance)


class Rig(testing.Rig):
    """The SDK's Trader over the recorder and this plugin's own adapter and
    client, speaking to the simulated brokerage; trading enabled on its
    account."""

    instance = "alpaca"
    code = CODE
    source = "alpaca"

    def connect(self, broker: Any) -> Venue:
        self.brokerage = broker or SyntheticBroker(clock)
        self.store = Store(Path(tempfile.mkdtemp()))
        self.broker = Broker(
            self.store,
            None,
            PAPER_BASE,
            send=self.brokerage,
            limiter=RateLimiter(per_minute=6_000_000, sleep=lambda _: None),
            now=clock,
            keyless=True,
            synthetic=True,
        )
        self.updates = SyntheticUpdates(self.brokerage)
        return AlpacaVenue(self.broker)

    async def after_poll(self) -> None:
        """The trade updates a read's steps made, as the stream delivers them."""
        await self.updates.drain(self.trader, self.store)


async def placed_and_filled(recorder: Recorder) -> None:
    """A placement of 10 placed and filled at the simulated brokerage: 4, then
    the rest, each with the date read's settlement date."""
    rig = Rig(recorder)
    held = placement()
    rig.holds(held)
    await rig.hear(held)
    await rig.poll(2)
