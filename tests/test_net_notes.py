"""!notes -- NET Bible notes: cleaning the raw bolls.life markup, placing
note markers from labs.bible.org, reference handling, paging, and the command
end to end. Raw strings below are copied from real bolls.life / labs.bible.org
responses; nothing here touches the network."""
import asyncio

import pytest

import net_notes_lookup as N

LRM = "‎"


# ── cleaning and grouping ───────────────────────────────────────────────────

def test_one_group_per_br():
    raw = ("tn Or “refuses to believe,” or “disobeys.”<br>"
           "sn The alternatives presented are only two.")
    assert N.split_note_groups(raw) == [
        [("tn", "Or “refuses to believe,” or “disobeys.”")],
        [("sn", "The alternatives presented are only two.")],
    ]


def test_parts_sharing_one_marker_stay_in_one_group():
    # Genesis 1:2: a translator's note and a study note under one marker.
    raw = ("tn The Hebrew term refers to the watery deep (see "
           "<a href='/NET/1/7/11'>Gen 7:11</a>).sn The watery deep. In the Babylonian account...")
    groups = N.split_note_groups(raw)
    assert len(groups) == 1
    assert [k for k, _ in groups[0]] == ["tn", "sn"]


def test_links_keep_their_text():
    raw = "sn An allusion to <a href='/NET/4/21/5-9'>Num 21:5–9</a>."
    assert N.split_note_groups(raw) == [[("sn", "An allusion to Num 21:5–9.")]]


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
    s = "τὸ φῶς (the light shines)"   # word counts differ -> not a transliteration
    assert N.clean_note(s) == s


def test_hebrew_shewa():
    assert N.clean_note("the Hebrew term תְּהוֹם (tÿhom, “deep”)") == \
        f"the Hebrew term תְּהוֹם{LRM} (tᵉhom, “deep”)"


def test_hebrew_spacing_and_direction():
    # Genesis 1:1 source text: misplaced spaces, and the comma got pulled
    # into the right-to-left run when displayed.
    assert N.clean_note("Hebrew name for God (אֱלֹהִים,’elohim ) is a plural") == \
        f"Hebrew name for God (אֱלֹהִים{LRM}, ’elohim) is a plural"


def test_multiword_hebrew_is_not_split_by_direction_marks():
    out = N.clean_note("the phrase בְּרֵאשִׁית בָּרָא (bÿre’shit bara’) means")
    assert "בְּרֵאשִׁית בָּרָא" + LRM in out        # one mark, after the whole phrase
    assert out.count(LRM) == 1


def test_manuscript_sigla_in_text_critical_notes():
    raw = "tc Most witnesses (A Θ Ψ 050 Ë1,13 Ï latt) and Ì66 have"
    assert N.split_note_groups(raw) == [[("tc", "Most witnesses (A Θ Ψ 050 f1,13 𝔐 latt) and 𝔓66 have")]]


def test_sigla_only_mapped_in_text_critical_notes():
    assert N.clean_note("Ïgnored outside tc", kind="tn") == "Ïgnored outside tc"


# ── marker placement ────────────────────────────────────────────────────────

def test_marked_segments_from_labs_markup():
    raw = ('<p class="bodytext">In the <st data-num="07225" class="">beginning</st><n id="1" /> '
           '<st data-num="0430" class="">God</st><n id="2" /> <st data-num="01254" class="">created</st>'
           '<n id="3" /> the <st data-num="08064" class="">heavens</st> and the '
           '<st data-num="0776" class="">earth</st>.<n id="4" /></p>')
    segs = N._marked_segments(raw)
    assert segs == ["In the beginning", " God", " created", " the heavens and the earth.", ""]
    assert [N._anchor_word(s) for s in segs[:4]] == ["beginning", "God", "created", "earth"]


# ── lookup (network stubbed) ────────────────────────────────────────────────

FAKE_BOLLS = {
    16: {"text": "For this is the way God loved the world",
         "comment": "tn Or “this is how much.”<br>sn Two alternatives."},
    17: {"text": "For God did not send his Son", "comment": "sn That is, “to judge.”"},
    18: {"text": "The one who believes", "comment": ""},
}
FAKE_LABS = {
    16: "For this is the way<n id=\"1\" /> God loved the world.<n id=\"2\" />",   # agrees
    17: "Completely different wording here<n id=\"1\" />",                        # text disagrees
    18: "The one who<n id=\"1\" /> believes<n id=\"2\" />",                       # notes missing in bolls
}


@pytest.fixture
def stub_net(monkeypatch):
    monkeypatch.setattr(N, "_get_trans_book_id", lambda slug, book: 43 if book.lower() in ("john", "jn") else None)
    monkeypatch.setattr(N, "_get_canon_name", lambda slug, bid, fallback: "John")
    monkeypatch.setattr(N, "_fetch_chapter", lambda bid, ch: FAKE_BOLLS if ch == 3 else None)
    monkeypatch.setattr(N, "_fetch_labs_chapter", lambda book, ch: FAKE_LABS if ch == 3 else None)


def test_lookup_places_markers_when_sources_agree(stub_net):
    r = N.get_net_notes("Jn 3:16")
    assert r["reference"] == "John 3:16"
    assert r["url"] == "https://netbible.org/bible/John+3"
    v = r["verses"][0]
    assert v["segments"] == ["For this is the way", " God loved the world.", ""]
    assert [n["anchor"] for n in v["notes"]] == ["way", "world"]
    assert v["notes"][0]["parts"] == [("tn", "Or “this is how much.”")]


def test_lookup_skips_markers_when_text_disagrees(stub_net):
    v = N.get_net_notes("John 3:17")["verses"][0]
    assert v["segments"] is None
    assert v["notes"] == [{"anchor": None, "parts": [("sn", "That is, “to judge.”")]}]


def test_lookup_reports_marked_notes_missing_from_source(stub_net):
    v = N.get_net_notes("John 3:18")["verses"][0]
    assert v["notes"] == [] and v["marker_count"] == 2


def test_lookup_works_without_labs(stub_net, monkeypatch):
    monkeypatch.setattr(N, "_fetch_labs_chapter", lambda book, ch: None)
    v = N.get_net_notes("John 3:16")["verses"][0]
    assert v["segments"] is None and len(v["notes"]) == 2


def test_lookup_range(stub_net):
    r = N.get_net_notes("John 3:16-18")
    assert r["reference"] == "John 3:16–18"
    assert [v["verse"] for v in r["verses"]] == [16, 17, 18]


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
    assert pages[0].startswith("*verse*\n\nSentence number 0")   # verse isn't stranded alone
    assert pages[1].startswith("…Sentence")                      # continuation marked
    assert "".join(pages).count("Sentence number 149") == 1


def _run_notes(reference, monkeypatch, ctx, result):
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: result)
    monkeypatch.setattr(reference, "record_special_stat", lambda *a: None)
    asyncio.run(reference.cmd_notes.callback(ctx, reference="John 3:16"))
    return ctx.sent[0]


def test_notes_command_marks_the_verse(reference, monkeypatch, fake_ctx):
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 3:16", "url": "https://netbible.org/bible/John+3",
        "verses": [{"verse": 16, "text": "For this is the way God loved the world.",
                    "segments": ["For this is the way", " God loved the world.", ""],
                    "marker_count": 2,
                    "notes": [{"anchor": "way", "parts": [("tn", "Or “this is how much.”"),
                                                          ("sn", "Two alternatives.")]},
                              {"anchor": "world", "parts": [("tc", "Most mss.")]}]}],
    })
    embed = msg["embed"]
    assert embed.title == "📝 NET Notes — John 3:16"
    assert embed.url == "https://netbible.org/bible/John+3"
    assert embed.description.startswith("*For this is the way¹ God loved the world.²*")
    assert ("**¹ way**\n*Translator's note:* Or “this is how much.”\n*Study note:* Two alternatives."
            in embed.description)
    assert "**² world**\n*Text-critical note:* Most mss." in embed.description
    assert "Biblical Studies Press" in embed.footer.text   # credit is always shown


def test_notes_command_numbers_continue_across_verses(reference, monkeypatch, fake_ctx):
    verse = lambda n: {"verse": n, "text": "Word here.", "segments": ["Word", " here.", ""],
                       "marker_count": 2,
                       "notes": [{"anchor": "Word", "parts": [("tn", "a")]},
                                 {"anchor": "here", "parts": [("tn", "b")]}]}
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 3:16–17", "url": "u", "verses": [verse(16), verse(17)]})
    d = msg["embed"].description
    assert "**[16]** *Word¹ here.²*" in d and "**[17]** *Word³ here.⁴*" in d
    assert "**⁴ here**" in d


def test_notes_command_unanchored_and_missing(reference, monkeypatch, fake_ctx):
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 3:17–18", "url": "https://netbible.org/bible/John+3",
        "verses": [{"verse": 17, "text": "For God did not send his Son", "segments": None,
                    "marker_count": 1, "notes": [{"anchor": None, "parts": [("sn", "To judge.")]}]},
                   {"verse": 18, "text": "The one who believes", "segments": None,
                    "marker_count": 2, "notes": []}],
    })
    d = msg["embed"].description
    assert "isn't available for this verse" in d and "**Note 1**\n*Study note:* To judge." in d
    assert "The NET has 2 note(s) on this verse, but the notes source is missing them" in d


def test_notes_command_reports_partially_missing_notes(reference, monkeypatch, fake_ctx):
    # Psalm 23:4: the NET marks 4 notes, the notes source has 1.
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "Psalms 23:4", "url": "https://netbible.org/bible/Psalms+23",
        "verses": [{"verse": 4, "text": "Even when I must walk", "segments": None, "marker_count": 4,
                    "notes": [{"anchor": None, "parts": [("tn", "The Piel of nakham.")]}]}],
    })
    assert "The NET marks 4 notes on this verse; only 1 could be retrieved" in msg["embed"].description


def test_notes_command_paginates_long_results(reference, monkeypatch, fake_ctx):
    long_note = "This note is long. " * 400   # ~7600 chars, like the longest real notes
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 1:18", "url": "u",
        "verses": [{"verse": 18, "text": "No one has ever seen God.", "segments": None,
                    "marker_count": 1, "notes": [{"anchor": None, "parts": [("tc", long_note)]}]}],
    })
    assert msg["embed"].title.endswith("(1/3)")
    assert len(msg["embed"].description) <= 4096
    assert msg["view"] is not None   # ◀ ▶ buttons


def test_notes_command_error_and_usage(reference, monkeypatch, fake_ctx):
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference=""))
    assert "Usage" in fake_ctx.sent[0]["content"]
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: {"found": False, "error": "nope"})
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent[1]["content"] == "⚠️ nope"
