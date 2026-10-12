"""greek_translit -- scholarly transliteration of inflected Greek forms
(used by !interlinear and !notes). Expected values recorded from the
implementation before it moved out of bot_commands/card.py."""
import pytest

from greek_translit import _transliterate_greek


@pytest.mark.parametrize("greek, latin", [
    ("οὕτως", "hoútōs"),                       # rough breathing on diphthong, acute
    ("ὥστε", "hṓste"),
    ("ὁ ὢν ἐν τῷ οὐρανῷ", "ho ṑn en tōi ouranōi"),   # grave on omega, iota subscript
    ("τέκνα θεοῦ", "tékna theoû"),              # circumflex kept on short-length diphthong
    ("ζωή", "zōḗ"),
    ("ἀπόλλυμι", "apóllymi"),
    ("Αἰνὼν", "Ainṑn"),                         # capital
    ("ἄγγελος", "ángelos"),                     # gamma nasal
])
def test_transliterate(greek, latin):
    assert _transliterate_greek(greek) == latin
