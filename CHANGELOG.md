# Changelog

## 0.12.1

- **Custody's pages on the SDK** (ruling 213): Account links, Statements and
  History are `meridian.roles.custody.account_pages(...)`, declared by the
  SDK; `custody_pages.py` keeps only what Alpaca's sync holds (its `Source`:
  the accounts the credential reaches, each one's statement and activities,
  its custodian and account type). Their paths, tools, records and words are
  as they were; the tools' descriptions are the SDK's. The plugin's own
  `LinkAsked` and its unchanged Statements and History templates are gone
  (the role's own are drawn); Account links keeps its template, for its
  notice and its plain form per account.
- **Connection fits one screen.** Its sections -- Key, Limits and use and
  Stream -- show one at a time under a tab row (`?tab=key`, `limits`,
  `stream`), so the page fits an 800-pixel screen with the stream's session
  showing (it ran to about 820-900 pixels). `read_connection` answers every
  section, as before.
- **The pins**: `meridian` 0.1.50, which reads the pages the SDK declares in
  `role-pages`; open-meridian 0.31.1 and plugin-python:0.31.1 by digest, as
  0.12.0.

## 0.12.0

On open-meridian 0.31.1, contract 26.

- **Environment's paper value is `paper`** ("Paper", Alpaca's own word;
  contract v26, G1 question 4): the setting is the SDK's
  `meridian.environment(demo="paper")`, Paper until a person chooses Live.
  **On upgrading, save Environment again as Paper:** a value saved before
  0.12.0 is `sandbox`, which is no longer a choice. On open-meridian 0.31.1
  it arrives unset and named in `Settings.refused`: the plugin reads
  Alpaca's paper API, Trading's badge is not Demo, and Trading and
  Connection say to save Environment again (`environment_to_save` in
  `read_trading` and `read_connection`).
- **The listings in the lake on the SDK** (ruling 213): `lake.py`, about
  1,170 lines kept nearly line for line with Tradier's, is now a subclass of
  open-meridian 0.31.0's `meridian.roles.data.listings.Feed` keeping only
  what is Alpaca's: its source's name, how far its history reaches, its
  trades' and quotes' conditions. Wants, standing wants, recording, the
  restart watermark and the counts are the SDK's; what is recorded is
  unchanged, and the data suite passes as before.
- **The custody slice waits for meridian 0.1.50.** The Account links,
  Statements and History pages stay in `custody_pages.py`: the SDK's
  `custody.account_pages` declares them inside the SDK, which meridian
  0.1.49's `role-pages` rule does not recognise yet, so `plugin check
  --verified` would fail. They move once 0.1.50 recognises it.
- **The session's reported environment** (contract v26, the agents'
  demo-only guard, spec/the-contract-gaps-v26-and-v27-close G1): the venue
  adapter reads the environment its session reached from the host it calls,
  `paper-api.alpaca.markets` `paper` and `api.alpaca.markets` `live`
  (`meridian.reached_environment`), and the SDK's Trader publishes it on the
  venue catalogue. The simulated brokerage reports `paper`. **Trading**
  shows the connection's badge, Demo, Live or Live (environment not
  confirmed) (`meridian.connection_badge`), and `read_trading` answers
  `reached_environment` and `badge` beside the role's fields.
- **The data suite's v26 cases.** `queries-the-lake-within-bounds` passes on
  the SDK's producer (`lake_query`); `reports-an-event-group` and
  `reports-a-flag-the-venue-does-not-state` are not presented, with why
  (Alpaca's stock data lists no event contract). The event group heard and
  read is the SDK's.
- **The pins**: open-meridian 0.31.1, as released on PyPI, and
  plugin-python:0.31.1 by tag and digest (`sha256:67781f14...a3535b39`); core
  v26's runtime and harness (17a13a2, merged as 648e25f, chart 0.1.308), by
  tag and digest; `meridian` 0.1.49, the first CLI holding contract v26's
  suites.
- **Tests**: the catalogue's environment, the environment read from each
  host, the badge on Trading and in its tool, and the data suite's new
  cases, on the simulated brokerage and recorded exchanges; nothing reaches
  Alpaca.

## 0.11.0 (2026-10-19)

On open-meridian 0.30.0, contract 25 unchanged: the connectivity role's work
is the SDK's (sdk-contract/the-sdk-carries-each-roles-common-logic, ruled
2026-10-13; ruling 206).

- **Trading on the SDK's Trader** (`meridian.roles.connectivity`): the
  plugin's `trading.py` (about 1,800 lines, kept nearly line for line with
  Tradier's) is gone. Placements heard and sent once, outcomes, fills
  into the book, busts, cancels and replaces, pauses and stops, the catalogue
  and venue-originated fills are the SDK's `Trader`, handed this plugin's
  adapter (`venue.py`) and the listing market's zone (`custody.MARKET_ZONE`,
  America/New_York). Alpaca's client (`broker.py`) and its conversion stay
  the plugin's, as transport.
- **The Trading page** answers the SDK's `trading_read`, drawn by
  `meridian/roles/connectivity/trading.html`; its records and
  `templates/trading.html` are gone. Its tools, rows and labels are as they
  were ("Trade updates", "Not streaming" passed to the template); the next
  step reads "No key yet: Enter it in Settings".
- **Its tests** run the plugin's adapter over the simulated brokerage on the
  SDK's rig (`meridian.roles.connectivity.testing.Rig`); simulated only,
  nothing reaches Alpaca.
- **The pins**: open-meridian 0.30.0, as released on PyPI, and
  plugin-python:0.30.0 by tag and digest
  (`sha256:a238c6d9...3473ed6`) in the Dockerfile, which `make image` now
  builds on as an upload does; core v25's runtime and harness (abf028f) and
  `meridian` 0.1.46 as before.
- **Fixed: a symbol Alpaca calls invalid is declined, not asked again.**
  Alpaca answers a call naming a symbol it cannot take (a plan fund's code,
  TCH4 on the dev deployment) with a 400, "invalid symbol: TCH4", for the
  whole call. The source failed each time, its subjects were declined as
  unsettled, and the bars were asked again about once a minute. Now the
  symbol is kept as invalid, the call asked again without it, and its
  subjects declined `not_covered` once for the date (the contract's decline
  path); it is not asked of Alpaca again while the plugin runs.
- **Fixed: why the trade updates stopped is said.** A stream silent for ten
  minutes logged "the trade updates stopped ()": a bare TimeoutError has no
  message. The log and the Trading page now give the failure's type and
  message ("TimeoutError: nothing heard for 600s", or a close's code and
  reason), never the key; so do the other streams' restarts.

## 0.10.0 (unreleased)

On open-meridian 0.29.0, contract 25 (sdk-contract/plugins-are-shared-and-
documented-contract), the v25 build's step 8; past contract 24, which this
plugin skipped on the v23 pins.

- **The whole declaration** (`declaration.py`): its settings, its interface
  -- Connection, Datasets, Account links, Statements, History, Trading and
  Raw records, with the tools their routes make -- on a port fixed at 8000,
  that it reads external accounts, its catalogue and storage, and its
  documentation. `__main__` connects with the declaration alone; so do the
  e2e's desk and reader. The parts the pages import moved to `declared.py`.
- **The daily dataset names its calendar** (contract 24's `calendar_id`,
  the v24 plan's O10): the platform's US equity venues calendar,
  `CAL-01M4VF0F4XGP3RATCCSKDPZSBP`, so the lake flags a close dated on a
  closed day.
- **Its documentation** (`docs/`): the drafts revised for all three roles --
  the account at Alpaca, its orders, Account links, Statements, History,
  Trading and Raw records added; the data and custody roles' pages linked;
  "a later version" for the account removed.
- **The suites**: custody's v24 case, a holding named by its symbol alone,
  recorded unresolved; connectivity's give-up case not presented (no trade
  is given up at Alpaca); the two cases every suite holds answered by the SDK.
- **The pins**: open-meridian 0.29.0 and plugin-python:0.29.0, core v25's
  runtime and harness, and `meridian` 0.1.46 in `check.yaml`, each as released
  (core abf028f, chart 0.1.306, by tag and digest).
- **`make e2e`** takes the harness down with `--profile runner`.

## 0.9.0 (unreleased)

0.8.1 was never released: its fix ships as 0.9.0 (the v24 plan's O5), on
the v23 pins (open-meridian 0.27.0, core 50d6f0a's runtime and harness),
since nothing here needs contract 24 (the product owner, 2026-10-14). The
daily dataset's calendar waits for v25: open-meridian 0.28.0 is the first SDK
whose DatasetDeclaration carries `calendar_id`.

- **Live is a person's choice.** `environment` defaults to `sandbox`,
  Alpaca's paper trading API, not `live`: an upgrade, or an Environment
  never saved, no longer turns the plugin Live. Over a deployment that
  never saved one, 0.8.0 came up on Live, where Alpaca's live Trading API
  refuses a paper account's key (40110000). Its description says Live is
  chosen by a person (the product owner, 2026-10-14).
- Nothing else changes. Tests: an unset environment is the sandbox, and
  Live only once chosen.

## 0.8.0 (unreleased)

- On open-meridian 0.27.0 (contract 23): the pins moved as the SDK's
  0.26.0 to 0.27.0 step moves them; meridian 0.1.43's checks.
- The `custody` role, beside `data` and `connectivity`, in SnapTrade
  0.16.0's shape: the account Alpaca's key reaches (`/v2/account`), its
  positions (`/v2/positions`) and its activities (`/v2/account/activities`),
  read every **Read every**, reported in the contract's words: the account,
  margin by its margin classification; its sync state; a statement as of
  the day in New York, a row per position and the cash, the settled
  quantity and pending lines derived from the account's unsettled fills and
  the deployment's settlement dates; every activity, converted to its kind
  or kept as reported, a fill's amount derived. Alpaca states the currency
  of every amount by its account's (USD), read as the product owner ruled
  for OANDA's account; each resolve offers it with its provenance reported
  from the account's raw record (`ResolveIdentifierRequest.provenance`).
- Custody's pages: **Account links** (`read_account_links`, `link_account`,
  checked by `check_link_account`), **Statements** (`read_statements`) and
  **History** (`read_account_activities`); **Raw records** serves custody
  too. Settings: custody's **Read every** and **Stale after**. A third kind
  of raw record, `activity` (2555 days), SnapTrade's.
- Connectivity, contract 23: an order placed in Alpaca's own app has its
  fills reported on no placement, held unmatched until the desk's `ems`
  accepts or answers them DK; the accept's placement takes the order's
  later fills. Only fills after the plugin first watched the account are
  reported (`trading/originated.json`). The catalogue's
  `execution_acknowledgement` is none: Alpaca takes none, so a DK tells it
  nothing. Every fill names Alpaca's order ID.
- The suites: custody passes every case but 12 Alpaca never presents, each
  with why; connectivity passes every case but 10 not presented, among them
  `reports-a-charge` (`about: charges without a fill`) and v23's charge
  re-reported on an accepted placement and value-date roll; data marks
  v23's three outcome cases not presented. No suite test is skipped or
  expected to fail.
- `make e2e`: Alpaca's account linked to the e2e's account, its opening
  balance recorded from Alpaca's statement by the desk (now holding
  `operations` too); an order placed in Alpaca's app reported on no
  placement and accepted to a new order; and after every fill, the book
  reconciled against Alpaca's statement with no break.

## 0.7.0 (unreleased)

- The `connectivity` role (contract 22), beside `data`, in SnapTrade
  0.16.0's shape: the plugin places the placements naming its instance at
  Alpaca's Trading API, in the account its `ems` mapped
  (`AccountScope.venue_account_map`), with the placement's ID as the client
  order ID, and reports acknowledgements, rejections (`unsupported` with
  nothing sent, or `venue rejected` with Alpaca's code and words),
  replaces, restatements, cancels, expiries, done for day, fills and busts,
  each with its raw record. A status the mapping does not know is outcome
  unknown and resolved by reading; a send never answered is asked about,
  never sent again, across a restart (`trading/sent.json`).
- Fills: as Alpaca states them on its trade updates stream, and inferred
  from the orders read every 15 seconds besides, each derived to the same ID
  (the order and the filled quantity it brought it to); every fill's
  settlement date is the deployment's (ComputeDate, with its basis), since
  Alpaca states none.
- Cancel and replace read from `Placement.change_requests`; a replace is
  Alpaca's `PATCH`, its new order followed. Pauses and stops honoured, a
  stop's cancels reported naming its entry.
- The venue catalogue per venue account code: none on a read-only account;
  once trading is enabled on it by the connectivity role's admin
  (**Trading**, `enable_trading`, at `/admin/connections/enable-trading`),
  Alpaca's order types and times in force.
- Settings: `environment` (`live`, or `sandbox`: Alpaca's paper trading
  API), first; the key and sample data now serve both roles. The key's
  value carries over.
- Two kinds of raw record, each with its window an admin sets: `responses`
  (30 days) and `trading` (2555 days), archivable; **Raw records** follows
  a fact's reference.
- The connectivity suite: 19 cases pass; 7 are not presented, each with
  why (calendars, locates, a fill's place of execution, compliance waits);
  `reports-a-charge` is not produced, Alpaca stating no fee on a placement
  that filled nothing (for the product owner to rule on).
- `make e2e` runs the order path after the data steps (e2e/orders.py),
  with a stand-in desk (e2e/desk.py), against a simulated brokerage
  (src/alpaca/synthetic_broker.py). Nothing reaches Alpaca's trading API.

## 0.6.0 (unreleased)

- On open-meridian 0.26.0 (contract 22): the pins moved as the SDK's
  0.25.0 to 0.26.0 step (`meridian plugin migrate --to 0.26.0`) moves them,
  rewriting nothing. Contract 22 is the order path and settlement
  calendars; this plugin places no order and works out no date, so nothing
  else changes.
- The data suite's two calendar cases (`reads-a-calendar`,
  `asks-for-a-settlement-date`) are not presented, each with why: Alpaca's
  bars are dated as Alpaca states them, and nothing here needs a
  settlement calendar or a settlement date.
- AGENTS.md says to name a declared algorithm on autonomous work, and to
  work out a date in core (`compute_date`, `read_calendar`), never by hand.

## 0.5.0 (unreleased)

- On open-meridian 0.25.0 (contract 21): the pins moved as the SDK's
  0.24.0 to 0.25.0 step (`meridian plugin migrate --to 0.25.0`) moves them,
  rewriting nothing. Contract 21 lets a plugin's
  autonomous work act as its role's service account; this plugin acts on
  nothing of the deployment's by itself, so nothing else changes.
- AGENTS.md says how a plugin acts on its own: only as its role's service
  account, through `meridian.runs_as(role)`.

## 0.4.0 (unreleased)

- On open-meridian 0.24.0 (contract 20): the role is `data` (a data
  plugin), `dgm` until now.
- Connection and Datasets are the data role's pages
  (spec/plugin-pages-follow-their-role): Connection's "Key", "Limits and
  use" and "Stream", Datasets' "Served", "Wants" and "Subjects", in the
  role's order and words, with Alpaca's feeds, stream session, feed column
  and "Kept current" at the role's extension points; the "not set up yet"
  states ("No key yet", linking to Settings; "No wants yet"); and
  `read_connection` and `read_datasets` answering the role's common fields
  with Alpaca's beside. The data role's figures on the Summary.
- Datasets says whether a deployment admin has licensed each dataset,
  read from the deployment on start and every minute.
- A restart's gap backfilled: the first time a listing's trades are wanted
  after a restart, the trades since the last one recorded, from Alpaca's
  history, two days back at most.
- The setting `synthetic` is `sample_data` (Sample data), the SDK's.
- Fixed: whether the key has SIP in real time is asked by SIP's trades of
  the last minute, not by a latest quote, and a SIP refusal falls back to
  IEX: the latest quotes come from the feed the key is entitled to (IEX on
  a free or a paper key). The refused probe is no longer the Connection
  page's last error.
- Fixed: a symbol Alpaca has nothing for (TCH4) is declined once for the
  date, not asked and declined again every minute.
- The data suite's v20 cases: a trade recorded, a restart's gap backfilled
  and its datasets' licences read, presented; the taker's side and the
  maker's side inverted not presented (Alpaca states no aggressor).

## 0.3.0 (unreleased)

- On open-meridian 0.23.0 (contract 19): the lake's trades and quotes.
- `trades`, a new dataset: each trade with the platform's trade attributes,
  converted from its conditions on its tape (CTA's and UTP's letters), a
  code with no conversion kept as reported; no aggressor, which Alpaca never
  states; a cancel, an error or a correction the trade's next version.
  Streamed for the listings under a standing want, pulled for a range;
  kept two days by default.
- `live` gains quotes: the best bid and offer with its sizes, one side
  empty where Alpaca sends none, streamed at most once a second a listing.
- Alpaca's stream over WebSocket (the standard library's own client), with
  reconnect, subscriptions made again from the standing wants, and the gap
  caught up from Alpaca's trade history; a free account's 30
  listings kept to, the rest declined, not entitled.
- Fixed: a second record of one listing is recorded under its own row key
  (the key names the record, `SPY:1d:2026-10-08@LCL-...`), not under the
  first's, which the lake versioned as a restatement; a day read again
  unchanged keeps its raw record, so the lake keeps it unchanged. Rows
  recorded by 0.2.0 keep their keys.
- The SDK's suite with its 1b cases: four not presented, each with why.
- Connection shows the stream; Datasets searches and pages the standing
  wants (kit 0.11.0).

## 0.2.0 (unreleased)

- A `dgm` on open-meridian 0.22.0 (contract 18): the catalogue's `daily`
  (closes and daily bars from SIP, New York's day to the 16:00 close, pulled
  and pushed) and `live` (last, bid and ask, SIP in real time where the key
  has it, else IEX; pulled and kept current while a standing want stands),
  each with Alpaca's personal-use terms as its default licence.
- Wants answered or declined per subject; a forming day restated under one
  row key until final; listings resolved by Alpaca's symbol, venues by
  Alpaca's exchange letter, misses reported.
- An instrument the book holds from another source, known only by that
  source's identifiers (a custodian's symbol and CUSIP), read from its
  record and priced under Alpaca's symbol.
- Connection and Datasets under Manage, each a read tool
  (`read_connection`, `read_datasets`).
- The SDK's `dgm` suite, unchanged; an e2e on core's plugin harness with the
  synthetic exchange, and `make e2e-recorded` with a developer's recording;
  `make live`, the account holder's live check.

## 0.1.0

- The spike: connectivity and conversion against Alpaca's Market Data API
  v2, before the lake's contract (open-meridian 0.18.0). Its live check
  passed on 2026-10-05.