"""Storage read once the plugin has registered (open-meridian 0.37.0): on an
instance run as shards or with a standby pod, its shard's own folder."""

from __future__ import annotations

from pathlib import Path

import pytest
from meridian import edge

from alpaca.__main__ import Custodian, Market, Process, Trading


def test_storage_read_once_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Built before Register, as `main()` builds them, the classes read no
    storage: read then, it raises. Registered as shard 1, the first settings
    or a class's start reads its folder; registered again as shard 0, that
    one's."""
    monkeypatch.setenv("MERIDIAN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("MERIDIAN_PLUGIN_SHARDS", "2")
    monkeypatch.setattr(edge, "_serving", None)
    process = Process()
    market = Market(process)
    process.state.lake = market
    process.roles = [market, Custodian(process), Trading(process)]
    monkeypatch.setattr(edge, "_serving", (1, 2))
    process.open_storage()
    shard = tmp_path / "shard-1"
    assert process.granted == shard
    assert process.store.root == shard / "raw"
    assert process.kinds.base == shard
    assert process.account.granted == shard
    assert market.products.path == shard / "products.json"
    process.stopped()
    monkeypatch.setattr(edge, "_serving", (0, 2))
    process.open_storage()
    assert process.store.root == tmp_path / "shard-0" / "raw"
    assert market.products.path == tmp_path / "shard-0" / "products.json"
