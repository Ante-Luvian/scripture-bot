"""
The Glossa Ordinaria in English -> data/patristics/glossa_ordinaria.json: a book a book of the Bible ("Glossa Ordinaria
on Jonah"), numbered as the KJV numbers its verses, each verse's glosses in the order the edition has them, each under
the words of the verse it explains.

The Latin is Martin Morard's edition of the editio princeps (Strasbourg, 1480/81) on Gloss-e (IRHT-CNRS), fetched by
scripts/fetch_glossa.py into scripts/.cache/glossa/. The English is ours, made for ScriptureBot (2026-11-11 on): the
glosses in scripts/glossa/english/<NN>.json ({gloss id: English}), the words of the Bible they explain in
scripts/glossa/lemmas/<NN>.json ({Latin: English}, in the Douay-Rheims's English, since it's the same Latin Bible).
Those files are the only copy of that work: they're kept in git.

The Glossa follows the Latin Bible's verse numbers, which differ from the KJV's in places: VERSIFICATION gives the
differences, a book at a time.

    python scripts/build_glossa.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LATIN = Path(__file__).resolve().parent / ".cache" / "glossa"
ENGLISH = Path(__file__).resolve().parent / "glossa" / "english"
LEMMAS = Path(__file__).resolve().parent / "glossa" / "lemmas"
OUT = ROOT / "data" / "patristics" / "glossa_ordinaria.json"
BOOKS = {"40": "Hosea", "41": "Joel", "44": "Jonah"}  # Gloss-e's numbers -> the KJV's names (the books translated so far)
LABELS = {"[allegorically]": "Allegorically", "[the moral sense]": "In the moral sense", "[Jerome]": "Jerome",
          "[Haimo]": "Haimo", "[Gregory]": "Gregory"}


def jonah(c: int, v: int) -> tuple:
    """The Vulgate's Jonah 2:1 is the KJV's 1:17, and its 2:2-11 the KJV's 2:1-10."""
    if c == 2:
        return (1, 17) if v == 1 else (2, v - 1)
    return c, v


def hosea(c: int, v: int) -> tuple:
    """The Vulgate's Hosea 2:24 is the end of the KJV's 2:23; its 6:2-3 the KJV's 6:1-2 (its 6:1 begins with the end of
    the KJV's 5:15, but is mostly the KJV's 6:1); its 14:1 the KJV's 13:16, and its 14:2-10 the KJV's 14:1-9."""
    if c == 2 and v == 24:
        return 2, 23
    if c == 6 and v in (2, 3):
        return 6, v - 1
    if c == 14:
        return (13, 16) if v == 1 else (14, v - 1)
    return c, v


VERSIFICATION = {"Hosea": hosea, "Jonah": jonah}

# Where a Vulgate verse straddles two of the KJV's, the glosses on the words the KJV puts in the other verse go there
# (gloss id -> KJV chapter and verse). Hosea 6:1 begins with the end of KJV 5:15 ("In their affliction they will rise
# early to me"), and Hosea 11:1 with the end of KJV 10:15 ("As the morning passeth, so hath the king of Israel passed
# away"); two long notes filed under those words are about another verse.
MOVES = {
    **{f"40_{g}": (5, 15) for g in ("interl3821", "marg2339", "interl3822", "interl3823", "interl3824", "interl3825")},
    "40_marg2340": (6, 2), "40_marg2341": (6, 2),
    **{f"40_{g}": (10, 15) for g in ("interl4129", "marg2449", "marg2450", "interl4130", "interl4131", "interl4132")},
    # the Vulgate's Hosea 6:3 is the KJV's 6:2 up to "we shall live in his sight"; "We shall know, and we shall follow on"
    # begins the KJV's 6:3
    **{f"40_{g}": (6, 3) for g in ("interl3841", "interl3842", "interl3843", "interl3844", "interl3845", "marg2342",
                                    "marg2343", "interl3846", "interl3847", "marg2344")},
    # the Vulgate's Hosea 10:15 begins with the end of the KJV's 10:14 ("the mother was dashed upon her children")
    "40_marg2448": (10, 14),
}
# ... and the words those long notes are about, in the Douay-Rheims's English
WORDS = {"40_marg2340": "He will revive us after two days: on the third day he will raise us up",
         "40_marg2341": "He will revive us after two days: on the third day he will raise us up",
         "40_marg2451": "and I loved him: and I called … out of Egypt"}


def render(notes: list) -> str:
    """A verse's notes, each phrase of the verse once, in the order the edition first explains it, with all its notes
    under it: the short ones written between the lines first, then the long ones from the margin. A note under a
    heading ("Jerome", "Allegorically") or under no words stands on its own where it falls."""
    groups, order = {}, []
    for i, (words, kind, text) in enumerate(notes):
        key = words if words and words not in LABELS else i
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((kind != "interl", text))
    lines = []
    for key in order:
        if not isinstance(key, str):
            words, _, text = notes[key]
            lines.append(f"*{LABELS[words]}:* {text}" if words in LABELS else text)
            continue
        texts = [t for _, t in sorted(groups[key], key=lambda g: g[0])]
        if len(texts) == 1:
            lines.append(f"**“{key}”** — {texts[0]}")
        else:
            lines.append(f"**“{key}”**")
            lines.extend(f"• {t}" for t in texts)
    return "\n".join(lines)


def clean(s: str) -> str:
    return re.sub(r"\s*\{t\. [^}]*\}\s*", " ", s).strip()


def main():
    books = {}
    for n, name in BOOKS.items():
        latin = json.loads((LATIN / f"{n}.json").read_text(encoding="utf-8"))
        english = json.loads((ENGLISH / f"{n}.json").read_text(encoding="utf-8"))
        lemmas = json.loads((LEMMAS / f"{n}.json").read_text(encoding="utf-8"))
        to_kjv = VERSIFICATION.get(name, lambda c, v: (c, v))
        notes = {}                                  # (KJV chapter, verse) -> [(words, kind, English)]
        missing = []
        for c, verses in latin["chapters"].items():
            for v, glosses in verses.items():
                for g in glosses:
                    text = english.get(g["id"])
                    if not text:
                        missing.append(g["id"])
                        continue
                    words = WORDS.get(g["id"]) or lemmas.get(clean(g["lemma"]), "")
                    where = MOVES.get(g["id"]) or to_kjv(int(c), int(v))
                    notes.setdefault(where, []).append((words, g["type"], text, g["id"]))
        chapters = {}
        for (kc, kv), verse_notes in sorted(notes.items()):
            # a note refiled under other words (WORDS) takes its place among that phrase's notes, not where it stood
            verse_notes.sort(key=lambda note: note[3] in WORDS)
            chapters.setdefault(str(kc), {})[str(kv)] = render([note[:3] for note in verse_notes])
        if missing:
            raise SystemExit(f"{name}: {len(missing)} glosses not yet in English, e.g. {missing[:3]}")
        books[f"Glossa Ordinaria on {name}"] = chapters
    data = {"source": "trans. for ScriptureBot from the Latin (ed. Morard, 1480/81 text)", "books": books}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(books)} books, {sum(len(v) for c in books.values() for v in c.values())} verses -> "
          f"{OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
