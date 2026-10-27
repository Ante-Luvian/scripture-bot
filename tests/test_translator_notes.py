"""Cleanup of 2026-10-26: translators' notes served as the author's text, titles two collections share, and
Julian's misattributed translations. Each was found by a user asking for a verse."""
import re


def _text(lookup, book: str) -> str:
    corpus, name = lookup._resolve_book(book)[0], lookup._resolve_book(book)[1]
    chapters = lookup._data[corpus][name]
    return "\n".join(v for ch in chapters.values() for v in ch.values())


def test_taylors_notes_are_not_the_authors_text(lookup):
    """`!verse iamblichus` gave "On the Mysteries 138:6", Taylor's note on Galen. Taylor's books end with
    the author's last words now."""
    mysteries = _text(lookup, "On the Mysteries")
    assert not re.search(r"\bGale\b|De Ingenio Sanitatis|Roger Bacon", mysteries)
    last = lookup._data["classical"]["On the Mysteries"]
    assert list(last)[-1] == "104" and "immutable guard of true conceptions" in list(last["104"].values())[-1]
    assert "Gaffarel" not in _text(lookup, "Theology of Plato")
    cave = _text(lookup, "On the Cave of the Nymphs")
    assert "This Cronius" not in cave and cave.rstrip().endswith("the present Cave of the Nymphs.")


def test_no_page_numbers_in_porphyry(lookup):
    for book in ("On Abstinence", "On the Cave of the Nymphs", "Letter to Marcella", "Auxiliaries to the Intelligibles"):
        assert not re.search(r"\|\d", _text(lookup, book)), book


# ── the Neoplatonists repaired from their sources (scripts/build_neoplatonists.py) ──

def test_porphyrys_lost_italics_and_greek_are_back(lookup):
    mysteries = lookup.get_verse("On the Mysteries 8:11")["text"]
    assert "you say, “*it must be granted that there are Gods*.”" in mysteries        # was 'you say, “.”'
    assert "“*the pacifications of anger*”" in lookup.get_verse("On the Mysteries 20:8")["text"]
    assert "*the long-haired Samian*" in lookup.get_verse("Life of Pythagoras 6:10")["text"]   # Iamblichus's
    abstinence = lookup.get_verse("On Abstinence 1.22")["text"]
    assert "λυκοκτονος" in abstinence and ", *slayer of wolves*;" in abstinence             # was "the , slayer"


def test_no_footnote_numbers_in_the_text(lookup):
    """Each was a link in the source, run into the text ("O Firmus 1 , that you")."""
    assert "O Firmus, that you" in lookup.get_verse("On Abstinence 1.1")["text"]
    assert "the anniversary festival, which" in _text(lookup, "Hymn to King Helios")
    assert "he says that God did not descend alone" in _text(lookup, "Against the Galilaeans")
    assert not re.search(r"\( ?[Nn]ote \d+\)", _text(lookup, "On the Cave of the Nymphs"))
    proclus = _text(lookup, "Life of Proclus")
    assert not re.search(r"\|\d", proclus) and "Aries, at 16 degrees 26 minutes" in proclus   # (real numbers stay)
    for book, glued in (("Divine Names", "being5"), ("Mystical Theology", "consecrated132"), ("Isis and Osiris", "Pythagoras118")):
        assert glued not in _text(lookup, book)


def test_the_life_of_plotinus_is_whole(lookup):
    """It came in pieces: chapters missing, the titles of treatises made chapters, the website on the end."""
    life = lookup._data["classical"]["Life of Plotinus"]
    assert list(life) == [str(n) for n in range(1, 27)]
    assert life["1"]["1"].startswith("Plotinus, the philosopher our contemporary, seemed ashamed of being in the body")
    assert "Sacred Texts" not in _text(lookup, "Life of Plotinus")
    assert lookup._book_sources["Life of Plotinus"] == "trans. Stephen MacKenna (1917)"
    assert lookup._book_sources["Letter to Marcella"] == "trans. Alice Zimmern (1896)"
    assert lookup._book_sources["Life of Pythagoras"] != lookup._book_sources["On Abstinence"]


def test_the_orphic_hymns_whole(lookup):
    """All 86 and To Musaeus, each with its title: three had run into the hymn before (38 into 37...)."""
    hymns = lookup._data["classical"]["Orphic Hymns"]
    assert sorted(map(int, hymns)) == list(range(0, 87))
    assert hymns["2"]["1"].startswith("*To Night [Nyx]*\n*The Fumigation with Torches.*")
    assert hymns["38"]["1"].startswith("*To Corybas") and hymns["42"]["1"].startswith("*To the Seasons")
    assert any("Love's [Eors'] delightful flow'r:" in v for v in hymns["55"].values())


def test_the_chaldaean_oracles_whole(lookup):
    oracles = lookup._data["classical"]["Chaldaean Oracles"]
    assert list(oracles) == [str(n) for n in range(1, 200)]                 # (106 and 153 were lost, 73 last)
    assert oracles["153"]["1"] == "Enlarge not thy Destiny."
    assert oracles["86"]["1"].endswith("under the strong necessity of Mithus.")   # (was cut at "as many as")
    assert "Lobeck" not in oracles["3"]["1"] and "Pic. Concl." not in oracles["192"]["1"]


def test_no_page_numbers_in_the_pythagoreans(lookup):
    for book in ("Golden Verses of Pythagoras", "Golden Sentences of Democrates"):
        assert not re.search(r"\bp\. \d+", _text(lookup, book)), book


def test_a_title_two_collections_share_reaches_both(lookup):
    """Plato's Apology and Rufinus's, Aristotle's On the Soul and Tertullian's: each one opens, each with its
    own credit (Aristotle was credited to Tertullian's translator)."""
    seen = {}
    for corpus, books in lookup._data.items():
        for title, chapters in books.items():
            if title in seen and seen[title][1] != chapters:
                raise AssertionError(f"{title}: in {seen[title][0]} and {corpus}, different texts, one unreachable")
            seen.setdefault(title, (corpus, chapters))
    assert lookup.get_verse("On the Soul 1:1")["source"] == "various translators"                 # Aristotle's
    assert lookup.get_verse("On the Soul (Tertullian) 1:1")["source"].startswith("trans. Holmes")
    assert lookup.get_verse("On the Mysteries 1:1")["source"] == "trans. Thomas Taylor (1821)"
    assert "Ambrose" in lookup.get_verse("On the Mysteries (Ambrose) 1:1")["text"]
    assert lookup.get_verse("Letters (Theodoret) 1:1")["found"]
    assert lookup.get_verse("Epistle of Barnabas 1:1")["source"] == "trans. J. B. Lightfoot"
    assert lookup.get_verse("Epistle of Barnabas (Roberts and Donaldson) 1:1")["text"].count("All hail")


def test_julian(lookup):
    """King's translation (1888), not Taylor's; Wright's Against the Galilaeans; no "Caesars" that was really
    Taylor's hymn to the Sun; the Sun oration's opening restored."""
    assert lookup.get_verse("Hymn to King Helios 1:1")["text"].lower().count("it is my opinion that the present subject")
    assert lookup._book_sources["Hymn to King Helios"] == "trans. C. W. King (1888)"
    assert lookup._book_sources["Against the Galilaeans"] == "trans. Wilmer Cave Wright (1923)"
    # (the real Caesars came back with the rest of Wright's Julian, scripts/build_platonists.py)
    assert lookup._book_sources["The Caesars"].startswith("trans. Wilmer Cave Wright")
    assert "season of the Kronia" in lookup.get_verse("The Caesars 1")["text"]


def test_the_platonist_shelf_filled_out(lookup):
    """2026-10-26: the rest of the Pythagorean, Platonic, Orphic and Neoplatonic texts in clean English."""
    theology = lookup._data["classical"]["Theology of Plato"]
    assert list(theology)[0] == "1.1" and list(theology)[-1].startswith("6.")      # (all six books, not the first five)
    # (book III: Portus's Greek marks only I, II, VII, IX...; Taylor printed VII as "III")
    assert [k for k in theology if k.startswith("3.")][:4] == ["3.1", "3.2", "3.7", "3.9"]
    assert theology["3.7"]["1"].startswith("Again therefore, the mystic doctrine concerning *the one*")
    for book in ("Political Fragments of the Pythagoreans", "Fragments of Philolaus", "Fragments of Archytas",
                 "Ocellus Lucanus on the Universe", "Fragments of Heraclitus", "Orphic Gold Tablets",
                 "The Doctrine of Plato (Alcinous)", "Dissertations of Maximus of Tyre", "Apologia of Apuleius",
                 "The Golden Ass", "Scipio's Dream", "Letter to Anebo", "Porphyry Against the Christians",
                 "Commentary on the Chaldaean Oracles", "Letters of Julian", "Lives of the Philosophers and Sophists",
                 "Celsus Against the Christians", "Consolation of Philosophy", "On Providence and Fate"):
        assert book in lookup._data["classical"], book
    assert "Lake of Memory" in lookup.get_verse("Orphic Gold Tablets 1:1")["text"]
