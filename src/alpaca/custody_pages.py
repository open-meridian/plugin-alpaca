"""Custody's pages, from 0.8.0 (spec/plugin-pages-follow-their-role,
`meridian.roles.custody`), each the same answer as its tool; from SDK 0.31.0
the SDK's (`custody.account_pages`), this module supplying what is Alpaca's
alone; from 0.13.0 in the role's own templates, Account links' notice and
plain form per account the SDK's too (0.32.0). Raw records, which serves
both roles, is the SDK's (page.py).

- Account links (`/links`, Manage; custody): `read_account_links`, linking
  with `link_account` (checked by `check_link_account`) the account the key
  reaches, its custodian and type pre-filled: Alpaca, margin.
- Statements (`/statements`) and History (`/history`), Open and View.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from meridian.roles import custody

from .custody import institution
from .page import current, pages

LINKS, STATEMENTS, HISTORY = custody.ACCOUNT_LINKS, custody.STATEMENTS, custody.HISTORY
WHAT = "This plugin brings an Alpaca account into this deployment"
#: The type a new account is pre-filled with: every Alpaca account is margin.
ACCOUNT_TYPE = "margin"


class Source:
    """What Alpaca's sync holds, as custody's pages read it."""

    vendor = "Alpaca"
    credential = "key"

    def _paper(self) -> bool:
        config = current().config
        return bool(config.paper and not config.sample_data)

    def reached(self) -> Sequence[str]:
        syncer = current().syncer
        number = syncer.status.number if syncer is not None else ""
        return [number] if number else []

    def account(self, number: str) -> custody.ExternalAccountRead:
        return custody.ExternalAccountRead(
            number,
            f"Alpaca {'paper' if self._paper() else 'live'} {number}",
            f"{institution(self._paper())}, {ACCOUNT_TYPE}",
        )

    def custodian(self) -> str:
        return institution(self._paper())

    def account_type(self, number: str) -> str:
        return ACCOUNT_TYPE

    def statement(self, number: str) -> tuple[str, str] | None:
        syncer = current().syncer
        if syncer is None or syncer.status.number != number:
            return None
        status = syncer.status
        return (
            status.statement_as_of,
            f"{status.statement_state or 'Not read yet'} ({status.state})",
        )

    def activities(self, number: str) -> Sequence[tuple[Any, str]]:
        syncer = current().syncer
        if syncer is None or syncer.status.number != number:
            return []
        return list(syncer.status.activities)

    def links(self) -> Sequence[Any]:
        return current().scope.links


# Account links, Statements and History in the role's templates.
custody.account_pages(pages, Source, what=WHAT)
