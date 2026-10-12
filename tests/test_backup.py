"""Daily backup of the runtime state."""
import datetime

import pytest

from conftest import RUNTIME_FILES


@pytest.fixture(scope="module")
def backup(bot_module):
    from bot_commands import backup
    return backup


def test_backs_up_the_same_files_the_tests_isolate(backup):
    assert backup.RUNTIME_STATE == RUNTIME_FILES


def test_every_runtime_file_is_found(backup, bot_module):
    names = {p.name for p in backup.runtime_paths()}
    assert {"stats.json", "bookmarks.json", "guild_config.json", "quiz_scores.json"} <= names


def test_copies_once_a_day_and_keeps_two_weeks(backup, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "stats.json").write_text('{"a": 1}', encoding="utf-8")
    missing = src / "bookmarks.json"
    dest = tmp_path / "backups"
    day = datetime.date(2026, 10, 1)
    assert backup.backup_data([src / "stats.json", missing], dest, day) == 1
    assert (dest / "2026-10-01" / "stats.json").read_text(encoding="utf-8") == '{"a": 1}'
    assert backup.backup_data([src / "stats.json"], dest, day) is None        # already done today
    for i in range(1, 20):
        backup.backup_data([src / "stats.json"], dest, day + datetime.timedelta(days=i))
    kept = sorted(p.name for p in dest.iterdir())
    assert len(kept) == 14 and kept[-1] == "2026-10-20" and kept[0] == "2026-10-07"


def test_never_touches_the_real_folder(backup, bot_module):
    import core
    assert backup.BACKUP_DIR != core.ROOT / "backups"
