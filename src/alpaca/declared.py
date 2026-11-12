"""What this version declares beside its role (W8.1, W4.1): its catalogue, its
settings and the storage it asks for.

Built from the plugin's code and used twice: `__main__` registers with it,
and `meridian plugin upload` reads the same one from the built image
(pyproject.toml's `[tool.meridian] declaration`).

**The catalogue** (contracts v18 and v19), three datasets apart, as the lake
plan's Q21 and Q40 have a source's daily and live data and its trades:

- `daily`: closes and daily bars, from Alpaca's consolidated (SIP) history;
  its day New York's, ending at the 16:00 close; pulled for a read and
  pushed once a session's close is final; about ten years of history (since
  2016). Not one venue's: the consolidated view. From 0.13.0 (contract v27)
  it declares its delay, 16 minutes (`declared_delay_ns`): SIP's history is
  asked past a free account's restricted latest 15 minutes, with a minute's
  margin, whatever the key's plan, so the day still forming is that far
  behind; staleness and age are judged against it.
- `live`: the latest trade's price and the best bid and ask, and from
  contract v19 the best bid and offer as a quote with its sizes, from SIP
  where the key has it in real time, else IEX; pulled for a read; while a
  standing want stands its prices kept current once a minute and its quotes
  streamed. Each row names the exchange it is from, resolved to the venue
  master's ID; the catalogue, written in code before any venue is resolved,
  names none. Real time (no declared delay): IEX's, or SIP's where the key
  has it in real time.
- `trades` (contract v19): each trade with its attributes, from the same
  feed, streamed for the listings under a standing want and pulled for a
  range; apart from the live prices (the plan's Q40), so an admin licenses
  and keeps them apart.

**Its terms and pricing** (contract 30, ruling 1032): no dataset declares a
licence. Each describes Alpaca's market data plans and terms in plain words
(`TERMS`): a non-professional subscriber receives market data "solely for
their personal, non-business use", nothing redistributed without Alpaca's
written consent. The deployment's admin sets the deployment's licence on
the Data sources page, which is the one enforced (one person's terms suit
it; the live dataset served and not kept, the trades kept two days, the
plan's Q40). A summary, not legal advice; the README says the same.

**How a gap is recovered** (W10.14): `daily` and `trades` are `backfill` --
Alpaca serves bars and trades back in time, and a want of a range is
answered from them; `live` is `stream_only` -- a quote or a latest price as
it stood is not served again. No sessions calendar: the platform holds no
US equity trading-sessions calendar yet (the daily dataset's `calendar_id`
is the trading calendar's). No `most_shards`.

**The storage**, at the edge (decisions/028): Alpaca's raw responses, every
row's raw record, and the product map. The account side keeps three kinds
of raw record (kinds.py), each with its own window an admin of the plugin
sets: `responses` (each read of the account, its positions and its orders,
30 days), `activity` (from 0.8.0, custody's: each page of the account's
activities, seven years) and `trading` (each exchange with the Trading API
that places, replaces or cancels, seven years), all archivable. The retention is the
longest window, the data role's raw responses kept within it.
"""

from __future__ import annotations

from meridian import DatasetDeclaration

from .convert import DAY_END_MINUTE
from .kinds import KINDS
from .lake import DAILY, LIVE, LIVE_CADENCE_SECONDS, TRADES
from .vendor import SIP_DELAY_NS

VENDOR = "Alpaca"
#: How long a raw record is kept at the most: the longest kind's window.
RETENTION_DAYS = max(kind.window_days for kind in KINDS)
#: Alpaca's consolidated history reaches back to 2016.
HISTORY_DAYS = 3650
#: Alpaca's market data plans and terms, in plain words (ruling 1032).
TERMS = (
    "Alpaca's Market Data API, read with the account's API key. Its Free plan ($0) serves IEX "
    "in real time and other data 15 minutes delayed, 200 calls a minute; Algo Trader Plus "
    "($99 a month) serves all US exchanges in real time, calls unlimited; both reach back "
    "seven years and more. A non-professional subscriber receives the data solely for "
    "personal, non-business use, and nothing is redistributed without Alpaca's written "
    "consent."
)

#: The platform's US equity venues (NYSE markets) calendar, read from the
#: platform on 2026-10-14 (the v24 plan's O10): the daily dataset's business
#: dates are the days it says US equity markets are open, so the lake flags a
#: close dated on a closed day (contract v24's `calendar_id`, which waited for
#: this plugin's move off the v23 pins).
US_EQUITY_CALENDAR = "CAL-01M4VF0F4XGP3RATCCSKDPZSBP"

CATALOGUE = (
    DatasetDeclaration(
        key=DAILY,
        vendor=VENDOR,
        data_types=[
            "meridian.v1.Price",
            "meridian.v1.Bar",
            "meridian.v1.Bar.vwap",
            "meridian.v1.Bar.trade_count",
        ],
        modes=["pull", "push"],
        cadence=86_400,
        history=HISTORY_DAYS,
        terms_and_pricing=TERMS,
        gap_recovery="backfill",
        day_time_zone="America/New_York",
        day_end_minute=DAY_END_MINUTE,
        calendar_id=US_EQUITY_CALENDAR,
        declared_delay_ns=SIP_DELAY_NS,
    ),
    DatasetDeclaration(
        key=LIVE,
        vendor=VENDOR,
        data_types=["meridian.v1.Price", "meridian.v1.Quote"],
        modes=["pull", "stream"],
        cadence=LIVE_CADENCE_SECONDS,
        terms_and_pricing=TERMS,
        gap_recovery="stream_only",
        day_time_zone="America/New_York",
        day_end_minute=DAY_END_MINUTE,
    ),
    DatasetDeclaration(
        key=TRADES,
        vendor=VENDOR,
        data_types=["meridian.v1.Trade"],
        modes=["pull", "stream"],
        terms_and_pricing=TERMS,
        gap_recovery="backfill",
        day_time_zone="America/New_York",
        day_end_minute=DAY_END_MINUTE,
    ),
)
