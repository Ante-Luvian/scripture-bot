"""!notes -- NET Bible notes: cleaning the raw bolls.life markup, reference
handling, paging, and the command end to end. Raw strings below are copied
from real bolls.life get-chapter responses; nothing here touches the network."""
import asyncio

import pytest

import net_notes_lookup as N


# ── cleaning ────────────────────────────────────────────────────────────────

def test_split_by_br_and_kind():
    raw = ("tn Or “refuses to believe,” or “disobeys.”<br>"
           "sn The alternatives presented are only two.")
    assert N.split_notes(raw) == [
        ("tn", "Or “refuses to believe,” or “disobeys.”"),
        ("sn", "The alternatives presented are only two."),
    ]


def test_run_together_notes_are_split():
    # Genesis 1:2 in the source: a tn note runs straight into an sn note.
    raw = ("tn The Hebrew term refers to the watery deep (see "
           "<a href='/NET/1/7/11'>Gen 7:11</a>).sn The watery deep. In the Babylonian account...")
    kinds = [k for k, _ in N.split_notes(raw)]
    assert kinds == ["tn", "sn"]


def test_links_keep_their_text():
    raw = "sn An allusion to <a href='/NET/4/21/5-9'>Num 21:5–9</a>."
    assert N.split_notes(raw) == [("sn", "An allusion to Num 21:5–9.")]


@pytest.mark.parametrize("legacy, fixed", [
    ("The Greek adverb οὕτως (Joutws) can refer", "The Greek adverb οὕτως (houtōs) can refer"),
    ("the word ἀπόλλυμι (apollumi) can mean", "the word ἀπόλλυμι (apollymi) can mean"),
    # comma form inside parentheses, multi-word, iota subscript
    ("(ὁ ὢν ἐν τῷ οὐρανῷ, Jo wn en tw ouranw)", "(ὁ ὢν ἐν τῷ οὐρανῷ, ho ōn en tōi ouranōi)"),
    # legacy final sigma written as a double quote, followed by a gloss
    ("μονογενὴς θεός (monogenh\" qeo\", “the only God”)",
     "μονογενὴς θεός (monogenēs theos, “the only God”)"),
    ("πιστεύω + εἰς (pisteuw + ei\")", "πιστεύω + εἰς (pisteuō + eis)"),
])
def test_greek_transliterations_are_regenerated(legacy, fixed):
    assert N.clean_note(legacy) == fixed


def test_mismatched_transliteration_is_left_alone():
    # word counts differ -> not a one-to-one transliteration, don't touch it
    s = "τὸ φῶς (the light shines)"
    assert N.clean_note(s) == s


def test_hebrew_shewa():
    assert N.clean_note("the Hebrew term תְּהוֹם (tÿhom, “deep”)") == "the Hebrew term תְּהוֹם (tᵉhom, “deep”)"


def test_manuscript_sigla_in_text_critical_notes():
    raw = "tc Most witnesses (A Θ Ψ 050 Ë1,13 Ï latt) and Ì66 have"
    assert N.split_notes(raw) == [("tc", "Most witnesses (A Θ Ψ 050 f1,13 𝔐 latt) and 𝔓66 have")]


def test_sigla_only_mapped_in_text_critical_notes():
    assert N.clean_note("Ïgnored outside tc", kind="tn") == "Ïgnored outside tc"


# ── lookup (network stubbed) ────────────────────────────────────────────────

FAKE_JOHN_3 = {
    16: {"text": "For this is the way God loved the world",
         "comment": "tn Or “this is how much.”<br>sn Two alternatives."},
    17: {"text": "For God did not send his Son", "comment": "sn That is, “to judge.”"},
    18: {"text": "The one who believes", "comment": ""},
}


@pytest.fixture
def stub_net(monkeypatch):
    monkeypatch.setattr(N, "_get_trans_book_id", lambda slug, book: 43 if book.lower() in ("john", "jn") else None)
    monkeypatch.setattr(N, "_get_canon_name", lambda slug, bid, fallback: "John")
    monkeypatch.setattr(N, "_fetch_chapter", lambda bid, ch: FAKE_JOHN_3 if ch == 3 else None)


def test_lookup_single_verse(stub_net):
    r = N.get_net_notes("Jn 3:16")
    assert r["reference"] == "John 3:16"
    assert r["url"] == "https://netbible.org/bible/John+3"
    assert r["verses"] == [(16, "For this is the way God loved the world",
                            [("tn", "Or “this is how much.”"), ("sn", "Two alternatives.")])]


def test_lookup_range(stub_net):
    r = N.get_net_notes("John 3:16-18")
    assert r["reference"] == "John 3:16–18"
    assert [v[0] for v in r["verses"]] == [16, 17, 18]
    assert r["verses"][2][2] == []   # verse with no notes


@pytest.mark.parametrize("ref, fragment", [
    ("John 3",       "Give a verse"),
    ("John 3:1-9",   "up to 5"),
    ("John 3:5-2",   "runs backwards"),
    ("Notabook 1:1", "doesn't have a book"),
    ("John 99:1",    "Couldn't retrieve"),
    ("John 3:99",    "isn't in the NET"),
])
def test_lookup_errors(stub_net, ref, fragment):
    r = N.get_net_notes(ref)
    assert not r["found"] and fragment in r["error"]


# ── paging and the command ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def reference(bot_module):
    from bot_commands import reference
    return reference


def test_paginate_splits_overlong_note_at_sentences(reference):
    long_note = " ".join(f"Sentence number {i} about the Greek text." for i in range(150))  # ~6000 chars
    pages = reference._paginate_blocks(["*verse*", long_note])
    assert len(pages) >= 2
    assert all(len(p) <= 3800 for p in pages)
    assert pages[1].startswith("…Sentence")          # continuation marked
    assert "".join(pages).count("Sentence number 149") == 1


def test_notes_command_end_to_end(reference, monkeypatch, fake_ctx):
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: {
        "found": True, "reference": "John 3:16", "url": "https://netbible.org/bible/John+3",
        "verses": [(16, "For this is the way God loved the world",
                    [("tn", "Or “this is how much.”"), ("sn", "Two alternatives."), ("tc", "Most mss.")])],
    })
    monkeypatch.setattr(reference, "record_special_stat", lambda *a: None)
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference="John 3:16"))

    embed = fake_ctx.sent[0]["embed"]
    assert embed.title == "📝 NET Notes — John 3:16"
    assert embed.url == "https://netbible.org/bible/John+3"
    assert "*For this is the way God loved the world*" in embed.description
    assert "**1. Translator's note** — Or “this is how much.”" in embed.description
    assert "**2. Study note**" in embed.description and "**3. Text-critical note**" in embed.description
    assert "Biblical Studies Press" in embed.footer.text   # credit is always shown


def test_notes_command_paginates_long_results(reference, monkeypatch, fake_ctx):
    long_note = "This note is long. " * 400   # ~7600 chars, like the longest real notes
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: {
        "found": True, "reference": "John 1:18", "url": "u",
        "verses": [(18, "No one has ever seen God.", [("tc", long_note)])],
    })
    monkeypatch.setattr(reference, "record_special_stat", lambda *a: None)
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference="John 1:18"))

    msg = fake_ctx.sent[0]
    assert msg["embed"].title.endswith("(1/3)")
    assert len(msg["embed"].description) <= 4096
    assert msg["view"] is not None   # ◀ ▶ buttons


def test_notes_command_error_and_usage(reference, monkeypatch, fake_ctx):
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference=""))
    assert "Usage" in fake_ctx.sent[0]["content"]
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: {"found": False, "error": "nope"})
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent[1]["content"] == "⚠️ nope"
