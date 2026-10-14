"""Drive the real !verse command with a stand-in Discord context (no network,
no Discord connection)."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def verse(bot_module):
    from bot_commands import verse
    return verse


def test_multi_translation_verse_sends_parallel_embed(verse, monkeypatch, fake_ctx):
    """Regression: `!verse John 3:16 kjv web` raised TypeError, because the
    2-arg sender it called was shadowed by !parallel's 3-arg _send_parallel."""
    calls = []

    def fake_get_parallel(ref, translations):
        calls.append((ref, translations))
        return {"found": True, "reference": "John 3:16",
                "parallel": [("KJV", "King James Version", "For God so loved the world"),
                             ("WEB", "World English Bible", "For God so loved the world")]}

    monkeypatch.setattr(verse, "get_parallel", fake_get_parallel)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16 kjv web"))

    assert calls == [("John 3:16", ["kjv", "web"])]
    assert len(fake_ctx.sent) == 1
    embed = fake_ctx.sent[0]["embed"]
    assert embed.title == "📖 John 3:16"
    assert [f.name for f in embed.fields] == ["**KJV**", "**WEB**"]
    assert embed.footer.text == "King James Version · World English Bible"


def test_multi_translation_verse_error(verse, monkeypatch, fake_ctx):
    monkeypatch.setattr(verse, "get_parallel",
                        lambda ref, tr: {"found": False, "error": "Unknown book: **Notabook**"})
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="Notabook 1:1 kjv web"))
    assert fake_ctx.sent[0]["embed"].description == "Unknown book: **Notabook**"


# ── study buttons ───────────────────────────────────────────────────────────

def _labels(buttons):
    return [b.item.label for b in buttons]


@pytest.mark.parametrize("reference, labels", [
    ("John 3:16",          ["Notes", "Cross-refs", "Interlinear", "Card", "Catena"]),
    ("John 3:16–18",       ["Notes", "Cross-refs", "Interlinear", "Card", "Catena"]),
    ("John 3:1–9",         ["Cross-refs", "Interlinear", "Card", "Catena"]),   # !notes takes up to 5 verses
    ("John 3:16 (ESV)",    ["Notes", "Cross-refs", "Interlinear", "Card", "Catena"]),
    ("1 Corinthians 13:4", ["Notes", "Cross-refs", "Interlinear", "Card", "Catena"]),
    ("Psalms 23",          []),   # whole chapter
    ("Quran 1:1",          []),   # not the Bible
    ("Tobit 1:1",          []),   # apocrypha: no NET notes / Strong's
    ("Book of Enoch 1:9",  []),
])
def test_study_buttons_only_for_bible_verses(verse, reference, labels):
    assert _labels(verse._study_buttons({"found": True, "reference": reference})) == labels


def test_no_study_buttons_on_errors(verse):
    assert verse._study_buttons({"found": False, "error": "nope"}) == []


# A button press, faked at the Discord-object level only: the button
# callbacks and the commands they run are the real ones. (An earlier test
# faked bot.get_context itself -- exactly the call that failed in Discord --
# so it passed while every study button was broken.)

class _FakeResponse:
    def __init__(self):
        self.edited_view = None

    async def edit_message(self, view=None):
        self.edited_view = view

    async def defer(self):
        pass


class _FakeChannel:
    id = 555

    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})

    def typing(self):
        class _Typing:
            async def __aenter__(self): return self
            async def __aexit__(self, *exc): return False
        return _Typing()


def _press(buttons, label):
    """Press a button the way Discord delivers it AFTER A RESTART: nothing
    in memory but the message's components; the button is rebuilt from its
    custom_id through from_custom_id, as discord.py's dynamic-item dispatch
    does. Returns (interaction, rebuilt button)."""
    pressed = next(b for b in buttons if b.item.label == label)
    message = type("Message", (), {"components": [type("Row", (), {"children": [b.item for b in buttons]})()]})()
    interaction = type("Interaction", (), {
        "response": _FakeResponse(), "channel": _FakeChannel(), "guild": None, "message": message,
        "user": type("User", (), {"id": 1, "__str__": lambda self: "tester"})(),
    })()
    cls = type(pressed)
    match = cls.__discord_ui_compiled_template__.fullmatch(pressed.item.custom_id)
    rebuilt = asyncio.run(cls.from_custom_id(interaction, pressed.item, match))
    asyncio.run(rebuilt.callback(interaction))
    return interaction, rebuilt


def test_study_buttons_are_registered_persistent_items(verse, bot_module):
    store = bot_module.bot._connection._view_store
    assert verse.StudyButton.__discord_ui_compiled_template__ in store._dynamic_items
    btn = verse._study_buttons({"found": True, "reference": "John 3:16"})[0]
    assert btn.item.custom_id == "study:notes:John 3:16"
    assert len(btn.item.custom_id) <= 100   # Discord's limit


def test_cross_refs_button_runs_the_real_command(verse):
    interaction, _ = _press(verse._study_buttons({"found": True, "reference": "John 3:16"}), "Cross-refs")
    # one use: the message's buttons come back with only this one disabled
    edited = interaction.response.edited_view
    assert edited.timeout is None
    assert [(c.item.label, c.item.disabled) for c in edited.children] == [
        ("Notes", False), ("Cross-refs", True), ("Interlinear", False), ("Card", False), ("Catena", False)]
    embed = interaction.channel.sent[0]["embed"]
    assert embed.title == "🔗 Cross-references — John 3:16"


def test_card_button_renders_the_verse(verse):
    interaction, _ = _press(verse._study_buttons({"found": True, "reference": "John 3:16"}), "Card")
    sent = interaction.channel.sent[0]
    assert sent["file"].fp.read(8) == b"\x89PNG\r\n\x1a\n"


def test_notes_button_passes_the_reference_without_translation_suffix(verse, monkeypatch):
    from bot_commands import reference
    seen = []
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: seen.append(ref) or {"found": False, "error": "x"})
    interaction, _ = _press(verse._study_buttons({"found": True, "reference": "John 3:16–18 (ESV)"}), "Notes")
    assert seen == ["John 3:16-18"]
    assert interaction.channel.sent[0]["content"] == "⚠️ x"


def test_verse_command_attaches_study_buttons(verse, monkeypatch, fake_ctx):
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16"))
    view = fake_ctx.sent[0]["view"]
    assert [c.item.label for c in view.children] == ["Notes", "Cross-refs", "Interlinear", "Card", "Catena"]
    # A view that times out unregisters its persistent buttons bot-wide
    assert view.timeout is None


def test_plain_verse_lookup_sends_result(verse, monkeypatch, fake_ctx):
    """The ordinary local path, end to end through _send_result."""
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent, "nothing was sent"
    text = " ".join(str(m.get("content") or "") + str(m["embed"].to_dict() if m.get("embed") else "")
                    for m in fake_ctx.sent)
    assert "For God so loved the world" in text


def test_a_single_verse_has_no_number_beside_it(bot_module):
    import core
    one = core._without_lone_verse_number({"found": True, "text": "**[16]** For God so loved the world"})
    assert one["text"] == "For God so loved the world"
    two = {"found": True, "text": "**[16]** For God so loved the world\n**[17]** For God sent not his Son"}
    assert core._without_lone_verse_number(two) == two                        # a range keeps its numbers
