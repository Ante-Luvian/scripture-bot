"""Magic and esotericism (scripts/build_esoteric.py, 2026-11-01): an opt-in tradition, English only."""
import re

import pytest


def _text(lookup, book):
    corpus, name = lookup._resolve_book(book)
    return "\n".join(v for ch in lookup._data[corpus][name].values() for v in ch.values())


def test_a_server_that_never_chose_has_it_and_one_that_chose_must_switch_it_on(bot_module):
    import core
    core._update_guild_config(1, traditions=None)
    assert "esoteric" in core.guild_traditions(1)                       # (never chose: everything)
    core._update_guild_config(2, traditions=["christian"])
    assert "esoteric" not in core.guild_traditions(2)
    every_old_one = [k for k in core.TRADITIONS if k not in core.ADDED_TRADITIONS | core.OPT_IN_TRADITIONS]
    core._update_guild_config(3, traditions=every_old_one)
    got = core.guild_traditions(3)
    assert core.ADDED_TRADITIONS <= got and "esoteric" not in got       # (ticked them all: still not this one)
    core._update_guild_config(4, traditions=["christian", "esoteric"])
    assert "esoteric" in core.guild_traditions(4)


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
