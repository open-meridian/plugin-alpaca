"""The Alpaca plugin: Alpaca's US equity and ETF market data in an Open Meridian
deployment's lake, as a data plugin (contract v20; plans/the-lake-prices-the-book,
the retail pair).

It connects to the sidecar it is launched beside, declaring its catalogue,
its settings and its storage (declaration.py) and its pages (page.py); on
each delivery of its settings it makes its Alpaca client again with the key
(or, with sample data, the built-in exchange) and asks which feeds the key
is entitled to; it reads which of its datasets a deployment admin has
licensed (contract v20), and reports the data role's figures; then it
hears what the lake wants of it and records against each want or declines
it per subject (lake.py), and keeps its timetable:
standing wants kept current, days still forming read again, a final close
pushed. While any standing want stands, it streams Alpaca's trades and
quotes for the listings wanted (stream.py), reconnecting when the stream
breaks and catching up the gap; and, the first time a listing's trades are
wanted after a restart, backfilling what it missed while stopped from the
last trade it recorded (lake.py, `backfill_restart`).

From 0.7.0 it is also the account's connection for orders, where the
deployment launched it with `connectivity`: it hears each placement naming
its instance and places it at Alpaca's Trading API in the environment
chosen (paper or live), hears Alpaca's trade updates and reads the orders,
honouring the firm's pauses and stops, and from 0.8.0 reports the fills of
orders placed in Alpaca's own app on no placement (the SDK's
`meridian.roles.connectivity.Trader`; updates.py).
From 0.8.0, where launched with `custody`, it is the account's custodian
too: it reads the account every Read every, reporting its positions, cash
and activity (custody.py). Sample data trades with, and reads, a simulated
brokerage (synthetic_broker.py), never Alpaca.

It holds nothing it cannot lose: what each subject's symbol is, and every
raw response, are in the storage the deployment grants it (decisions/028);
a restart reads them back and hears the lake again. The key arrives as two
secret settings, never logged, shown or sent anywhere but Alpaca.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian import edge
from meridian.errors import NotRegistered
from meridian.roles import Latency
from meridian.roles.connectivity import Sent, Trader, Watched, trading_files

from .broker import Broker, base_for, stream_for
from .custody import MARKET_ZONE, Syncer
from .declaration import DECLARATION, PORT
from .kinds import Store, tend, windows_from
from .kinds import root as kinds_root
from .lake import Lake, Products
from .page import State, figures, pages, use
from .raw import RawStore, storage_root
from .settings import Config, config_from
from .source import AlpacaSource
from .stream import AlpacaFeed, Feed, Streamer, symbol_limit
from .synthetic import SyntheticFeed, SyntheticTransport, exchange
from .synthetic_broker import SyntheticBroker
from .updates import AlpacaUpdates, SyntheticUpdates
from .vendor import IEX, Alpaca, NoKey, VendorError, urllib_transport
from .venue import AlpacaVenue

log = logging.getLogger("alpaca")

#: How often the timetable is looked at.
TICK_SECONDS = 15
#: How often the datasets' licences are read again.
LICENCES_SECONDS = 60
#: How often connectivity reads the orders at Alpaca, beside its trade
#: updates; and the simulated brokerage, which steps an order on each read.
POLL_SECONDS = 15
SYNTHETIC_POLL_SECONDS = 1
#: How often custody reads the simulated brokerage, in place of Read every.
SYNTHETIC_READ_SECONDS = 5
#: How often the kinds' windows are tended between deliveries of settings.
TEND_SECONDS = 3600
#: How often the source's health is said again between deliveries of
#: settings, from what Alpaca last answered.
HEALTH_SECONDS = 60


class Account:
    """Connectivity's client for the settings as they stand: the Trading API
    of the environment chosen, or the simulated brokerage."""

    def __init__(self, store: Store, granted: Path | None) -> None:
        self.store, self.granted = store, granted
        self.broker: Broker | None = None
        self.venue: AlpacaVenue | None = None
        self.updates: AlpacaUpdates | SyntheticUpdates | None = None
        self._synthetic: SyntheticBroker | None = None
        self._said: tuple[object, ...] = ()

    def use(self, config: Config) -> bool:
        """Make the client again where the settings changed what it is; True
        where they did."""
        said = (config.sample_data, config.environment, config.credentials)
        if said == self._said:
            return False
        self._said = said
        if config.sample_data:
            if self._synthetic is None:
                state = self.granted / "synthetic-venue" / "orders.json" if self.granted else None
                self._synthetic = SyntheticBroker(lambda: datetime.now(UTC), state)
            self.broker = Broker(
                self.store,
                None,
                base_for(config.environment),
                send=self._synthetic,
                keyless=True,
                synthetic=True,
            )
            self.updates = SyntheticUpdates(self._synthetic)
        elif config.credentials is not None:
            self.broker = Broker(self.store, config.credentials, base_for(config.environment))
            self.updates = AlpacaUpdates(config.credentials, stream_for(config.environment))
        else:
            self.broker, self.updates = None, None
        self.venue = AlpacaVenue(self.broker) if self.broker is not None else None
        return True


def source_for(config: Config, store: RawStore) -> tuple[Alpaca | None, AlpacaSource | None]:
    """The client and the source the settings give: sample data, the key's,
    or none while the key is incomplete."""
    if config.sample_data:
        alpaca = Alpaca(store, None, transport=SyntheticTransport(), keyless=True)
        return alpaca, AlpacaSource(alpaca, synthetic=True)
    if config.credentials is None:
        return None, None
    alpaca = Alpaca(store, config.credentials, transport=urllib_transport)
    return alpaca, AlpacaSource(alpaca)


def feed_for(state: State, store: RawStore) -> Feed | None:
    """The stream the settings give: sample data, Alpaca's on the feed the
    key has in real time, or none while the key is incomplete."""
    config = state.config
    if config.sample_data:
        return SyntheticFeed(store)
    if config.credentials is None:
        return None
    known = state.source.known if state.source is not None else None
    feed = known.live_feed if known is not None and known.answered else IEX
    return AlpacaFeed(config.credentials, feed, store)


def stream_limit(state: State) -> int | None:
    """How many listings the key may stream at once."""
    if state.config.sample_data:
        return None
    known = state.source.known if state.source is not None else None
    return symbol_limit(known.live_feed if known is not None else IEX)


def registered(role: Any) -> bool:
    """Whether `meridian.run` registered `role`: the instance holds its
    role."""
    try:
        role.plugin  # noqa: B018 - raises where it is not registered
    except NotRegistered:
        return False
    return True


async def read_licences(role: Any, state: State) -> None:
    """Which of its own declared datasets a deployment admin has licensed
    (contract v20, W10.9), for the Datasets page: a dataset with none is
    served by its catalogue's default terms until one is set."""
    answered = await role.list_datasets()
    state.licensed = frozenset(licence.dataset for licence in answered.licences)


class Process:
    """What the plugin's role classes share: the state the pages read, the
    raw records, the account's client, the settings applied, and the work
    no one role owns -- the latency reported and the health said by the
    first class started, the account scope followed and the kinds tended by
    the first of custody and connectivity started."""

    def __init__(self) -> None:
        self.granted = edge.storage_dir()
        self.store = RawStore(storage_root(Path(tempfile.mkdtemp(prefix="alpaca-raw-"))))
        self.kinds = Store(kinds_root())
        # The sessions' latency (contract v27), shown on Connection's
        # Sessions; and from 0.14.0 (contract v28, rulings 515 and 518) each
        # live row's age at the edge too, all reported every 10 seconds
        # through the first class started (SDK 0.35).
        self.latency = Latency()
        self.state = State(store=self.kinds, latency=self.latency)
        self.account = Account(self.kinds, self.granted)
        self.woken = asyncio.Event()
        self.first: Any = None
        self.desk: Any = None
        self.roles: list[Any] = []

    def connection(self) -> meridian.Plugin | None:
        """The connection, through any class registered on it."""
        for role in self.roles:
            if registered(role):
                held: meridian.Plugin = role.plugin
                return held
        return None

    async def on_settings(self, delivered: Any) -> None:
        """Each delivery of the settings, the first before any class starts:
        the Alpaca client made again with the key (or, with sample data, the
        built-in exchange), the account's client too, what is streamed
        asked again, and the kinds tended."""
        state, market = self.state, self.state.lake
        state.config = config_from(delivered.values, delivered.refused)
        state.values = dict(delivered.values)
        state.alpaca, state.source = source_for(state.config, self.store)
        if market is not None:
            market.source = state.source
            if state.config.sample_data and registered(market):
                # The built-in exchange's listings, as a source's own list.
                await market.seed_symbols(sorted(exchange()["bars"]))
        if self.account.use(state.config):
            state.updates, state.venue = self.account.updates, self.account.venue
            self.woken.set()
        await self.health(again=True)
        if market is not None:
            market.stream_limit = stream_limit(state)
            market.restream()
        if state.streamer is not None:
            state.streamer.restart()
        plugin = self.connection()
        if plugin is not None:
            await tend_now(plugin, self.kinds, delivered.values)

    async def health(self, again: bool = False) -> None:
        """Say how the source is: a missing key or a refused one is the
        plugin's health, never a ticket. `again` asks Alpaca what the key is
        entitled to anew; otherwise what it last answered is said."""
        plugin = self.connection()
        if plugin is None:
            return
        healthy, detail = await source_health(self.state, again)
        try:
            await plugin.report(healthy=healthy, detail=detail[:200])
        except (meridian.MeridianError, ValueError) as failed:
            log.warning("health not reported: %s", failed)

    def started(self, role: Any) -> None:
        """A class started: the first reports the latency and says the
        health; the first of custody and connectivity follows the account
        scope and tends the kinds."""
        if self.latency.role is None:
            self.latency.role = role
        if self.first is None:
            self.first = role
        if self.desk is None and role.role in ("custody", "connectivity"):
            self.desk = role

    async def shared(self, role: Any) -> None:
        """The work `role` owns of what the classes share (see `started`)."""
        work: list[Coroutine[Any, Any, None]] = []
        if role is self.first:
            work += [self.latency.run(), self._health()]
        if role is self.desk:
            work += [self._scope(), self._tend()]
        if work:
            await asyncio.gather(*work)

    async def _health(self) -> None:
        while True:
            await asyncio.sleep(HEALTH_SECONDS)
            await self.health()

    async def _scope(self) -> None:
        """The account scope, its links (W4.11) and its ems's venue account
        map (W11.22), on start and on every change: the account side and its
        pages hold it from here, and custody reads again at once. A stream
        that ends is raised, so the class's work starts again."""
        plugin = self.connection()
        assert plugin is not None
        async for scope in plugin.account_scope():
            self.state.scope = scope
            self.woken.set()
        raise ConnectionError("the account scope's stream ended")

    async def _tend(self) -> None:
        while True:
            await asyncio.sleep(TEND_SECONDS)
            plugin = self.connection()
            if plugin is not None:
                await tend_now(plugin, self.kinds, self.state.values)


async def source_health(state: State, again: bool) -> tuple[bool, str]:
    """How the source is, in a word for the plugin's health."""
    config = state.config
    if config.sample_data:
        return True, "sample data: the built-in exchange"
    if state.source is None:
        return False, "no Alpaca key: enter it in Settings"
    try:
        entitled = (
            await asyncio.to_thread(state.source.entitlements, True)
            if again
            else state.source.known
        )
    except (NoKey, VendorError, OSError) as failed:
        return False, f"Alpaca did not answer: {failed}"
    if entitled is None:
        return False, "Alpaca not asked yet"
    if not entitled.answered:
        return False, f"Alpaca refused the key: {entitled.detail}"
    live = "SIP" if entitled.sip_live else "IEX"
    return True, f"answering; daily from SIP, live from {live}"


async def tend_now(plugin: meridian.Plugin, kinds: Store, values: Any) -> None:
    """Each kind's units past its window moved as the settings say."""
    try:
        await tend(plugin, kinds, windows_from(values), datetime.now(UTC).date())
    except (meridian.MeridianError, OSError) as failed:
        log.warning("the raw records were not tended this time: %s", failed)


class Market(Lake):
    """The data role's class: Alpaca's listings in the lake (lake.py), its
    stream kept open, its timetable kept and its licences read in `run`."""

    def __init__(self, process: Process) -> None:
        granted = process.granted
        super().__init__(None, Products(granted / "products.json" if granted else None))
        self.process = process
        self.latency = process.latency

    async def on_start(self) -> None:
        self.process.started(self)

    async def run(self) -> None:
        assert self.streamer is not None
        await asyncio.gather(
            self.streamer.run(), self._timetable(), self._licences(), self.process.shared(self)
        )

    async def _timetable(self) -> None:
        while True:
            try:
                await self.tick()
            except meridian.MeridianError as failed:
                log.warning("the timetable stopped this time: %s", failed)
            await asyncio.sleep(TICK_SECONDS)

    async def _licences(self) -> None:
        """The licences, read on start and every minute."""
        while True:
            try:
                await read_licences(self, self.process.state)
            except meridian.MeridianError as failed:
                log.warning("the datasets' licences were not read this time: %s", failed)
            await asyncio.sleep(LICENCES_SECONDS)


class Custodian(Syncer):
    """The custody role's class: Alpaca read every Read every (custody.py),
    or sooner when the settings or the links change."""

    def __init__(self, process: Process) -> None:
        state = process.state
        super().__init__(
            lambda: process.account.broker,
            paper=lambda: state.config.paper and not state.config.sample_data,
            stale_after=lambda: state.config.stale_after,
            linked=lambda number: state.scope.link_of(number) is not None,
        )
        self.process = process

    async def on_start(self) -> None:
        self.process.state.syncer = self
        self.process.started(self)

    async def run(self) -> None:
        await asyncio.gather(self._reads(), self.process.shared(self))

    async def _reads(self) -> None:
        state, woken = self.process.state, self.process.woken
        while True:
            woken.clear()
            try:
                await self.run_once()
            except meridian.MeridianError as failed:
                log.warning("this read of the account stopped: %s", failed)
            wait = SYNTHETIC_READ_SECONDS if state.config.sample_data else state.config.poll_seconds
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(woken.wait(), timeout=wait)


class Trading(Trader):
    """The connectivity role's class: the SDK's `Trader` against Alpaca's
    Trading API (or the simulated brokerage), its trade updates heard
    beside it (updates.py)."""

    def __init__(self, process: Process) -> None:
        state, account = process.state, process.account
        sent, enabled, originated = trading_files(process.granted)
        super().__init__(
            lambda: account.venue,
            now=lambda: datetime.now(UTC),
            sent=Sent(sent),
            enabled=Sent(enabled),
            # The venue account codes its ems mapped on it (W11.22).
            scope=lambda: state.scope,
            watched=Watched(originated),
            market_zone=MARKET_ZONE,
            # Each call to the Trading API its round trip, a placement its
            # acknowledgement, a fill its delay (contract v27).
            latency=state.latency,
            poll_seconds=lambda: (
                SYNTHETIC_POLL_SECONDS if state.config.sample_data else POLL_SECONDS
            ),
        )
        self.process = process

    async def on_start(self) -> None:
        self.process.state.trader = self
        self.process.started(self)
        await super().on_start()

    async def run(self) -> None:
        await asyncio.gather(super().run(), self._updates(), self.process.shared(self))

    async def _updates(self) -> None:
        """The trade updates of the client as the settings stand, heard again
        whenever the client is made again."""
        account = self.process.account
        while True:
            updates = account.updates
            if updates is None:
                await asyncio.sleep(1)
                continue
            task = asyncio.create_task(updates.run(self, account.store))
            while account.updates is updates and not task.done():
                await asyncio.sleep(1)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    process = Process()
    state = process.state
    market = Market(process)
    state.lake = market
    store = process.store
    state.streamer = market.streamer = Streamer(
        lambda: feed_for(state, store), market.heard, market.flush, caught_up=market.caught_up
    )
    # One class per role it may hold (SDK 0.35): `meridian.run` registers
    # those the instance holds, applies the first settings, and starts each
    # one's `run`, again after a backoff should it fail.
    process.roles = [market, Custodian(process), Trading(process)]
    use(state)
    # The version's whole declaration (declaration.py): its settings, its
    # pages with the levels each serves and their tools, and its
    # documentation. A version registers exactly what it was uploaded with
    # (contract v25).
    meridian.run(
        declaration=DECLARATION,
        roles=process.roles,
        pages=pages,
        port=PORT,
        on_settings=process.on_settings,
        figures=lambda: figures(state),
    )


if __name__ == "__main__":
    main()
