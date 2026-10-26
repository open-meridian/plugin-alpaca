"""The data suite, the SDK's own (meridian.suites; contract v23 from 0.8.0),
run unchanged against this plugin: every case mapped to the plugin's own
conversion, from Alpaca's recorded exchange and stream, through the lake's half it runs in
production (lake.py), against the suite's `Recorder`.

Nineteen cases are not presented, each with why (`NOT_PRESENTED`). Two are
about kinds of data Alpaca's US stock data never publishes (`about`, from
contract v19): a currency's rate against another currency, and a crypto
asset's price (its crypto is left to the crypto pair). Two are about a field
its trades never state (`about_field`, from contract v20): the side that
took liquidity (`meridian.v1.Trade.aggressor`), which the contract never
guesses from the price -- a regular trade naming the taker's side, and a
maker's side inverted. And two are contract v22's calendar cases (`about`
calendars and settlement dates): the plugin dates a bar by the session's
close in New York as Alpaca states it, and never reads a settlement calendar
or asks for a settlement date. And from contract v23, three are about an
event contract's outcomes (`about` outcomes), which Alpaca's stock data never
states. Every other case about trades is presented.

From contract v26, two more are about outcomes: an event's group, and a flag
the venue leaves unstated. `queries-the-lake-within-bounds` is mapped as
the SDK's data template maps it: one bounded query of a kind the role
reads, trades, of a listing it records (`lake_query`); the plugin itself
asks the lake nothing. The event group heard and read is the SDK's.

From contract v27, the seven rates cases (`about` rates), which Alpaca's
stock data never publishes. From contract v28 the feed delay (required
again, ruling 518) and a crossed quote (ruling 424) are presented, on
quotes streamed for a standing want, aged and judged at the edge (lake.py);
the chains, filings, holdings, dividend and rating cases are not, nor the
duplicate and gap cases (Alpaca numbers no quote). The stream's
liveness is presented: from open-meridian 0.32.3 the listings feed records
it for any message heard, a listing's trading status among them.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data.testing import RATES_CASES, feed_delay, lake_query
from meridian.suites import Recorder, run

from alpaca import convert
from alpaca.lake import LIVE_KINDS, Standing

from conftest import (
    BRK,
    ISIN_ONLY,
    RECORDS,
    SPY,
    TQQQ,
    Clock,
    answer_records,
    at,
    synthetic_lake,
    want,
)

DAY = "2026-10-08"
#: Saturday morning after the synthetic week: every day of it final.
AFTER = at("2026-10-10", 9)
#: Thursday 2026-10-09, 15:00 New York: the session still open.
DURING = at("2026-10-09", 15)

Producer = Callable[[Recorder], Awaitable[None]]

#: Contract v28's cases Alpaca's stock data never presents (ruling 602), each
#: group with why. Named through this table, not as literal keys, because
#: meridian 0.1.52's check, which CI pins until the builder moves to 0.1.53,
#: holds contract v27's suites and refuses a v28 case name it does not know.
V28_NOT_PRESENTED: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("records-a-chains-series", "records-open-interest", "a-chain-row-is-never-resolved"),
        "Alpaca's stock data here lists no option chain",
    ),
    (
        ("a-filing-recorded", "a-fact-restated", "a-fact-confirmed", "resolves-a-filer"),
        "Alpaca's market data publishes no filings",
    ),
    (
        ("a-complete-holdings-report", "a-cusip-used-as-key", "a-stake-crossed"),
        "Alpaca's market data publishes no holdings report",
    ),
    (
        ("a-dividend-declared",),
        "this plugin reads no corporate action from Alpaca: no declared dividend",
    ),
    (("a-rating-action",), "Alpaca's market data states no rating"),
    (
        ("a-duplicate-is-recorded-suspicious", "rows-after-a-gap-are-suspicious"),
        "Alpaca's stream numbers no quote: no sequence to repeat or skip",
    ),
)

#: The cases Alpaca's stock data does not present, and why (above).
NOT_PRESENTED = {
    "an-fx-rate": "Alpaca's US stock data states no currency's rate against another",
    "a-stablecoin-quote": "a data plugin of US stocks: Alpaca's crypto is the crypto pair's",
    "the-takers-side-stated": "Alpaca's stock trades never state which side took liquidity",
    "the-makers-side-inverted": "Alpaca's stock trades state neither side of a trade",
    "reads-a-calendar": (
        "dates each bar by the session's close as Alpaca states it: reads no settlement calendar"
    ),
    "asks-for-a-settlement-date": (
        "records bars and trades as Alpaca publishes them; never computes a settlement date"
    ),
    "records-an-outcome": "Alpaca's stock data lists no event contract, so states no outcome",
    "restates-a-disputed-outcome": (
        "Alpaca's stock data lists no event contract, so states no outcome"
    ),
    "records-a-partial-payout": "Alpaca's stock data lists no event contract, so states no outcome",
    # Contract v26: an event's group and the flags a venue leaves unstated are
    # about outcomes too.
    "reports-an-event-group": "Alpaca's stock data lists no event contract: no event to group",
    "reports-a-flag-the-venue-does-not-state": (
        "Alpaca's stock data lists no event contract: no event whose flags go unstated"
    ),
    # Contract v27: the rates slice (about rates).
    **{case: "Alpaca's US stock data publishes no rates" for case in RATES_CASES},
    # Contract v28 (ruling 602), named through V28_NOT_PRESENTED: meridian
    # 0.1.52's check holds contract v27's suites.
    **{case: why for cases, why in V28_NOT_PRESENTED for case in cases},
}

#: A moment in the session, for the stream's messages.
LIVE_AT = "2026-10-09T15:30:00.123456789Z"


#: The fields Alpaca sends as numbers.
NUMBERS = frozenset({"i", "p", "s", "bp", "bs", "ap", "as"})


def message(**fields: Any) -> dict[str, Any]:
    """One of Alpaca's stream messages, its numbers parsed as Alpaca's are:
    each from its own text, a Decimal where it has a point."""
    said = {"t": LIVE_AT, "z": "B", "x": "V", **fields}
    text = (
        "{"
        + ",".join(
            f"{json.dumps(k)}:{v if k in NUMBERS else json.dumps(v)}" for k, v in said.items()
        )
        + "}"
    )
    return dict(json.loads(text, parse_float=Decimal))


def producers(tmp: Path) -> dict[str, Producer]:
    def lake(recorder: Recorder, now: int = AFTER):  # type: ignore[no-untyped-def]
        answer_records(recorder, RECORDS)
        return synthetic_lake(recorder, Clock(now), tmp / uuid.uuid4().hex)

    async def wanted(recorder: Recorder, event: ops.ObservationsWantedEvent) -> None:
        held = lake(recorder)
        recorder.answer("ObservationsWanted", lambda _: event)
        await recorder.receive(observations_wanted=held.on_want)

    async def daily_close(recorder: Recorder) -> None:
        # The plugin resolves a listing by its own symbol, then records the
        # close the lake wants for it.
        held = lake(recorder)
        await held.seed(["BRK.B"])
        (subject,) = held.products.symbols
        recorder.answer("ObservationsWanted", lambda _: want(subject, business_date=DAY))
        await recorder.receive(observations_wanted=held.on_want)

    async def forming(recorder: Recorder) -> None:
        clock = Clock(DURING)
        answer_records(recorder, RECORDS)
        held = synthetic_lake(recorder, clock, tmp / "forming")
        await held.daily([SPY], dt.date(2026, 10, 9), dt.date(2026, 10, 9))
        clock.now = at("2026-10-09", 16, 30)
        await held.tick()

    async def exact(recorder: Recorder) -> None:
        # TQQQ's close on 2026-10-09 is stated to eighteen places.
        await wanted(recorder, want(TQQQ, business_date="2026-10-09"))

    async def bar(recorder: Recorder) -> None:
        # BRK.B's bars state no VWAP.
        await wanted(recorder, want(BRK, data_type="meridian.v1.Bar", business_date=DAY))

    async def streamed(
        recorder: Recorder, *messages: dict[str, Any], subject: str = SPY, latency: Any = None
    ) -> None:
        # A standing want of the trades: the listing streamed, and what the
        # stream states recorded, as the plugin's stream hands it on.
        held = lake(recorder, DURING)
        held.latency = latency
        event = want(
            subject, dataset="suite-plugin:trades", data_type="meridian.v1.Trade", standing=True
        )
        recorder.answer("ObservationsWanted", lambda _: event)
        await recorder.receive(observations_wanted=held.on_want)
        for n, said in enumerate(messages):
            await held.heard(convert.streamed(said, f"stream/iex/suite#{n}", "iex"))
        await held.flush(force=True)

    async def condition(recorder: Recorder) -> None:
        # An odd lot on tape B: the CTA's `I`.
        await streamed(recorder, message(T="t", S="SPY", i=7, p="575.45", s=7, c=["@", "I"]))

    async def not_converted(recorder: Recorder) -> None:
        await streamed(recorder, message(T="t", S="SPY", i=8, p="575.46", s=50, c=["@", "~"]))

    async def withdrawn_trade(recorder: Recorder) -> None:
        stated = message(T="t", S="SPY", i=9, p="575.47", s=100, c=["@"])
        cancel = message(T="x", S="SPY", i=9, p="575.47", s=100, a="C")
        await streamed(recorder, stated, cancel)

    async def alive(recorder: Recorder) -> None:
        # Contract v27 (0.32.3's listings feed): a stream message with no price
        # changed -- a listing's trading status -- is the live dataset's
        # liveness.
        await streamed(recorder, message(T="s", S="SPY", sc="T", sm="Trading"))

    async def quote(recorder: Recorder) -> None:
        await streamed(
            recorder,
            message(
                T="q",
                S="SPY",
                bx="V",
                bp="575.43",
                bs=200,
                ax="V",
                ap="575.46",
                **{"as": 300},
                c=["R"],
            ),
        )

    def spy_quote(bid: str, ask: str) -> dict[str, Any]:
        return message(
            T="q", S="SPY", bx="V", bp=bid, bs=200, ax="V", ap=ask, **{"as": 300}, c=["R"]
        )

    async def delayed(recorder: Recorder, latency: Any) -> None:
        # Contract v28 (ruling 518): a streamed quote's age at the edge,
        # recorded and reported.
        await streamed(recorder, spy_quote("575.43", "575.46"), latency=latency)

    async def crossed(recorder: Recorder) -> None:
        # Contract v28 (ruling 424): the bid above the offer, recorded invalid.
        await streamed(recorder, spy_quote("575.49", "575.46"))

    async def one_sided(recorder: Recorder) -> None:
        # BRK.B's offer side empty: Alpaca sends it as 0.
        await streamed(
            recorder,
            message(
                T="q",
                S="BRK.B",
                bx="V",
                bp="455.30",
                bs=100,
                ax="V",
                ap=0,
                **{"as": 0},
                c=["R"],
                z="A",
            ),
            subject=BRK,
        )

    async def standing_streamed(recorder: Recorder) -> None:
        await streamed(recorder, message(T="t", S="SPY", i=10, p="575.48", s=100, c=["@"]))

    async def ambiguous(recorder: Recorder) -> None:
        # The listing's symbol meets two of the deployment's records.
        held = lake(recorder)
        recorder.answer(
            "ResolveIdentifier",
            lambda _: ops.ResolveIdentifierResult(
                found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS
            ),
        )
        await held.seed(["TQQQ"])

    async def venue(recorder: Recorder) -> None:
        # SPY's latest trade printed on IEX, Alpaca's letter V, which the
        # venue master holds as Alpaca's code.
        await wanted(recorder, want(SPY, dataset="suite-plugin:live"))

    async def venue_not_held(recorder: Recorder) -> None:
        held = lake(recorder)
        recorder.answer(
            "ResolveVenue",
            lambda _: ops.ResolveVenueResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND),
        )
        recorder.answer("ObservationsWanted", lambda _: want(SPY, dataset="suite-plugin:live"))
        await recorder.receive(observations_wanted=held.on_want)

    async def recorded_against(recorder: Recorder) -> None:
        await wanted(recorder, want(SPY, business_date=DAY))

    async def elsewhere(recorder: Recorder) -> None:
        # TQQQ as a custodian's book holds it, by its CUSIP and the
        # custodian's symbol: the record read (W3.6), Alpaca's symbol found.
        await wanted(recorder, want(TQQQ, business_date=DAY))

    async def declined(recorder: Recorder) -> None:
        await wanted(recorder, want(ISIN_ONLY, business_date=DAY))

    async def restarted(recorder: Recorder) -> None:
        # The plugin starts again; the lake holds the last trade of SPY it
        # recorded, at 15:59:00, and Alpaca's history states two since. The
        # first standing want of SPY's trades backfills them, then streams.
        held = lake(recorder, at("2026-10-09", 16, 5))
        last = ops.Trade(
            meta=ops.ObservationMeta(
                row_key="SPY:52983525029000@LCL-SPY",
                subjects=[ops.SubjectRef(entity_id=SPY)],
                source=ops.Source(dataset="suite-plugin:trades"),
                valid_from_ns=at("2026-10-09", 15, 59),
            )
        )
        recorder.answer("ListTrades", lambda _: ops.ListTradesResult(trades=[last]))
        event = want(
            SPY, dataset="suite-plugin:trades", data_type="meridian.v1.Trade", standing=True
        )
        recorder.answer("ObservationsWanted", lambda _: event)
        await recorder.receive(observations_wanted=held.on_want)

    async def licences(recorder: Recorder) -> None:
        # On start, its own declared datasets' licences (contract v20).
        from alpaca.__main__ import read_licences
        from alpaca.page import State

        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(
                licences=[ops.DatasetLicence(dataset="suite-plugin:daily", kept=True)]
            ),
        )
        state = State()
        await read_licences(recorder, state)
        assert state.licensed == {"suite-plugin:daily"}

    async def withdrawn(recorder: Recorder) -> None:
        clock = Clock(AFTER)
        answer_records(recorder, RECORDS)
        held = synthetic_lake(recorder, clock, tmp / "withdrawn")
        held.standing["WNT-9"] = Standing("WNT-9", (SPY,), LIVE_KINDS, AFTER)
        recorder.answer(
            "WantWithdrawn",
            lambda _: [ops.WantWithdrawnEvent(want_id="WNT-9", dataset="suite-plugin:live")],
        )
        await recorder.receive(want_withdrawn=held.on_withdrawn)
        clock.now += 3600 * 10**9
        await held.tick()

    return {
        "a-daily-close": daily_close,
        "the-forming-day-restated": forming,
        "an-exact-price": exact,
        "a-daily-bar": bar,
        "an-asset-that-does-not-resolve": ambiguous,
        "a-venue-resolved": venue,
        "a-venue-not-held": venue_not_held,
        "a-want-recorded-against": recorded_against,
        "a-subject-another-source-resolved": elsewhere,
        "a-subject-declined": declined,
        "a-standing-want-withdrawn": withdrawn,
        "a-condition-converted": condition,
        "a-condition-not-converted": not_converted,
        "a-trade-withdrawn": withdrawn_trade,
        "a-quote-recorded": quote,
        "reports-its-feed-delay": feed_delay(delayed),
        "a-crossed-quote-is-recorded-invalid": crossed,
        "records-a-datasets-liveness": alive,
        "a-one-sided-quote": one_sided,
        "a-standing-want-streamed": standing_streamed,
        "a-trade-recorded": standing_streamed,
        "a-restarts-gap-backfilled": restarted,
        "reads-its-datasets-licences": licences,
        # Contract v26: one bounded query of a kind the role reads, of a
        # listing it records, as the SDK's data template maps it.
        "queries-the-lake-within-bounds": lake_query(SPY, "trades"),
    }


def test_the_data_suite_passes_unchanged(tmp_path: Path) -> None:
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED)
    assert report.passed, report.failures
    # Contract v24: and the two cases every suite holds, which the SDK answers.
    # Contract v26: the bounded lake query, and the event group the SDK answers.
    # Contract v28: the feed delay and a crossed quote too.
    assert len(report.passed_cases) == 27
    assert report.answered_by_sdk == [
        "hears-and-reads-a-replacement",
        "reads-the-template-catalogue",
        "hears-and-reads-an-event-group",
    ]
    assert sorted(report.not_presented) == sorted(NOT_PRESENTED)


def test_a_price_read_through_a_float_fails_the_suite(tmp_path: Path, restore_parse: None) -> None:
    import json

    import alpaca.vendor as vendor

    vendor.parse = lambda text: json.loads(text, parse_float=float)
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED)
    assert "an-exact-price" in report.failures, report.failures
