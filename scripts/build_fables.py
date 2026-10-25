"""
More fables for !fable, from Project Gutenberg (sacred-texts, the first choice, has blocked this machine):

  * Phaedrus, the Roman fabulist (1st century), in Henry Thomas Riley's prose (1887), #25512
    -> data/classical/phaedrus.json, "Fables of Phaedrus": a chapter a fable, numbered through his five books
       and the "New Fables" some attribute to him (Riley's own "Book I, Fable 3" kept in each fable's first
       line). Riley's "Aesopian Fables" of unknown authors are left out.
  * La Fontaine's Fables (1668-94), in Walter Thornbury's verse (1886, with Doré's plates), #50316
    -> data/ballads/la_fontaine.json, "Fables of La Fontaine": a chapter a fable, in Thornbury's numbering.
  * The Talking Beasts (1911), Kate Douglas Wiggin and Nora Archibald Smith's book of the world's fables, #13815
    -> data/ballads/talking_beasts.json: a book a section (Bidpai, the Hitopadesa, Krilof...), a chapter a fable.
       Its Aesop and La Fontaine are left out: !fable has fuller translations of both.

Each fable's first paragraph is led by its title in italics, as Aesop's are. Footnote marks are dropped.

    python scripts/build_fables.py
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "fables"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def page(n: int) -> str:
    path = CACHE / f"{n}.html"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = f"https://www.gutenberg.org/cache/epub/{n}/pg{n}-images.html"
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
    return path.read_text(encoding="utf-8").split("THE FULL PROJECT GUTENBERG")[0]


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


def clean(s: str) -> str:
    s = re.sub(r'(?is)<span class="pagenum">.*?</span>', "", s)
    s = re.sub(r'(?is)<a class="(?:tag|fnanchor|crossref)[^"]*"[^>]*>.*?</a>', "", s)    # (note marks, cross-links)
    s = re.sub(r"(?is)<a[^>]*>\s*\[\d+\]\s*</a>|\[\d+\]", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?i)<br\s*/?>\s*", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


def titled(title: str, paras: list) -> dict:
    title = title.strip().rstrip(".")
    if title.isupper():                                 # ("THE GRASSHOPPER AND THE ANT" -> "The Grasshopper and the Ant")
        small = {"a", "an", "and", "the", "of", "to", "in", "on", "at", "by", "for", "with", "or", "his", "her", "who",
                 "which", "as", "from", "into"}
        words = title.lower().split(" ")
        title = " ".join(w if i and w in small else w[:1].upper() + w[1:] for i, w in enumerate(words))
        title = re.sub(r"(?<=[-(])([a-z])", lambda m: m.group(1).upper(), title)
    paras = [p for p in paras if p]
    paras[0] = f"*{title}*\n{paras[0]}"
    return {str(i + 1): p for i, p in enumerate(paras)}


def save(path: Path, source: str, books: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": source, "books": books}, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, chapters in books.items():
        print(f"{name}: {len(chapters)} fables -> {path.relative_to(ROOT)}")


# ── Phaedrus (Riley) ────────────────────────────────────────────────────────

def phaedrus() -> dict:
    t = page(25512)
    t = t[:t.find('id="smart_')] if 'id="smart_' in t else t          # (Smart's verse version follows Riley's)
    heads = list(re.finditer(r'(?is)<h4[^>]*>\s*<a id="(?:riley_([A-Za-z]+)|(NF))_([A-Z]+)">\s*Fable\s+[IVXLC]+\.?\s*</a>'
                             r'\s*(?:<br\s*/?>)?(.*?)</h4>', t))
    fables = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        book, num, title = h.group(1) or "NF", roman(h.group(3)), clean(h.group(4))
        body = t[h.end():nxt.start() if nxt else len(t)]
        body = re.split(r'(?is)<h[1-4][^>]*>', body)[0]                # (stop at the next book's heading)
        paras = [clean(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
        where = f"Book {book}, Fable {num}" if book != "NF" else f"the New Fables, Fable {num}"
        fables[str(len(fables) + 1)] = titled(title, [f"({where})"] + paras)
    if len(fables) < 120:
        raise SystemExit(f"Phaedrus: only {len(fables)} fables found")
    return fables


# ── La Fontaine (Thornbury) ─────────────────────────────────────────────────

def la_fontaine() -> dict:
    t = page(50316)
    # "FABLE XXII." then the title, with an anchor or not, and sometimes a picture between them
    heads = list(re.finditer(r'(?is)<p class="fable">\s*(?:<a[^>]*>\s*(?:</a>)?)?\s*FABLE\s+([IVXLCDM]+)\.?\s*'
                             r'(?:</a>)?\s*</p>(?:(?!<p class="fable).)*?<p class="fable">(.*?)</p>', t))
    fables = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        n, title = roman(h.group(1)), clean(h.group(2))
        body = t[h.end():nxt.start() if nxt else len(t)]
        body = body.split('<hr class="chap">')[0]                       # (Doré's plate for the next fable)
        paras = [clean(p) for p in re.findall(r'(?is)<p class="fable0\d"[^>]*>(.*?)</p>', body)]
        if not any(paras):
            raise SystemExit(f"La Fontaine {n} ({title}) has no text")
        if str(n) in fables:
            raise SystemExit(f"La Fontaine {n} twice")
        fables[str(n)] = titled(title, paras)
    return dict(sorted(fables.items(), key=lambda kv: int(kv[0])))


# ── The Talking Beasts ──────────────────────────────────────────────────────

SECTIONS = {"THE FABLES OF BIDPAI": "Fables of Bidpai", "FABLES FROM THE HITOPADESA": "Fables from the Hitopadesa",
            "FABLES FROM INDIA": "Fables from India", "MALAYAN FABLES": "Malayan Fables",
            "MOORISH FABLES": "Moorish Fables", "AFRICAN FABLES": "African Fables",
            "FABLES FROM KRILOF": "Fables of Krylov", "FABLES PROM THE CHINESE": "Fables from the Chinese",
            "FABLES FROM THE SPANISH": "Fables of Yriarte", "FABLES OF GAY AND COWPER": "Fables of Gay and Cowper"}


def talking_beasts() -> dict:
    t = page(13815)
    t = t.split("INDEX OF TITLES")[0]
    marks = [(m.start(), m.end(), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip())
             for m in re.finditer(r"(?is)<h4[^>]*>(.*?)</h4>", t)]
    books = {}
    for (start, end, name), nxt in zip(marks, marks[1:] + [(len(t), 0, "")]):
        book = SECTIONS.get(name)
        if not book:
            continue
        body = t[end:nxt[0]]
        body = re.split(r"(?is)<h2[^>]*>", body)[0]
        fables, title, paras = {}, None, []
        # a fable's title is a paragraph set off with space above it; an author's name (h5) may come between
        for m in re.finditer(r'(?is)<p([^>]*)>(.*?)</p>', body):
            attrs, text = m.group(1), clean(m.group(2))
            if "margin-top" in attrs and len(text) < 90 and "\n" not in text and text.strip(". ") not in ("Moral", "The Moral"):
                if title and paras:
                    fables[str(len(fables) + 1)] = titled(title, paras)
                title, paras = text, []
            elif title:
                paras.append(text)
        if title and paras:
            fables[str(len(fables) + 1)] = titled(title, paras)
        if not fables:
            raise SystemExit(f"{book}: no fables found")
        books[book] = fables
    return books


def main():
    save(ROOT / "data" / "classical" / "phaedrus.json", "trans. Henry Thomas Riley (1887)", {"Fables of Phaedrus": phaedrus()})
    save(ROOT / "data" / "ballads" / "la_fontaine.json", "trans. Walter Thornbury (1886)",
         {"Fables of La Fontaine": la_fontaine()})
    save(ROOT / "data" / "ballads" / "talking_beasts.json",
         "The Talking Beasts, ed. Kate Douglas Wiggin and Nora Archibald Smith (1911)", talking_beasts())


if __name__ == "__main__":
    sys.exit(main())
