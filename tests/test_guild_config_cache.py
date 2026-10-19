"""Each server's settings are read on every command, so the parsed file is cached until it changes."""
import json


def test_cached_until_the_file_changes(bot_module, monkeypatch):
    import core
    reads = []
    real = type(core.GUILD_CONFIG_PATH).read_text

    def counting(self, *a, **k):
        reads.append(self)
        return real(self, *a, **k)
    core._update_guild_config(1, packs=["church"])
    monkeypatch.setattr(type(core.GUILD_CONFIG_PATH), "read_text", counting)
    for _ in range(5):
        assert core._load_guild_config()["1"]["packs"] == ["church"]
    assert len(reads) <= 1
    core._update_guild_config(1, packs=["divination"])         # a change is seen at once
    assert core._load_guild_config()["1"]["packs"] == ["divination"]


def test_callers_get_their_own_copy(bot_module):
    import core
    core._update_guild_config(2, feature_streaks=True)
    mine = core._load_guild_config()
    mine["2"]["feature_streaks"] = False                         # changed but not saved
    assert core._load_guild_config()["2"]["feature_streaks"] is True


def test_no_file_means_no_settings(bot_module, tmp_path, monkeypatch):
    import core
    monkeypatch.setattr(core, "GUILD_CONFIG_PATH", tmp_path / "nothing.json")
    assert core._load_guild_config() == {}
    (tmp_path / "nothing.json").write_text("{not json", encoding="utf-8")
    assert core._load_guild_config() == {}
