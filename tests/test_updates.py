"""Alpaca's trade updates stream (updates.py) on a stand-in socket: why it
stopped is said, in the log and on the Trading page, by the failure's type
and message (a silence's length, a close's code and reason), never the key.
Nothing reaches Alpaca."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from alpaca import updates, ws
from alpaca.settings import Credentials
from alpaca.updates import AlpacaUpdates, described

KEY = Credentials("PKTESTKEYID", "test-secret-not-real")
AUTHORIZED = json.dumps(
    {"stream": "authorization", "data": {"status": "authorized", "action": "authenticate"}}
)


class Socket:
    """Alpaca's stream as far as authorizing the key; then `then`: silence,
    or a failure raised."""

    def __init__(self, then: BaseException | None) -> None:
        self.then = then
        self.sent: list[str] = []
        self.heard = 0

    async def send(self, text: str) -> None:
        self.sent.append(text)

    async def recv(self) -> str:
        self.heard += 1
        if self.heard == 1:
            return AUTHORIZED
        if self.then is not None:
            raise self.then
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")

    async def close(self) -> None:
        return None


async def stopped_once(then: BaseException | None) -> AlpacaUpdates:
    """The stream run until it has stopped once, then cancelled."""
    socket = Socket(then)

    async def connect(_: str) -> Socket:
        return socket

    stream = AlpacaUpdates(KEY, "wss://paper-api.alpaca.markets/stream", connect)
    task = asyncio.create_task(stream.run(None, None))  # type: ignore[arg-type]
    for _ in range(200):
        if stream.state == "waiting":
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    return stream


def logged(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(r.getMessage() for r in caplog.records if r.name == "alpaca.updates")


async def test_a_silent_stream_is_said_to_have_stopped_for_its_silence(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The dev deployment's "the trade updates stopped ()": a stream silent
    past SILENT_SECONDS, whose bare TimeoutError said nothing."""
    monkeypatch.setattr(updates, "SILENT_SECONDS", 0.05)
    caplog.set_level(logging.WARNING, logger="alpaca.updates")
    stream = await stopped_once(None)
    said = logged(caplog)
    assert "the trade updates stopped (TimeoutError: nothing heard for 0s)" in said
    assert stream.last_error == "TimeoutError: nothing heard for 0s"
    assert "()" not in said and KEY.secret_key not in said and KEY.key_id not in said


async def test_a_closed_stream_is_said_with_its_code_and_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="alpaca.updates")
    closed = ws.Closed("the server closed the connection: 1008 policy violation")
    stream = await stopped_once(closed)
    said = logged(caplog)
    assert "stopped (Closed: the server closed the connection: 1008 policy violation)" in said
    assert stream.last_error.startswith("Closed: the server closed the connection: 1008")
    assert KEY.secret_key not in said and KEY.secret_key not in stream.last_error


def test_a_failure_with_no_message_is_named_by_its_type() -> None:
    assert described(TimeoutError()) == "TimeoutError"
    assert described(OSError("no route to host")) == "OSError: no route to host"
    assert described(ValueError("Expecting value")) == "ValueError: Expecting value"
