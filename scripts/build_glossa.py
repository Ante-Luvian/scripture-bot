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
BOOKS = {"44": "Jonah"}                       # Gloss-e's numbers -> the KJV's names (the books translated so far)
LABELS = {"[allegorically]": "Allegorically", "[the moral sense]": "In the moral sense", "[Jerome]": "Jerome",
          "[Haimo]": "Haimo", "[Gregory]": "Gregory"}


def jonah(c: int, v: int) -> tuple:
    """The Vulgate's Jonah 2:1 is the KJV's 1:17, and its 2:2-11 the KJV's 2:1-10."""
    if c == 2:
        return (1, 17) if v == 1 else (2, v - 1)
    return c, v


VERSIFICATION = {"Jonah": jonah}


def clean(s: str) -> str:
    return re.sub(r"\s*\{t\. [^}]*\}\s*", " ", s).strip()


def main():
    books = {}
    for n, name in BOOKS.items():
        latin = json.loads((LATIN / f"{n}.json").read_text(encoding="utf-8"))
        english = json.loads((ENGLISH / f"{n}.json").read_text(encoding="utf-8"))
        lemmas = json.loads((LEMMAS / f"{n}.json").read_text(encoding="utf-8"))
        to_kjv = VERSIFICATION.get(name, lambda c, v: (c, v))
        chapters = {}
        missing = []
        for c, verses in latin["chapters"].items():
            for v, glosses in verses.items():
                kc, kv = to_kjv(int(c), int(v))
                lines = []
                for g in glosses:
                    text = english.get(g["id"])
                    if not text:
                        missing.append(g["id"])
                        continue
                    words = lemmas.get(clean(g["lemma"]), "")
                    if words in LABELS:
                        lines.append(f"*{LABELS[words]}:* {text}")
                    elif words:
                        lines.append(f"**“{words}”** — {text}")
                    else:
                        lines.append(text)
                if lines:
                    verse = chapters.setdefault(str(kc), {})
                    verse[str(kv)] = (verse.get(str(kv), "") + "\n" if str(kv) in verse else "") + "\n".join(lines)
        if missing:
            raise SystemExit(f"{name}: {len(missing)} glosses not yet in English, e.g. {missing[:3]}")
        books[f"Glossa Ordinaria on {name}"] = chapters
    data = {"source": "trans. for ScriptureBot from the Latin (ed. Morard, 1480/81 text)", "books": books}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(books)} books, {sum(len(v) for c in books.values() for v in c.values())} verses -> "
          f"{OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
