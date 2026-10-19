"""bolls.life puts footnote and cross-reference marks in superscript inside the verse text; they
were showing up in verses ("the Pharisees ⓒ named Nicodemus", "born again, [1] ⓙhe"). The raw
strings below are what bolls.life sends (John 3 in each translation)."""
import pytest

from translation_lookup import _clean


@pytest.mark.parametrize("raw, clean", [
    ("There was a man from the Pharisees <sup>ⓒ</sup> named Nicodemus, <sup>ⓓ</sup> a ruler <sup>ⓔ</sup> of the Jews.",
     "There was a man from the Pharisees named Nicodemus, a ruler of the Jews."),                         # CSB
    ("This man came to him at night and said, “Rabbi, <sup>ⓕ</sup> we know that you are a teacher.” <sup>ⓘ</sup>",
     "This man came to him at night and said, “Rabbi, we know that you are a teacher.”"),
    ("Jesus replied, “I tell you for certain that you must be born from above<sup>[13]</sup> before you can see "
     "God's kingdom!”", "Jesus replied, “I tell you for certain that you must be born from above before you can see "
                        "God's kingdom!”"),                                                                # CEV
    (" <sup>[AA]</sup> Now there was a Pharisee named Nicodemus, a ruler of the Jews. <sup>[2]</sup>",
     "Now there was a Pharisee named Nicodemus, a ruler of the Jews."),                                    # NABRE
    ("<sup>{Jesus Talks with Nicodemus}</sup> d Now there was a man from the Pharisees, a leader of the Jews.",
     "Now there was a man from the Pharisees, a leader of the Jews."),                                     # ISV
    ('He came to Jesus <sup>{Lit. him}</sup> at night and told him, "Rabbi, <sup>{Rabbi is Heb. for Master and/or '
     'Teacher}</sup> we know"', 'He came to Jesus at night and told him, "Rabbi, we know"'),
])
def test_footnote_marks_are_removed(raw, clean):
    assert _clean(raw) == clean


@pytest.mark.parametrize("text", [
    '"For God so [greatly] loved and dearly prized the world, that He [even] gave His [One and] only begotten Son',  # AMP
    "It is Christ [Jesus] who died, rather, was raised",                                                    # NABRE
    "God did by sending his own Son as a human being with a nature like our own sinful one [but without sin].",  # CJB
    "the mind of the flesh [is] death, and the mind of the Spirit -- life and peace;",                     # YLT
    "a man of the Pharisees, Nicodemus [was] his name, a ruler of the Jews;",                              # LSV
])
def test_a_translations_own_brackets_stay(text):
    assert _clean(text) == text
