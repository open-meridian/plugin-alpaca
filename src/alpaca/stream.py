"""Alpaca's market data stream, over WebSocket, with reconnect (contract v19;
plans/the-lake-prices-the-book, row 19).

What is streamed is what the lake keeps current: the listings under a
standing want (lake.py says which), and nothing while there is none;
nothing of it is kept here. A standing want is heard once, when the lake
asks: contract v19 gives a want no catch-up read and the lake does not ask
again while it stands, so a process started anew streams nothing until a
want is asked anew (raised with the lake's plan).

**Alpaca's protocol** (`wss://stream.data.alpaca.markets/v2/{feed}`): the
server says it is connected; the client authenticates with the key (a
message the key's two parts travel in, never kept); then subscribes to
trades and quotes by symbol, and changes that as the wants change. Each
frame is a list of messages: trades (`T: t`), quotes (`q`), a trade
withdrawn (`x`) or corrected (`c`), and Alpaca's answers (`success`,
`subscription`, `error`). A free account streams IEX alone, 30 symbols on
one connection; SIP needs Algo Trader Plus. An error naming the key (402),
the plan (409) or the connection limit (406) is said on the Connection page
and asked again later; the symbol limit (405) is kept from by the lake.

**Reconnect**, the SDK's supervisor's from 0.15.0 (`helpers.sessions`,
ruling 1027). A connection that breaks, closes or goes silent is opened
again, a second later, then doubling to a minute, each wait within a fifth
of itself; the subscriptions are made again from what is wanted. On each
session after the first, the gap is caught up: the lake reads, from
Alpaca's trade history, the trades since each listing was last heard, and
records those it has not, so the lake holds every trade and its readers
catch up from it (W10.5, by watermark).

**Every message is a raw record first**, a line of the session's record
(raw.StreamLog), before anything converts it; the key is never in one.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from typing import Any, Protocol

from meridian.helpers import sessions

from . import convert, ws
from .convert import SourceQuote, SourceTrade
from .raw import RawStore, StreamLog
from .settings import Credentials
from .vendor import IEX, NS, STREAM

log = logging.getLogger("alpaca.stream")

#: A free account's most symbols on IEX's stream; SIP's plan has no limit.
IEX_SYMBOLS = 30
#: How long a session may say nothing before it is taken for broken: Alpaca
#: sends nothing between trades, so this is long.
SILENT_SECONDS = 120.0
#: How often what is heard is flushed to the lake, at the most.
FLUSH_SECONDS = 0.5
#: After the key is refused, how long before it is tried again.
REFUSED_WAIT = 300.0

Stated = SourceTrade | SourceQuote


class Refused(Exception):
    """Alpaca refused the key, the plan or the connection: tried again only
    after a while."""


class FeedError(Exception):
    """Alpaca said something went wrong in the session."""


class Feed(Protocol):
    """One session with a stream: opened, subscribed, read, closed."""

    name: str

    async def open(self) -> None: ...

    async def subscribe(self, symbols: Sequence[str]) -> None: ...

    async def receive(self) -> list[Stated]: ...

    async def close(self) -> None: ...


def _parse(text: str) -> Any:
    return json.loads(text, parse_float=Decimal)


class AlpacaFeed:
    """Feed on Alpaca's stream, every message kept."""

    def __init__(
        self,
        credentials: Credentials,
        feed: str,
        store: RawStore,
        connect: Callable[..., Awaitable[Any]] = ws.connect,
        url: str = STREAM,
        clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self.credentials, self.name, self.store = credentials, feed, store
        self.connect, self.url, self.clock_ns = connect, url, clock_ns
        self.socket: Any = None
        self.log: StreamLog | None = None
        self.subscribed: set[str] = set()

    async def open(self) -> None:
        self.subscribed = set()
        now = self.clock_ns()
        day = time.strftime("%Y%m%d", time.gmtime(now // NS))
        self.log = StreamLog(self.store, f"stream/{self.name}/{day}/{now}")
        self.socket = await self.connect(f"{self.url}/{self.name}")
        await self._expect("connected")
        await self.socket.send(
            json.dumps(
                {
                    "action": "auth",
                    "key": self.credentials.key_id,
                    "secret": self.credentials.secret_key,
                }
            )
        )
        await self._expect("authenticated")

    async def _expect(self, said: str) -> None:
        """Read until Alpaca says `said`; refused where it says an error."""
        for _ in range(5):
            for message in self._keep(_parse(await self.socket.recv())):
                if message.get("T") == "success" and message.get("msg") == said:
                    return
                if message.get("T") == "error":
                    raise Refused(f"{message.get('code')} {message.get('msg')}")
        raise FeedError(f"Alpaca never said {said}")

    def _keep(self, frame: Any) -> list[dict[str, Any]]:
        """Each message of a frame, kept as a line of the session's record,
        with the key it was kept under."""
        messages = frame if isinstance(frame, list) else [frame]
        out: list[dict[str, Any]] = []
        received = self.clock_ns()
        for message in messages:
            if not isinstance(message, dict):
                continue
            key = (
                self.log.keep(
                    {"feed": self.name, "received_at_ns": received, "message": _textual(message)}
                )
                if self.log is not None
                else ""
            )
            out.append({**message, "_raw": key})
        return out

    async def subscribe(self, symbols: Sequence[str]) -> None:
        wanted = set(symbols)
        added, dropped = sorted(wanted - self.subscribed), sorted(self.subscribed - wanted)
        if added:
            await self.socket.send(
                json.dumps({"action": "subscribe", "trades": added, "quotes": added})
            )
        if dropped:
            await self.socket.send(
                json.dumps({"action": "unsubscribe", "trades": dropped, "quotes": dropped})
            )
        self.subscribed = wanted

    async def receive(self) -> list[Stated]:
        out: list[Stated] = []
        for message in self._keep(_parse(await self.socket.recv())):
            if message.get("T") == "error":
                code = message.get("code")
                if code in (402, 406, 409):
                    raise Refused(f"{code} {message.get('msg')}")
                raise FeedError(f"{code} {message.get('msg')}")
            out.extend(convert.streamed(message, str(message.get("_raw")), self.name))
        return out

    async def close(self) -> None:
        if self.socket is not None:
            with contextlib.suppress(Exception):
                await self.socket.close()
        if self.log is not None:
            self.log.close()
        self.socket, self.log = None, None


def _textual(value: Any) -> Any:
    """A parsed message with each number as its text, as it arrived."""
    if isinstance(value, dict):
        return {k: _textual(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_textual(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


class Streamer(sessions.Supervisor):
    """Alpaca's stream kept open by the SDK's supervisor (open-meridian 0.35,
    ruling 1027: `helpers.sessions.Supervisor` over the plugin's own feed,
    its `Link`): one session open while anything is wanted, subscribed to
    what is; what it hears handed to `heard`, flushed with `flush`, and
    after a reconnect `caught_up` asked for the gap since each listing was
    last heard. A refusal (the key, the plan, the connection limit) is
    waited out `REFUSED_WAIT`; any other break the supervisor's backoff.
    Beside the supervisor's state, what the Connection page shows: the feed
    of the session last made, and the trades caught up."""

    def __init__(
        self,
        make_feed: Callable[[], Feed | None],
        heard: Callable[[list[Stated]], Awaitable[None]],
        flush: Callable[[], Awaitable[None]],
        caught_up: Callable[[dict[str, int]], Awaitable[int]] | None = None,
        **kwargs: Any,
    ) -> None:
        #: The feed of the session last made ("iex", "sip"), and the trades
        #: caught up from Alpaca's history after a reconnect, since start.
        self.feed = ""
        self.caught = 0

        def made() -> Feed | None:
            feed = make_feed()
            if feed is not None:
                self.feed = feed.name
            return feed

        async def counted(since: dict[str, int]) -> int:
            assert caught_up is not None
            found = await caught_up(since)
            self.caught += found
            return found

        kwargs.setdefault("silent_seconds", SILENT_SECONDS)
        super().__init__(
            made,
            heard=heard,
            flush=flush,
            caught_up=counted if caught_up is not None else None,
            session="stream",
            refused=(Refused,),
            refused_seconds=REFUSED_WAIT,
            flush_seconds=FLUSH_SECONDS,
            **kwargs,
        )


def symbol_limit(feed: str) -> int | None:
    """How many listings one session may stream: IEX's 30 on a free account,
    SIP's no limit."""
    return IEX_SYMBOLS if feed == IEX else None
