"""References spotted in ordinary chat get the verse -- and, for Bible
verses, the same study buttons as !verse."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def autodetect(bot_module):
    from bot_commands import autodetect
    return autodetect


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


def _chat(autodetect, monkeypatch, text):
    async def no_commands(message):
        pass
    monkeypatch.setattr(autodetect.bot, "process_commands", no_commands)
    channel = FakeChannel()
    author = type("Author", (), {"bot": False})()
    message = type("Message", (), {"content": text, "author": author, "channel": channel})()
    asyncio.run(autodetect.on_message(message))
    return channel.sent


def test_bible_verse_in_chat_gets_study_buttons(autodetect, monkeypatch):
    sent = _chat(autodetect, monkeypatch, "as it says in John 3:16, God so loved the world")
    assert len(sent) == 1
    assert "For God so loved the world" in sent[0]["embed"].description
    view = sent[0]["view"]
    assert [c.item.label for c in view.children] == ["Notes", "Cross-refs", "Interlinear", "Card"]
    assert view.timeout is None   # persistent buttons: the view must never time out


def test_non_bible_reference_in_chat_gets_plain_reply(autodetect, monkeypatch):
    sent = _chat(autodetect, monkeypatch, "Enoch 1:9 is quoted in Jude")
    assert sent and "view" not in sent[0]


@pytest.mark.parametrize("raw, book", [
    ("as it says in John", "John"),          # mid-sentence: used to fail entirely
    ("I love Jn", "Jn"),                     # abbreviation
    ("read 1 John", "1 John"),
    ("see Song of Solomon", "Song of Solomon"),   # longest match wins
    ("John", "John"),
    ("Enoch", "Enoch"),
    ("Talmud Berakhot", "Talmud Berakhot"),  # nothing exact: unchanged (old behaviour)
    ("see ch", "see ch"),                    # mid-sentence short lowercase word: not a book
    ("meet at pm", "meet at pm"),
    ("ps", "ps"),                            # ...but fine at the start of a message
    ("read Ps", "Ps"),                       # ...or capitalised
])
def test_trim_to_book(autodetect, raw, book):
    assert autodetect._trim_to_book(raw) == book


@pytest.mark.parametrize("text, expected", [
    ("as it says in John 3:16, God so loved the world", "For God so loved the world"),
    ("I keep thinking about 1 John 4:8 today", "God is love"),
    ("see Song of Solomon 2:1 for that", "rose of Sharon"),
])
def test_references_mid_sentence_are_found(autodetect, monkeypatch, text, expected):
    sent = _chat(autodetect, monkeypatch, text)
    assert sent and expected in sent[0]["embed"].description


def test_welcome_message_points_to_the_setup_commands(autodetect, bot_module):
    sent = []

    class Channel:
        def permissions_for(self, member):
            return type("P", (), {"send_messages": True})()

        async def send(self, **kw):
            sent.append(kw)

    guild = type("Guild", (), {"system_channel": Channel(), "me": object(), "text_channels": []})()
    asyncio.run(autodetect.on_guild_join(guild))
    text = sent[0]["embed"].description
    for command in ("!changelogsetup", "!changelogintro", "!votdsetup", "!oraclesetup", "!features"):
        assert command in text
        assert bot_module.bot.get_command(command[1:]) is not None   # and it's real


def test_ordinary_chat_gets_no_reply(autodetect, monkeypatch):
    assert _chat(autodetect, monkeypatch, "good morning everyone") == []
