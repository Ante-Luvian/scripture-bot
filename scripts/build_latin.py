"""
Latin authors the library lacked, into data/classical/latin.json (run scripts/clean_corpora.py after):

  old_age     Cicero's Cato Maior, On Old Age (Shuckburgh), from Gutenberg #2808 (his On Friendship the bot has)
  distichs    The Distichs of Cato (Chase, 1922), from Wikisource
  cato        Cato the Elder's On Agriculture, complete (Hooper and Ash's Loeb, 1934), from LacusCurtius: Harrison's
              translation on Gutenberg (#12140) is a digest of about a third of it
  varro       Varro's On Agriculture (the same Loeb), from LacusCurtius

LacusCurtius is slow (a page can take a minute and a half): scripts/fetch_lacus.py downloads its pages first.

    python scripts/build_latin.py [step ...]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_platonists import blocks, chapter, expect, gutenberg, numbered, split, text, wikisource, ws_blocks  # noqa: E402

OUT = ROOT / "data" / "classical" / "latin.json"


def _load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"source": "various translators",
                                                                            "books": {}, "book_sources": {}}


def _save(payload: dict) -> None:
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for book, chapters in payload["books"].items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"  {book}: {len(chapters)} chapters, {words:,} words")


def _put(book: str, chapters: dict, source: str) -> None:
    payload = _load()
    payload["books"][book] = chapters
    payload["book_sources"][book] = source
    _save(payload)


# ── Cicero, On Old Age ─────────────────────────────────────────────────────
# Sections numbered as Shuckburgh prints them ("2. Scipio. Many a time..."); the verse Cicero quotes is set apart
# (<pre>) in the middle of a section, and goes with it.

def old_age() -> None:
    t = gutenberg(2808)
    start = re.search(r"<h2>\s*ON OLD AGE\s*</h2>", t)
    part = t[start.end() if start else 0:t.find("*** END")] if start else ""
    expect(len(part) > 10000, "On Old Age not found")
    paras = []
    for m in re.finditer(r"(?is)<pre>(.*?)</pre>|<p\b[^>]*>(.*?)</p>", part):
        if m.group(1) is not None:
            s = "\n".join(line.strip() for line in m.group(1).strip().splitlines() if line.strip())
        else:
            s = text(m.group(2))
            s = re.sub(r"^([A-Z])([A-Z]+)\b(?= [a-z])", lambda w: w.group(1) + w.group(2).lower(), s)   # ("FOR I may")
        if s:
            paras.append(s)
    _put("On Old Age", {"1": numbered(paras)}, "Cicero, trans. E. S. Shuckburgh (1900)")


# ── The Distichs of Cato ───────────────────────────────────────────────────
# Chapter 0: the introduction, then the short precepts (the Monostichs); 1-4: the four books, a couplet a verse,
# each book's prose preface (bracketed in Chase) leading its first couplet.

def distichs() -> None:
    t = wikisource("Distichs of Cato")
    sections = {text(h): ws_blocks(body) for h, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>")}
    zero = sections["Introduction"] + sections["Monostichs"]
    books = {"0": {str(i + 1): s for i, s in enumerate(zero)}}
    for n, name in enumerate(("Book I", "Book II", "Book III", "Book IV"), 1):
        lines = "\n".join(p for p in sections[name] if not re.match(r"This work|Public domain", p)).split("\n")
        preface, couplets = [], []
        for line in lines:
            m = re.match(r"(\d+)\.\s+(.*)", line)
            if m:
                couplets.append([m.group(1), m.group(2)])
            elif couplets:
                couplets[-1][1] += "\n" + line
            else:
                preface.append(line)
        numbers = [int(k) for k, _ in couplets]
        expect(numbers == list(range(1, len(numbers) + 1)), f"{name}: couplets {numbers}")
        verses = {k: v.strip() for k, v in couplets}
        if preface:
            verses["1"] = "*" + " ".join(preface).strip("[] ") + "*\n" + verses["1"]
        books[str(n)] = verses
    _put("Distichs of Cato", books, "trans. Wayland Johnson Chase (1922)")


# ── LacusCurtius (Bill Thayer's transcriptions of the Loeb) ────────────────
# A chapter starts at <A CLASS="chapter" NAME="12">, a section at <A CLASS="sec" NAME="12.3">: the Loeb's numbers,
# kept, so "On Agriculture 12:3" is Cato 12.3. Left out: the link to the Latin page beside each chapter, page
# numbers, note numbers, and the notes (after <HR CLASS="endnotes">).

def lacus(pages: list, prefix: str = "") -> dict:
    """{chapter: {section: text}} of a work's pages; `prefix` before each chapter ("2." for Varro's second book)."""
    from fetch_lacus import fetch
    import html as _html
    out = {}
    for page in pages:
        t = fetch(page)
        t = t[:t.find('<HR CLASS="endnotes"')] if '<HR CLASS="endnotes"' in t else t
        t = t[t.find("</H1>"):] if "</H1>" in t else t
        t = re.sub(r'(?is)<A HREF="\s*L/[^"]*"[^>]*>\s*<IMG[^>]*>\s*</A>', " ", t)       # (the Latin page's link)
        t = re.sub(r'(?is)<SPAN CLASS="pagenum">.*?</SPAN>|<A CLASS="ref"[^>]*>.*?</A>', "", t)
        t = t.replace("&shy;", "").replace("&#8288;", "").replace("­", "")
        marks = [(m.group(1).lower(), m.group(2), m.start(), m.end())
                 for m in re.finditer(r'(?is)<A CLASS="(chapter|sec)" NAME="([^"]+)">[^<]*</A>', t)]
        # (Cato's preface has no chapter mark: its first section is the text before the mark "0.2")
        if marks and marks[0][0] == "sec" and marks[0][1].endswith(".2"):
            marks.insert(0, ("sec", marks[0][1][:-2] + ".1", 0, 0))
        chap = None
        for i, (kind, name, _, after) in enumerate(marks):
            end = marks[i + 1][2] if i + 1 < len(marks) else len(t)
            body = t[after:end]
            body = re.sub(r"(?is)<(i|em)>(.*?)</\1>", lambda x: f"*{x.group(2).strip()}*", body)
            body = re.sub(r"(?is)<P[^>]*>|<BR[^>]*>", "\n", body)
            body = _html.unescape(re.sub(r"<[^>]+>", "", body))
            body = "\n".join(re.sub(r"\s+", " ", line).strip() for line in body.split("\n"))
            body = re.sub(r"\n{2,}", "\n", body).strip()
            if kind == "chapter":
                chap = prefix + name
                out.setdefault(chap, {})
                if body:                                     # (a chapter whose first section isn't marked)
                    out[chap]["1"] = body
                continue
            c, _, s = name.rpartition(".")
            # a section belongs to the chapter it sits in (the page names one "3131.2", in chapter 31)
            key = chap if chap is not None else prefix + c
            if chap is not None and prefix + c != chap:
                print(f"    {page}: section {name} in chapter {chap}")
            if body:
                out.setdefault(key, {})[s] = (out.get(key, {}).get(s, "") + " " + body).strip()
    return out


def cato() -> None:
    pages = [f"E/Roman/Texts/Cato/De_Agricultura/{x}*.html" for x in "ABCDEFGHIJKL"]
    chapters = lacus(pages)
    numbers = sorted(int(c) for c in chapters if c.isdigit())
    expect(numbers[0] in (0, 1) and numbers[-1] == 162, f"Cato's chapters {numbers[:3]}...{numbers[-3:]}")
    _put("On Agriculture", dict(sorted(chapters.items(), key=lambda kv: int(kv[0]))),
         "Cato the Elder, trans. W. D. Hooper and H. B. Ash (1934)")


def varro() -> None:
    chapters = {}
    for book in (1, 2, 3):
        chapters.update(lacus([f"E/Roman/Texts/Varro/de_Re_Rustica/{book}*.html"], prefix=f"{book}."))
    expect(len(chapters) > 50, f"Varro: {len(chapters)} chapters")
    _put("On Farming", chapters, "Varro, trans. W. D. Hooper and H. B. Ash (1934)")


BUILDS = {"old_age": old_age, "distichs": distichs, "cato": cato, "varro": varro}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
