"""!notes -- NET Bible notes from netbible.org (text, markers, notes), the
bolls.life backup, reference handling, paging, and the command end to end.
HTML below is copied from real netbible.org / bolls.life responses; nothing
here touches the network."""
import asyncio

import pytest

import net_notes_lookup as N

LRM = "‎"

# ── netbible.org: verse text and markers ────────────────────────────────────

GENESIS_1_1 = (
    '<div class="chunk" id="netText_Genesis_1"><div class="paragraphtitle"><h3>The Creation of the World</h3></div>'
    '<p class="bodytext"> <span id="netText_Genesis_1_1" alt="Genesis_1_1" class="netVerse ">'
    '<span class="vref"><span class="chapterNumber">1</span></span> In the <st data-num="07225" class="">beginning</st>'
    '<sup> <a href="#" class="netNoteSuper" pos="1" data-book="Genesis" data-chapter="1" data-verse="1" '
    'id="noteSuper_1_Genesis_1" >1</a>&nbsp;</sup> <st data-num="0430" class="">God</st><sup> <a href="#" '
    'class="netNoteSuper" pos="2" data-book="Genesis" data-chapter="1" data-verse="1" id="noteSuper_2_Genesis_1" '
    '>2</a>&nbsp;</sup> <st data-num="01254" class="">created</st><sup> <a href="#" class="netNoteSuper" pos="3" '
    'data-book="Genesis" data-chapter="1" data-verse="1" id="noteSuper_3_Genesis_1" >3</a>&nbsp;</sup> the '
    '<st data-num="08064" class="">heavens</st> and the <st data-num="0776" class="">earth</st>.<sup> <a href="#" '
    'class="netNoteSuper" pos="4" data-book="Genesis" data-chapter="1" data-verse="1" id="noteSuper_4_Genesis_1" '
    '>4</a>&nbsp;</sup></span></p> </span> <p class="bodytext"> <span id="netText_Genesis_1_2" alt="Genesis_1_2" '
    'class="netVerse "><span class="vref"><span class="verseNumber">2</span></span> Now<sup> <a href="#" '
    'class="netNoteSuper" pos="1" data-book="Genesis" data-chapter="1" data-verse="2" id="noteSuper_5_Genesis_1" '
    '>5</a>&nbsp;</sup> the earth was without shape.</span></p></div>'
)

PSALM_23_1 = (
    '<div class="chunk" id="netText_Psalms_23"><div class="paragraphtitle"><h3>Psalm 23<sup> <a href="#" '
    'class="netNoteSuper" pos="1" data-book="Psalms" data-chapter="23" data-verse="1" id="noteSuper_1_Psalms_23" '
    '>1</a>&nbsp;</sup></h3></div><p class="psasuper"> <span id="netText_Psalms_23_1" alt="Psalms_23_1" '
    'class="netVerse "><span class="vref"><span class="chapterNumber">23</span></span> A <st data-num="04210" '
    'class="">psalm</st> of <st data-num="01732">David</st>.<p class="poetry"> <span id="netText_Psalms_23_1" '
    'alt="Psalms_23_1" class="netVerse ">The <span class="smcaps"><st data-num="03068">Lord</st></span> is my '
    '<st data-num="07462">shepherd</st>,<sup> <a href="#" class="netNoteSuper" pos="2" data-book="Psalms" '
    'data-chapter="23" data-verse="1" id="noteSuper_2_Psalms_23" >2</a>&nbsp;</sup> <p class="poetry"> '
    '<span id="netText_Psalms_23_1" alt="Psalms_23_1" class="netVerse ">I <st data-num="02637" class="">lack</st> '
    '<st data-num="03808" class="">nothing</st>.<sup> <a href="#" class="netNoteSuper" pos="3" data-book="Psalms" '
    'data-chapter="23" data-verse="1" id="noteSuper_3_Psalms_23" >3</a>&nbsp;</sup> </span></p> </span></div>'
)


def test_text_markers_and_note_numbers():
    verses, heading = N._parse_netbible_text(GENESIS_1_1)
    assert verses[1] == (["In the beginning", " God", " created", " the heavens and the earth.", ""], [1, 2, 3, 4])
    assert verses[2] == (["Now", " the earth was without shape."], [5])   # verse number "2" not in the text
    assert heading == {}                                                 # the section title has no note


def test_text_psalm_heading_note_superscription_and_small_caps():
    verses, heading = N._parse_netbible_text(PSALM_23_1)
    assert heading == {1: [("Psalm 23", 1)]}
    segments, numbers = verses[1]
    assert segments == ["A psalm of David. The LORD is my shepherd,", " I lack nothing.", ""]
    assert numbers == [2, 3]


# ── netbible.org: notes ─────────────────────────────────────────────────────

def _note(n, body):
    sup = f'<sup><span class="noteNoteSuper" id="note_{n}">{n}</span>&nbsp;</sup>' if n else ""
    return f'<div class="note">{sup}{body}</div>'


def test_notes_numbered_with_continuation_parts():
    html = (_note(1, '<span class="notetype">tn</span>  The translation assumes <i>absolute</i> state.')
            + _note(None, '<span class="notetype">sn</span>  <i>In the beginning</i>. The verse refers...')
            + _note(2, '<span class="notetype">sn</span>  <i>God</i>. The ending of '
                       '<span class="hebrew">אֱלֹהִים</span> (<span class="translit">ʾelohim</span>) is plural.'))
    notes = N._parse_netbible_notes(html)
    assert notes == {
        1: [("tn", "The translation assumes *absolute* state."),
            ("sn", "*In the beginning*. The verse refers...")],
        2: [("sn", f"*God*. The ending of אֱלֹהִים{LRM} (ʾelohim) is plural.")],
    }


def test_notes_text_critical_sigla_and_markdown_escaping():
    # John 1:18, real markup: apparatus sigla, superscripts, an uncial nomen
    # sacrum, a cross-reference, and literal asterisks in sigla ("א*", "C*").
    body = ('<span class="notetype">tc</span>  thus <span class="uncial">qMs</span> or '
            '<span class="uncial">uMs</span>. (A C<sup>3</sup> <span class="greek">Θ</span> ƒ<sup>1,13</sup> '
            '<span class="Apparatus">M</span> lat). <span class="Apparatus">P</span><sup>66</sup> '
            '<span class="hebrew">א</span>* B C* L. See <data ref="Bible:Jn 1">1</data>.')
    (kind, text), = N._parse_netbible_notes(_note(36, body))[36]
    assert kind == "tc"
    assert "thus Θ̅Σ̅ or Υ̅Σ̅." in text
    assert "(A C³ Θ ƒ¹˒¹³ 𝔐 lat)" in text
    assert f"𝔓⁶⁶ א{LRM}\\* B C\\* L" in text          # asterisks escaped for Discord
    assert text.endswith("See 1.")


# ── bolls.life backup: cleaning its legacy-encoded notes ───────────────────

def test_backup_groups_by_br_and_keeps_parts_together():
    raw = ("tn Or “refuses to believe.”<br>"
           "tn The watery deep (see <a href='/NET/1/7/11'>Gen 7:11</a>).sn The watery deep. In the account...")
    groups = N.split_note_groups(raw)
    assert groups[0] == [("tn", "Or “refuses to believe.”")]
    assert [k for k, _ in groups[1]] == ["tn", "sn"] and "Gen 7:11" in groups[1][0][1]


@pytest.mark.parametrize("legacy, fixed", [
    ("The Greek adverb οὕτως (Joutws) can refer", "The Greek adverb οὕτως (houtōs) can refer"),
    ("(ὁ ὢν ἐν τῷ οὐρανῷ, Jo wn en tw ouranw)", "(ὁ ὢν ἐν τῷ οὐρανῷ, ho ōn en tōi ouranōi)"),
    ("μονογενὴς θεός (monogenh\" qeo\", “the only God”)", "μονογενὴς θεός (monogenēs theos, “the only God”)"),
    ("τὸ φῶς (the light shines)", "τὸ φῶς (the light shines)"),   # not a transliteration: untouched
])
def test_backup_greek_transliterations(legacy, fixed):
    assert N.clean_note(legacy) == fixed


def test_backup_hebrew_sigla_and_markdown():
    assert N.clean_note("God (אֱלֹהִים,’elohim )") == f"God (אֱלֹהִים{LRM}, ’elohim)"
    assert N.clean_note("term תְּהוֹם (tÿhom)") == f"term תְּהוֹם{LRM} (tᵉhom)"
    assert N.clean_note("(A Ë1,13 Ï) and Ì66 B*", kind="tc") == "(A f1,13 𝔐) and 𝔓66 B\\*"
    assert N.clean_note("Ïgnored outside tc", kind="tn") == "Ïgnored outside tc"


# ── lookup (network stubbed) ────────────────────────────────────────────────

NOTES_HTML = (_note(1, '<span class="notetype">tn</span>  On beginning.')
              + _note(2, '<span class="notetype">sn</span>  On God.')
              + _note(3, '<span class="notetype">tn</span>  On created.')
              + _note(4, '<span class="notetype">tn</span>  On earth.')
              + _note(5, '<span class="notetype">tn</span>  On now.'))


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(N, "_get_trans_book_id", lambda slug, book: 1 if book.lower() in ("genesis", "gen") else None)
    monkeypatch.setattr(N, "_get_canon_name", lambda slug, bid, fallback: "Genesis")
    monkeypatch.setattr(N, "_fetch_netbible", lambda book, ch: (GENESIS_1_1, NOTES_HTML) if ch == 1 else None)
    monkeypatch.setattr(N, "_fetch_bolls_chapter", lambda bid, ch: None)


def test_lookup_from_netbible(stub):
    r = N.get_net_notes("Gen 1:1")
    assert (r["reference"], r["source"], r["url"]) == ("Genesis 1:1", "netbible", "https://netbible.org/bible/Genesis+1")
    v = r["verses"][0]
    assert v["text"] == "In the beginning God created the heavens and the earth."
    assert [(n["anchor"], n["parts"]) for n in v["notes"]] == [
        ("beginning", [("tn", "On beginning.")]), ("God", [("sn", "On God.")]),
        ("created", [("tn", "On created.")]), ("earth", [("tn", "On earth.")])]


def test_lookup_range(stub):
    r = N.get_net_notes("Genesis 1:1-2")
    assert r["reference"] == "Genesis 1:1–2"
    assert [v["verse"] for v in r["verses"]] == [1, 2]
    assert r["verses"][1]["notes"] == [{"anchor": "Now", "parts": [("tn", "On now.")]}]


def test_lookup_falls_back_to_bolls(stub, monkeypatch):
    monkeypatch.setattr(N, "_get_trans_book_id", lambda slug, book: 19)
    monkeypatch.setattr(N, "_get_canon_name", lambda slug, bid, fallback: "Psalms")
    monkeypatch.setattr(N, "_fetch_netbible", lambda book, ch: None)    # netbible.org unreachable
    monkeypatch.setattr(N, "_fetch_bolls_chapter", lambda bid, ch: {1: {
        "text": "My God, my God, why have you abandoned me?",
        "comment": "sn Psalm 22. The psalmist cries out.<br>sn Abandoned. The verb..."}})
    r = N.get_net_notes("Psalm 22:1")
    assert r["source"] == "bolls"
    v = r["verses"][0]
    assert v["segments"] is None
    assert v["intro"] == [{"title": "Psalm 22", "parts": [("sn", "Psalm 22. The psalmist cries out.")]}]
    assert v["notes"] == [{"anchor": None, "parts": [("sn", "Abandoned. The verb...")]}]


@pytest.mark.parametrize("ref, fragment", [
    ("Genesis 1",     "Give a verse"),
    ("Genesis 1:1-9", "up to 5"),
    ("Genesis 1:5-2", "runs backwards"),
    ("Notabook 1:1",  "doesn't have a book"),
    ("Genesis 99:1",  "Couldn't retrieve"),   # both sources fail
    ("Genesis 1:99",  "isn't in the NET"),
])
def test_lookup_errors(stub, ref, fragment):
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
    assert pages[1].startswith("…Sentence")
    assert "".join(pages).count("Sentence number 149") == 1


def _run_notes(reference, monkeypatch, ctx, result):
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: result)
    monkeypatch.setattr(reference, "record_special_stat", lambda *a: None)
    asyncio.run(reference.cmd_notes.callback(ctx, reference="x"))
    return ctx.sent[0]


def _verse(n, segments, notes, intro=()):
    return {"verse": n, "text": "".join(segments), "segments": segments, "notes": notes, "intro": list(intro)}


def test_notes_command_marks_the_verse(reference, monkeypatch, fake_ctx):
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 3:16", "url": "https://netbible.org/bible/John+3", "source": "netbible",
        "verses": [_verse(16, ["For this is the way", " God loved the world.", ""], [
            {"anchor": "way", "parts": [("tn", "Or “this is how much.”"), ("sn", "Two alternatives.")]},
            {"anchor": "world", "parts": [("tc", "Most mss.")]}])],
    })
    embed = msg["embed"]
    assert embed.title == "📝 NET Notes — John 3:16"
    assert embed.url == "https://netbible.org/bible/John+3"
    assert embed.description.startswith("*For this is the way¹ God loved the world.²*")
    assert ("**¹ way**\n*Translator's note:* Or “this is how much.”\n*Study note:* Two alternatives."
            in embed.description)
    assert "**² world**\n*Text-critical note:* Most mss." in embed.description
    assert "Biblical Studies Press" in embed.footer.text   # credit is always shown
    assert "backup" not in embed.description


def test_notes_command_numbers_continue_across_verses(reference, monkeypatch, fake_ctx):
    notes = [{"anchor": "Word", "parts": [("tn", "a")]}, {"anchor": "here", "parts": [("tn", "b")]}]
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 3:16–17", "url": "u", "source": "netbible",
        "verses": [_verse(16, ["Word", " here.", ""], notes), _verse(17, ["Word", " here.", ""], notes)]})
    d = msg["embed"].description
    assert "**[16]** *Word¹ here.²*" in d and "**[17]** *Word³ here.⁴*" in d
    assert "**⁴ here**" in d


def test_notes_command_heading_note_and_empty_verse(reference, monkeypatch, fake_ctx):
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "Psalms 23:1–2", "url": "u", "source": "netbible",
        "verses": [_verse(1, ["The LORD is my shepherd,", ""], [{"anchor": "shepherd", "parts": [("sn", "Metaphor.")]}],
                          intro=[{"title": "Psalm 23", "parts": [("sn", "*Psalm 23*. Overview.")]}]),
                   _verse(2, ["He takes me to lush pastures."], [])]})
    d = msg["embed"].description
    assert d.startswith("**On the heading “Psalm 23”**\n*Study note:* *Psalm 23*. Overview.")
    assert "*The LORD is my shepherd,¹*" in d and "**¹ shepherd**" in d
    assert "*He takes me to lush pastures.*\n*No notes on this verse.*" in d


def test_notes_command_backup_source_notice(reference, monkeypatch, fake_ctx):
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "Psalms 22:1", "url": "https://netbible.org/bible/Psalms+22", "source": "bolls",
        "verses": [{"verse": 1, "text": "My God, my God", "segments": None, "intro": [],
                    "notes": [{"anchor": None, "parts": [("sn", "Abandoned.")]}]}]})
    d = msg["embed"].description
    assert d.startswith("*(netbible.org couldn't be reached")
    assert "*My God, my God*" in d and "**Note 1**\n*Study note:* Abandoned." in d


def test_notes_command_paginates_long_results(reference, monkeypatch, fake_ctx):
    long_note = "This note is long. " * 400   # ~7600 chars, like the longest real notes
    msg = _run_notes(reference, monkeypatch, fake_ctx, {
        "found": True, "reference": "John 1:18", "url": "u", "source": "netbible",
        "verses": [_verse(18, ["No one has ever seen God.", ""], [{"anchor": "God", "parts": [("tc", long_note)]}])]})
    assert msg["embed"].title.endswith("(1/3)")
    assert len(msg["embed"].description) <= 4096
    assert msg["view"] is not None   # ◀ ▶ buttons


def test_notes_command_error_and_usage(reference, monkeypatch, fake_ctx):
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference=""))
    assert "Usage" in fake_ctx.sent[0]["content"]
    monkeypatch.setattr(reference, "get_net_notes", lambda ref: {"found": False, "error": "nope"})
    asyncio.run(reference.cmd_notes.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent[1]["content"] == "⚠️ nope"
