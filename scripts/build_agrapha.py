"""
The Agrapha: sayings of Jesus not in the four Gospels, as early writers quote them, into
data/nt_apocrypha/agrapha.json (2026-11-10).

No complete English collection is online (Pick's Paralipomena on Wikisource is a third transcribed), so this one
is compiled from the library itself, to its content standard: each saying is taken, word for word, from the
library's own copy of the work that quotes it (found by the pattern below; the build fails if it isn't there),
and given with that source and the command that opens it in context. All are direct quotations ascribed to Jesus
by the writer cited; none is from memory. Sayings already in a book of their own (the Gospel of Thomas, the
Oxyrhynchus sayings, the gospel fragments) are left to those books.

Left out, not in the library: Clement's sayings from the Gospel of the Egyptians ("How long shall men die?") --
ANF prints that book of the Stromateis in Latin; Origen's homily on Jeremiah ("He that is near me is near the
fire", Thomas 82); Jerome on Ephesians ("Never be joyful but when you look on your brother in love"); Tertullian
"On Baptism" 20; Codex Bezae's Luke 6:5.

    python scripts/build_agrapha.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "nt_apocrypha" / "agrapha.json"

# (chapter, source as shown, the reference that opens it, a pattern for the saying -- group 1 is the saying)
SAYINGS = [
    ("1", "Paul, quoting the Lord", "Acts 20:35", r"how he said, (It is more blessed to give than to receive\.)"),
    ("2", "2 Clement 4:5", "2 Clement 4:5", r"the Lord said, (Though ye be gathered together with Me in My bosom.*?workers of iniquity\.)"),
    ("2", "2 Clement 5:2-4", "2 Clement 5:4", r"Jesus said unto Peter, (Let not the lambs fear the wolves after they are dead;.*?Gehenna of fire\.)"),
    ("2", "2 Clement 12:2", "2 Clement 12:2", r"said, (When the two shall be one, and the outside as the inside, and the male with the female, neither male or female\.)"),
    ("2", "The Epistle of Barnabas 6:13", "Epistle of Barnabas 6:13", r"the Lord saith; (Behold I make the last things as the first\.)"),
    ("2", "The Epistle of Barnabas 7:11", "Epistle of Barnabas 7:11", r"He saith, (they that desire to see Me, and to attain unto My kingdom, must lay hold on Me through tribulation and affliction\.)"),
    ("2", "Ignatius, To the Smyrnaeans 3:2", "Ignatius to the Smyrnaeans 3:2", r"\*?(Lay hold and handle me, and see that I am not a demon without body\.)\*?"),
    ("3", "Papias, as Irenaeus reports him", "Fragments (Papias) 3:1", r"said\]: (The days will come in which vines shall grow, having each ten thousand branches.*?five-and-twenty metretes of wine\.)"),
    ("3", "Justin Martyr, Dialogue with Trypho 47", "Dialogue with Trypho 47:4", r"our Lord Jesus Christ said, '(In whatsoever things I shall take you, in these I shall judge you\.)'"),
    ("3", "Clement of Alexandria, Stromateis 1.28", "Stromateis 1.28:1", r"exhorts us: (Be skilful money-changers rejecting some things, but retaining what is good\.)"),
    ("3", "The Clementine Homilies, Homily 2", "Clementine Homilies 2:52", r"said our Master, '(Be ye good money-changers),'"),
    ("3", "Clement of Alexandria, Stromateis 5.10", "Stromateis 5.10:2", r"the Lord announced in a Gospel, (My mystery is to me, and to the sons of my house);"),
    ("3", "Origen, On Prayer", "On Prayer 1:6", r"illustrated by “(Ask for the great things and the little shall be added unto you,)” and “(Ask for the heavenly things and the earthly shall be added unto you,)”"),
    ("3", "Origen, Commentary on Matthew 13.2", "Commentary on the Gospel of Matthew 13.2:1", r"Jesus indeed says\. (Because of the weak I was weak, and I hungered because of the hungry, and I thirsted because of the thirsty)"),
    ("3", "The Clementine Homilies 12.29", "Clementine Homilies 12:29", r"has said, '(Good things must needs come, and blessed, said he, is he by whom they come; in like manner evil things must needs come, but woe to him through whom they come\.)'"),
    ("4", "Clement of Alexandria, Stromateis 2.9", "Stromateis 2.9:4", r"in the Gospel to the Hebrews it is written, (He that wonders shall reign, and he that has reigned shall rest\.)"),
    ("4", "Origen, Commentary on John 2.6", "Commentary on the Gospel of John 2.6:1", r"the Saviour Himself says, (My mother, the Holy Spirit took me just now by one of my hairs and carried me off to the great mount Tabor),"),
    ("4", "Jerome, Lives of Illustrious Men 2", "Lives of Illustrious Men 2:2", r"said to him, ‘(my brother eat thy bread, for the son of man is risen from among those that sleep\.)’"),
    ("5", "Robson, Christ in Islam (1929)", "Christ in Islam 4:21", r"said, \"(The world is a bridge, so pass over it and do not inhabit it\.)\""),
]
CHAPTERS = {"1": "In the New Testament, outside the Gospels", "2": "In the Apostolic Fathers",
            "3": "In the Church Fathers", "4": "From the Gospel of the Hebrews, as the Fathers quote it",
            "5": "In Islamic tradition"}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"agrapha: {message}")


def main() -> None:
    import scripture_lookup as s
    lookup = s.ScriptureLookup()
    book = {}
    for ch, label, ref, pattern in SAYINGS:
        m = re.match(r"(.+?) (\d[\d.]*):(\d+)$", ref)
        corpus, name = lookup._resolve_book(m.group(1))
        expect(corpus is not None, f"{ref}: no such book")
        text = lookup._data[corpus][name][m.group(2)][m.group(3)]
        found = re.search(pattern, text, re.S)
        expect(found is not None, f"{ref}: the saying is not in the library's text")
        parts = [g.strip().rstrip(",") for g in found.groups() if g]
        quoted = " and ".join(f"“{p[:1].upper() + p[1:]}”" for p in parts)       # (Origen quotes two together)
        verses = book.setdefault(ch, {})
        lead = f"*{CHAPTERS[ch]}*\n" if not verses else ""
        verses[str(len(verses) + 1)] = f"{lead}{quoted}\n— {label} (`!verse {ref}`)"
    OUT.write_text(json.dumps({"source": "compiled from the library's own texts",
                               "book_sources": {"Agrapha": "compiled from the library's texts"},
                               "books": {"Agrapha": book}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  Agrapha: {sum(map(len, book.values()))} sayings in {len(book)} chapters")


if __name__ == "__main__":
    main()
