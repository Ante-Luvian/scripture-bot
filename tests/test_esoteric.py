"""Magic and esotericism (scripts/build_esoteric.py, 2026-11-01): an opt-in tradition, English only."""
import re

import pytest


def _text(lookup, book):
    corpus, name = lookup._resolve_book(book)
    return "\n".join(v for ch in lookup._data[corpus][name].values() for v in ch.values())


def test_the_magic_books_come_with_the_gnostic_texts_not_opt_in(bot_module):
    """They were an opt-in tradition at first, and the owner's own server (which chose its traditions) never saw
    them in !books; the owner wants them with the Gnostic texts, wherever those are."""
    import core
    from bot_commands import books
    assert "esoteric" in core.TRADITIONS["gnostic"][1]
    core._update_guild_config(1, traditions=None)
    core._update_guild_config(2, traditions=["christian", "gnostic"])
    core._update_guild_config(3, traditions=["christian"])
    for guild, sees in ((1, True), (2, True), (3, False)):
        names = [name for name, _ in books.tree_for(guild)[1]]
        assert ("🔮 Magic & Esotericism" in names) is sees, guild


@pytest.mark.parametrize("ref, words", [
    ("agrippa 1.2", "Magick is a faculty of wonderfull vertue"),
    ("Arbatel of Magic 1", "Whosoever would know Secrets"),
    ("Heptameron 10", "We being made after the Image of God"),                  # (Turner's English, not the Latin)
    ("The Book of Abramelin 2.19", "LUCIFER. LEVIATAN. SATAN. BELIAL."),         # (the lists of names kept)
    ("goetia 1", "ruling in yᵉ East, called Bael"),                            # (the scribe's raised letters)
    ("goetia 0", "they are not ignorant Empiricks"),                           # (Peterson's [+not] kept)
    ("goetia 73", "into a deep lake"),                                          # (his supplied "[a]" kept)
    ("theurgia 6", "is called Padiel"),
    ("key of solomon 1.18", "The second pentacle of Saturn"),
    ("testament of solomon 5", "[He brought me] a little ring"),               # (Conybeare's own brackets)
    ("heptameron 14", "there will be hissings in the four parts"),            # (Turner's English, not the Latin)
    ("pseudomonarchia 2", "Agares"),
    ("sword of moses 1", "Four angels are appointed"),
    ("raziel 3", "The Angell said to Adam make thymiamata"),
    ("monad 9", "THEOREM IX"),
])
def test_the_books_open(lookup, ref, words):
    r = lookup.get_verse(ref)
    assert r["found"] and words in r["text"], ref


def test_english_only_and_no_editors_marks(lookup):
    for book in ("Three Books of Occult Philosophy", "Fourth Book of Occult Philosophy", "Arbatel of Magic",
                 "Heptameron", "The Book of Abramelin", "The Key of Solomon", "Goetia", "Theurgia Goetia",
                 "Ars Paulina", "Ars Almadel", "Ars Notoria", "Testament of Solomon", "The Sword of Moses",
                 "Pseudomonarchia Daemonum", "Sepher Raziel", "De Heptarchia Mystica", "The Hieroglyphic Monad",
                 "A Letter Apologeticall"):
        text = _text(lookup, book)
        assert not re.search(r"\b(Nos facti|Linea recta|exorcizamus|APHORISMVS|His peractis|In nomini dei)\b",
                             text), book
        assert not re.search(r"\[=|\[sic\]|\{|Greek text omitted|Joseph H\. Peterson|Mathers\.\s*$", text), book
        # (picture labels read as drop capitals, the site's menu, his variant notes)
        assert not re.search(r"\bfi\b|Home Contents Prev|\b(?:P|Sl\.\s?\d+) (?:adds|reads):", text), book
    assert "Introduction by S. L." not in _text(lookup, "The Book of Abramelin")


def test_the_demotic_magical_papyrus(lookup):
    """By column and line, as the translators number them (scripts/build_papyri.py)."""
    r = lookup.get_verse("demotic papyrus 2:5")
    assert r["found"] and "Pshoi that is in the abyss, bring in the light to me!" in r["text"]
    assert lookup.get_verse("magical papyrus verso 33:1")["found"]
    corpus, name = lookup._resolve_book("The Demotic Magical Papyrus")
    assert len(lookup._data[corpus][name]) == 29 and "p. 26" not in str(lookup._data[corpus][name])
