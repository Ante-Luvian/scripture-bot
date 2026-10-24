"""Ptolemy's Tetrabiblos (Ashmand) and Centiloquy, and Lilly's Introduction to Astrology (ed. Zadkiel), from
sacred-texts (scripts/build_astrology.py)."""
import re


def _book(lookup, name):
    corpus, book = lookup._resolve_exact(name)
    return lookup._data[corpus][book]


def test_every_chapter_and_aphorism(lookup):
    t = _book(lookup, "Tetrabiblos")
    for book, count in {1: 27, 2: 14, 3: 19, 4: 10}.items():
        assert sorted(int(k.split(".")[1]) for k in t if k.startswith(f"{book}.")) == list(range(1, count + 1))
    assert sorted(map(int, _book(lookup, "Centiloquy")["1"])) == list(range(1, 101))
    assert sorted(map(int, _book(lookup, "Lilly's Introduction to Astrology"))) == list(range(1, 36))


def test_the_terms_table_is_read_by_sign_and_adds_up_as_ptolemy_says(lookup):
    """Ptolemy, 1.23: by the Egyptian terms "Saturn 57, Jupiter 79, Mars 66, Venus 82, and Mercury 76"."""
    totals = {}
    for text in _book(lookup, "Tetrabiblos")["1.23"].values():
        m = re.match(r"\*(\w+)\*: (.+)", text)
        prev = 0
        for planet, upto in re.findall(r"([A-Z][a-z]+) to (\d+)°", m.group(2) if m else ""):
            totals[planet] = totals.get(planet, 0) + int(upto) - prev
            prev = int(upto)
    assert totals == {"Saturn": 57, "Jupiter": 79, "Mars": 66, "Venus": 82, "Mercury": 76}


def test_nothing_left_of_the_web_pages(lookup):
    for name in ("Tetrabiblos", "Centiloquy", "Lilly's Introduction to Astrology",
                 "Lilly's Introduction to Astrology, Appendix"):
        for chapter in _book(lookup, name).values():
            for text in chapter.values():
                assert not re.search(r"###|\[paragraph continues\]|Click to enlarge|\bp\. \d+$|END OF THE|<|&\w+;", text)
                assert not re.fullmatch(r"[_\-\s]+", text)


def test_the_glyph_the_transcription_lost(lookup):
    """Lilly's own chart: "when he [♃] entered ###, his exaltation" -- ♋, by his own table of dignities."""
    text = " ".join(_book(lookup, "Lilly's Introduction to Astrology")["27"].values())
    assert "when he entered ♋, his exaltation" in text
    dignities = " ".join(_book(lookup, "Lilly's Introduction to Astrology")["18"].values())
    assert re.search(r"♋ · ☽ D\. N\. · ♃ 15", dignities)


def test_references(lookup):
    assert lookup.get_verse("Tetrabiblos 3.18")["text"].startswith("**[1]** *The Quality of the Mind*")
    assert "JUDGMENT must be regulated by thyself" in lookup.get_verse("Centiloquy 1:1")["text"]
    assert lookup.get_verse("Lilly 7")["reference"] == "Lilly's Introduction to Astrology 7"
    assert lookup.neighbours("Tetrabiblos 1.27:3")["next"] == "Tetrabiblos 2.1:1"
