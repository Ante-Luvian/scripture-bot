"""
Classics of Islam and Sufism the library lacked, from the archive of sacred-texts.com (isl/), into
data/sufi/islamic_classics.json (2026-11-09).

    python scripts/build_islamic.py [names...]

Each page is read from its HTML: the text between the site's header ("... at sacred-texts.com") and its
footer, without the translators' footnotes and their marks, page numbers, or the line numbers in the margin; a
paragraph a verse (a stanza, for verse, its lines kept), the chapter's headings in italics over the paragraph
after them.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_world_texts as w            # (its sacred_text() and st_index() fetch and cache the archive)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sufi" / "islamic_classics.json"


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def pages(work: str) -> list:
    return w.st_index(f"isl/{work}/index.htm")


def paras(path: str) -> list:
    """A page's paragraphs and headings ("## ..."), in order."""
    page = w.sacred_text(path)
    page = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", "", page)
    head = re.search(r"(?is)at sacred-texts\.com.*?<HR>|Next</A>.*?<HR>", page)
    page = page[head.end():] if head else page
    end = re.search(r'(?is)<H\d[^>]*>\s*Footnotes|<HR>\s*(?:<P[^>]*>)?\s*(?:<CENTER>)?\s*<A HREF="[^"]*">Next:'
                    r'|<A HREF="[^"]*">\s*Next:|<nav\b', page)
    page = page[:end.start()] if end else page
    page = re.sub(r'(?is)<span class="margnote">.*?</span>', "", page)                    # (line numbers)
    page = re.sub(r'(?is)<a\s+href="?[^">]*#(?:fn|an|fr)_[^>]*>.*?</a>', "", page)          # (note marks)
    page = re.sub(r'(?is)<a\s+name="?page_[^>]*>.*?</a>', "", page)                         # (page numbers)
    page = re.sub(r"(?is)<P[^>]*>\s*\{p\. [\divxlc]+\}\s*</P>|\{p\. [\divxlc]+\}", "", page)
    page = re.sub(r"(?is)<P[^>]*>\s*\[\d+\.\s.*?\]\s*</P>", "", page)                       # ("[1. Traditional saying...]")
    page = re.sub(r"(?is)<H\d[^>]*>(.*?)</H\d>", lambda m: "<P>## " + m.group(1) + "</P>", page)
    out = []
    for chunk in re.split(r"(?i)<P\b[^>]*>", page):
        chunk = re.sub(r"(?i)<br\s*/?>", "\n", chunk)
        text = html.unescape(re.sub(r"<[^>]+>", "", chunk)).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.split("\n")]
        text = "\n".join(l for l in lines if l)
        text = re.sub(r"\[\d+\]", "", text)                                                   # ("God,"[1] and)
        text = re.sub(r"\s*\[p\. [\divxlc]+\]\s*", " ", text).strip()                        # ("is [p. 6] marked")
        if not text or re.fullmatch(r"[\W\d]*|p\. \d+|THE END\.?", text):
            continue
        if re.search(r"(?i)at sacred-texts\.com|^Sacred[- ]Texts\b|^Buy this Book", text):     # (the site's own lines)
            continue
        if out and not text.startswith("## ") and re.match(r"[a-z]", text) and not out[-1].startswith("## "):
            out[-1] += " " + text                                           # (a paragraph cut by a page break)
        else:
            out.append(text)
    return out


def verses(ps: list, drop_heads: int = 0) -> dict:
    """Paragraphs as verses, each heading in italics over the next; the first `drop_heads` headings (the
    chapter's own number and title, which the chapter's citation already gives) dropped."""
    out, pending, heads = {}, [], 0
    for p in ps:
        if p.startswith("## "):
            heads += 1
            if heads > drop_heads:
                pending.append(f"*{p[3:].strip()}*")
            continue
        out[str(len(out) + 1)] = "\n".join(pending + [p])
        pending = []
    return out


def alchemy_of_happiness() -> dict:
    """Al-Ghazali, The Alchemy of Happiness, trans. Claud Field (1910): its eight chapters."""
    chapters = [(p, l) for p, l in pages("tah") if l.startswith("Chapter ")]
    expect(len(chapters) == 8, f"Alchemy: {len(chapters)} chapters")
    return {str(n): verses(paras(p), drop_heads=2) for n, (p, _) in enumerate(chapters, 1)}


def mishkat() -> dict:
    """Al-Ghazali, The Niche for Lights (Mishkat al-Anwar), trans. W. H. T. Gairdner (1924): its three parts;
    Gairdner's long introduction and his own preface ("Author's Preface") left out."""
    idx = pages("mishkat")
    picks = [(p, l) for p, l in idx if l.startswith(("PART I.", "PART II.", "PART III."))]
    expect(len(picks) == 3, f"Mishkat: {[l for _, l in picks]}")
    return {str(n): verses(paras(p), drop_heads=1) for n, (p, _) in enumerate(picks, 1)}


def bird_parliament() -> dict:
    """Attar's Conference of the Birds in Edward FitzGerald's version, Bird Parliament (1889): a stanza a verse."""
    ps = [p for p in paras("isl/bp/bp01.htm") if not p.startswith("## ")]
    expect(len(ps) > 40, f"Bird Parliament: {len(ps)} stanzas")
    return {"1": {str(n): p for n, p in enumerate(ps, 1)}}


def bustan() -> dict:
    """Sa'di's Bustan, trans. A. Hart Edwards (1911): the prologue (0) and the ten chapters; each story's title
    in italics over it."""
    idx = pages("bus")
    picks = [(p, l) for p, l in idx if l.startswith(("Prologue", "Chapter "))]
    expect(len(picks) == 11, f"Bustan: {[l for _, l in picks]}")
    return {str(n): verses(paras(p), drop_heads=2 if n else 1) for n, (p, _) in enumerate(picks)}


def gospel_of_barnabas() -> dict:
    """The Gospel of Barnabas (the Italian manuscript, probably of the 16th century, with an Islamic Jesus), trans.
    Lonsdale and Laura Ragg (1907): its 222 chapters, each chapter's title in italics over its first verse."""
    idx = [(p, l) for p, l in pages("gbar") if re.match(r"\d+\.", l)]
    expect(len(idx) == 222, f"Barnabas: {len(idx)} chapters")
    out = {}
    for p, l in idx:
        n = re.match(r"(\d+)\.", l).group(1)
        ps = paras(p)
        heads = [x for x in ps if x.startswith("## ")]
        body = verses(ps, drop_heads=1)
        title = re.sub(r"^\d+\.\s*", "", heads[0][3:]) if heads else ""
        if body and title:
            body["1"] = f"*{title}*\n" + body["1"]
        out[n] = body
    return out


QURAN_OUT = ROOT / "data" / "quran" / "islamic_more.json"
# (name: builder, citation, file -- the Sufi works on the Sufi shelf's file, the rest with the Islamic books)
BUILDERS = {
    "Alchemy of Happiness": (alchemy_of_happiness, "al-Ghazali, trans. Claud Field (1910)", OUT),
    "Niche for Lights": (mishkat, "al-Ghazali, trans. W. H. T. Gairdner (1924)", OUT),
    "Bird Parliament": (bird_parliament, "Attar, trans. Edward FitzGerald (1889)", OUT),
    "Bustan": (bustan, "Sa'di, trans. A. Hart Edwards (1911)", OUT),
    "Gospel of Barnabas": (gospel_of_barnabas, "trans. Lonsdale and Laura Ragg (1907)", QURAN_OUT),
}


def main(names: list) -> None:
    payloads = {}
    for name, (fn, source, out) in BUILDERS.items():
        if names and name not in names:
            continue
        if out not in payloads:
            payloads[out] = (json.loads(out.read_text(encoding="utf-8")) if out.exists()
                             else {"source": "sacred-texts.com", "book_sources": {}, "books": {}})
        book = fn()
        expect(all(book.values()), f"{name}: an empty chapter")
        payloads[out]["books"][name] = book
        payloads[out]["book_sources"][name] = source
        print(f"  {name}: {len(book)} chapters, {sum(map(len, book.values()))} passages")
    for out, payload in payloads.items():
        if out != QURAN_OUT:                     # (Barnabas moved out of the Sufi file)
            payload["books"].pop("Gospel of Barnabas", None)
            payload["book_sources"].pop("Gospel of Barnabas", None)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
