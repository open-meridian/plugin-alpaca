"""The `environment` setting (from 0.8.1; from 0.12.0 the common setting,
its demo `paper` in Alpaca's word, contract v26): Paper, Alpaca's paper
trading API, by default, so Live is only ever a person's choice -- an upgrade, or a
value never saved, never turns the plugin Live (the product owner,
2026-10-14). The key is synthetic: nothing here reaches Alpaca."""

from __future__ import annotations

import meridian

from alpaca.broker import LIVE_BASE, PAPER_BASE, base_for
from alpaca.settings import (
    DECLARED,
    ENVIRONMENT,
    KEY_ID,
    LIVE,
    PAPER,
    SECRET_KEY,
    Config,
    config_from,
)

SETTINGS: tuple[meridian.Setting, ...] = DECLARED.declared()  # type: ignore[attr-defined]
BY_NAME = {setting.name: setting for setting in SETTINGS}
KEY = {KEY_ID: "PKTESTKEYID0000000002", SECRET_KEY: "test-secret-never-kept-0000000000000002"}


def delivered(held: dict[str, str]) -> meridian.Settings:
    """The settings as the SDK hands them over: typed, the declared defaults
    filled in, and the required ones held nothing for named, as the sidecar
    names them."""
    defaults = {s.name: s.default for s in SETTINGS if s.default is not None}
    values: dict[str, str | int | bool | list[dict[str, str]]] = {
        **defaults,
        **{name: BY_NAME[name]._parsed(text) for name, text in held.items()},
    }
    missing = tuple(s.name for s in SETTINGS if s.required and s.name not in held)
    return meridian.Settings(values=values, missing_required=missing)


def test_the_environment_is_first_and_paper_by_default() -> None:
    first = SETTINGS[0]
    assert first.name == ENVIRONMENT and first.required and first.label == "Environment"
    assert [(c.value, c.label) for c in first.choices] == [(LIVE, "Live"), (PAPER, "Paper")]
    assert first.default == PAPER
    assert "Paper until a person chooses Live." in first.description
    # The agents' demo-only guard (contract v26), said where the choice is made.
    assert first.description.endswith("Agents may place orders only on Paper.")
    assert first.roles == ("data", "custody", "connectivity")


def test_an_unset_environment_is_paper() -> None:
    settings = delivered(KEY)
    assert settings.values[ENVIRONMENT] == PAPER and ENVIRONMENT in settings.missing_required
    config = config_from(settings.values)
    assert config.environment == PAPER and config.paper
    assert base_for(config.environment) == PAPER_BASE
    # However it arrives: absent, or a value that is not a choice.
    assert config_from(dict(KEY)).environment == PAPER
    assert config_from({**KEY, ENVIRONMENT: ""}).environment == PAPER
    assert config_from({**KEY, ENVIRONMENT: "LIVE"}).environment == PAPER
    assert Config().environment == PAPER


def test_live_is_read_only_once_a_person_chooses_it() -> None:
    settings = delivered({**KEY, ENVIRONMENT: LIVE})
    assert settings.missing_required == ()
    config = config_from(settings.values)
    assert config.environment == LIVE and not config.paper
    assert base_for(config.environment) == LIVE_BASE
    assert config.credentials is not None and config.credentials.key_id == KEY[KEY_ID]


def test_a_value_saved_before_0_12_0_arrives_refused_and_unset() -> None:
    """`sandbox` was the paper value before 0.12.0. From SDK 0.31.1 a saved
    value the setting's choices no longer hold is delivered unset and said
    in `Settings.refused`, never raised: the plugin reads Alpaca's paper
    API, the guard's first key is empty (live), and the value is kept for
    the pages to say save it again."""
    value, refused = BY_NAME[ENVIRONMENT]._read("sandbox")
    assert value is None and refused is not None
    assert refused.reason == "not_a_choice" and "save it again" in refused.message
    defaults = {s.name: s.default for s in SETTINGS if s.default is not None}
    values = {k: v for k, v in {**defaults, **KEY}.items() if k != ENVIRONMENT}
    config = config_from(values, (refused,))
    assert config.environment == PAPER and base_for(config.environment) == PAPER_BASE
    assert config.environment_setting == "" and config.environment_to_save == "sandbox"
    assert config_from(delivered(KEY).values).environment_to_save == ""


def test_the_setting_is_the_guards_first_key_as_delivered() -> None:
    assert config_from(delivered(KEY).values).environment_setting == PAPER
    assert config_from(delivered({**KEY, ENVIRONMENT: LIVE}).values).environment_setting == LIVE
