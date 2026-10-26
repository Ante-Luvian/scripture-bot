"""
Look over a built corpus file before it goes live (the checks used while building data/english and
data/arthurian). Run from the project root:

    python scripts/inspect_corpus.py stats   data/english/pearl_poet.json [...]   # per book: passages, longest,
                                                                                # leftover markup
    python scripts/inspect_corpus.py show    data/english/sisam.json "orfeo" [n] # keys, first n passages, last one
    python scripts/inspect_corpus.py heads   data/english/gower.json [book]      # passages opening with a heading
    python scripts/inspect_corpus.py big     data/english/torrent.json "Torrent of Portyngale" [n]   # longest
    python scripts/inspect_corpus.py cleaner english/hawes.json [...]            # what clean_corpora would change
    python scripts/inspect_corpus.py letters                                     # ȝ þ ð and their stand-ins

All read-only. Output is UTF-8 whatever the console (PowerShell mangles ȝ and þ otherwise).
"""
import copy
import difflib
import glob
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout = io.open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)

# leftovers that should never reach a passage: markup, entities, folio and note marks, page numbers
BAD = re.compile(r"<|>|&[#a-zA-Z]+;|\{f\.|\{stub|myLayer|facsimile|\bMS reads\b|\[\d+\]|^\d+\s|\[Pg|Project Gutenberg")


def books_of(path):
    return json.load(open(path, encoding="utf-8"))["books"]


def passages(chapters):
    for c, verses in chapters.items():
        for v, t in verses.items():
            yield c, v, t


def stats(paths):
    for f in paths:
        for book, chs in books_of(f).items():
            vs = [t for _, _, t in passages(chs)]
            if not vs:
                print(f"{book[:45]:45} EMPTY")
                continue
            longest = max(vs, key=len)
            bad = [v for v in vs if BAD.search(v)]
            odd = [l for v in vs for l in v.split("\n") if l.count("*") % 2]
            print(f"{book[:45]:45} ch={len(chs):4} v={len(vs):5} maxc={len(longest):6} "
                  f"maxl={longest.count(chr(10)) + 1:4} bad={len(bad)} open-italics={len(odd)}")
            for b in bad[:2]:
                m = BAD.search(b)
                print("     BAD:", repr(b[max(0, m.start() - 60):m.end() + 60]))
            for l in odd[:2]:
                print("     ODD *:", repr(l[:100]))


def show(path, want="", n=1):
    for book, b in books_of(path).items():
        if want.lower() not in book.lower():
            continue
        ks = list(b)
        print("#####", book, len(ks), ks[:8], ks[-1])
        for k in ks[:n]:
            print(f"--- {k}\n{b[k].get('1', '') if isinstance(b[k], dict) else b[k]}")
        print(f"--- last {ks[-1]}\n{b[ks[-1]].get('1', '')}"[-700:])


def heads(path, want=""):
    for book, b in books_of(path).items():
        if want.lower() not in book.lower():
            continue
        print("#####", book)
        for k, v in b.items():
            t = v.get("1", "")
            if t.startswith("*"):
                print("  ", k, " | ".join(x for x in t.split("\n")[:3] if x.startswith("*"))[:110])


def big(path, book, n=3):
    b = books_of(path)[book]
    for c, v, t in sorted(passages(b), key=lambda x: -len(x[2]))[:n]:
        print("====", c, v, len(t), "chars", t.count("\n") + 1, "lines")
        print(t[:1500])


def cleaner(rels):
    from corpus_clean import clean_corpus
    for rel in rels:
        p = json.load(open(ROOT / "data" / rel, encoding="utf-8"))
        before = copy.deepcopy(p)
        n = clean_corpus(p, rel.replace("\\", "/"))
        print("=====", rel, n, "would change")
        shown = 0
        for book, chs in before["books"].items():
            for c, v, t in passages(chs):
                after = p["books"].get(book, {}).get(c, {}).get(v)
                if after != t and shown < 12:
                    shown += 1
                    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, t, after or "").get_opcodes():
                        if op != "equal":
                            print(f"  {book} {c}:{v} {op}: {t[max(0, i1 - 40):i2 + 40]!r} -> "
                                  f"{(after or '(removed)')[max(0, j1 - 40):j2 + 40]!r}")
                            break


def letters():
    """ȝ þ ð counts per book, and the stand-ins the owner doesn't want: 3 in a word (yogh), a scribe's y-for-þ."""
    yth = re.compile(r"\b[Yy](?:at|is|ir|ai|aim|ame|ar)\b")
    files = glob.glob(str(ROOT / "data" / "english" / "*.json")) + \
        [str(ROOT / "data" / "arthurian" / n) for n in ("middle_english.json", "auchinleck_arthur.json")]
    for f in files:
        for book, b in books_of(f).items():
            txt = "\n".join(t for _, _, t in passages(b))
            print(f"{book[:40]:40} þ={txt.count('þ') + txt.count('Þ'):5} ȝ={txt.count('ȝ') + txt.count('Ȝ'):5} "
                  f"ð={txt.count('ð') + txt.count('Ð'):4} 3-in-word={len(re.findall(r'[a-zþȝ]3|3[a-zþȝ]', txt)):3} "
                  f"y-for-þ={len(yth.findall(txt))}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "stats":
        stats(args)
    elif cmd == "show":
        show(args[0], args[1] if len(args) > 1 else "", int(args[2]) if len(args) > 2 else 1)
    elif cmd == "heads":
        heads(args[0], args[1] if len(args) > 1 else "")
    elif cmd == "big":
        big(args[0], args[1], int(args[2]) if len(args) > 2 else 3)
    elif cmd == "cleaner":
        cleaner(args)
    elif cmd == "letters":
        letters()
    else:
        raise SystemExit(__doc__)
