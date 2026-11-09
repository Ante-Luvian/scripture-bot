"""Pictures from Wikimedia are attached from local copies (2026-11-08: Discord stopped showing the
full-size Wikimedia addresses, and !dore, !blake and the 🖌️ buttons came up with no picture)."""
import sys

import pytest


@pytest.fixture
def here(bot_module, tmp_path, monkeypatch):
    import core
    monkeypatch.setattr(core, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cut.jpg").write_bytes(b"x")
    (tmp_path / "data" / "copy.jpg").write_bytes(b"x")
    return core


def test_own_file_first_then_the_copy_then_nothing(here):
    assert here.local_picture({"file": "data/cut.jpg", "copy": "data/copy.jpg"}).name == "cut.jpg"
    # Blake's "file" is the Commons title, not a path: the copy is used
    assert here.local_picture({"file": "File:Songs of Innocence.jpg", "copy": "data/copy.jpg"}).name == "copy.jpg"
    assert here.local_picture({"copy": "data/missing.jpg"}) is None
    assert here.local_picture({"image": "https://upload.wikimedia.org/x.jpg"}) is None


def test_the_three_commands_use_it(here, monkeypatch):
    from bot_commands import blake, dore, illustrations
    p = {"copy": "data/copy.jpg"}
    assert dore._local_file(p).name == illustrations._local_file(p).name == "copy.jpg"
    assert blake.local_picture is here.local_picture


@pytest.mark.parametrize("url, width, thumb", [
    ("https://upload.wikimedia.org/wikipedia/commons/9/9e/Dor%C3%A9Mary.jpg?utm_source=x", 1280,
     "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Dor%C3%A9Mary.jpg/1280px-Dor%C3%A9Mary.jpg"),
    ("https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d2/001.Light.jpg/1280px-001.Light.jpg?utm=x", 960,
     "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d2/001.Light.jpg/960px-001.Light.jpg"),
    ("https://upload.wikimedia.org/wikipedia/commons/a/ab/Plate.png", 500,
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Plate.png/500px-Plate.png"),
])
def test_thumbnail_addresses(url, width, thumb):
    from conftest import ROOT
    sys.path.insert(0, str(ROOT / "scripts"))
    import wikimedia_copies
    assert wikimedia_copies.thumbnail_url(url, width) == thumb
