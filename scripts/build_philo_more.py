"""
The works of Philo that data/jewish/philo.json lacked, in C. D. Yonge's translation (1854-55) as Early Jewish
Writings has it (earlyjewishwritings.com/text/philo/), added to it (2026-11-09):

    On Dreams I and II (book21), the Hypothetica (book37), On Providence I and II (book38-39), and the Fragments
    (book45, from John of Damascus's Parallels and others).

Like the rest of the file, a sectioned work goes by Yonge's section numbers, a chapter each ("On Dreams I 2" is
section 1.2); one without them (On Providence I, the Fragments) by paragraph. Yonge's and the site's notes in
braces ("{1}{#ge 1:27.A.}", "{**Yonge's title...}") are left out, and so is Eusebius's preface to each extract.
Left out: "Concerning the World" (book44), which Yonge's own note calls virtually the same treatise as On the
Eternity of the World, already in.

    python scripts/build_philo_more.py
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "ejw"
OUT = ROOT / "data" / "jewish" / "philo.json"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def page(n: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"philo_book{n}.html"
    if not f.exists():
        url = f"http://www.earlyjewishwritings.com/text/philo/book{n}.html"
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        time.sleep(1)
    raw = f.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")             # (the site's pages are Windows-1252)
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", text)
    text = re.sub(r"(?i)<p\b[^>]*>|<br\s*/?>\s*<br\s*/?>", "\n\n", text)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def body(n: int, start: str) -> str:
    text = page(n)
    i = text.find(start)
    expect(i >= 0, f"book{n}: no {start!r}")
    end = re.search(r"Go\s+to\s+the\s+Philo\s+page", text)
    expect(end is not None, f"book{n}: no footer")
    text = text[i + len(start):end.start()]
    # (hidden advertising on the page: "Our fantastic offers for free 642-889 exam ... dumps with great success")
    text = re.sub(r"Our fantastic offers.*?(?:success of \w+ ?\.|$)", "", text, flags=re.S)
    while True:                                  # (the notes in braces, some inside others)
        new = re.sub(r"\{[^{}]*\}", "", text)
        if new == text:
            break
        text = new
    return text


def paragraphs(text: str) -> list:
    out = []
    for p in re.split(r"\n\s*\n", text):
        p = re.sub(r"\s+", " ", p).strip()
        if p and not re.fullmatch(r"[A-Z0-9 ,.;:'\-()*]+", p) and not p.startswith("From Eusebius"):
            out.append(p)                        # (not the headings in capitals, nor Eusebius's references)
    return out


def sections(text: str, prefix: str = "") -> dict:
    """Yonge's sections: "(1.2) Now the second species" or "I. (1) Flaccus Avillius" opens section 1.2 or 1;
    what comes before the first is Eusebius's preface, left out."""
    text = re.sub(r"\s+", " ", " ".join(paragraphs(text)))
    parts = re.split(r"(?:\b[IVXLC]+\.\s*)?\((\d+(?:\.\d+)?)\)\s*", text)
    out = {}
    for num, chunk in zip(parts[1::2], parts[2::2]):
        key = num[len(prefix):] if prefix and num.startswith(prefix) else num
        chunk = chunk.strip()
        if chunk:
            out.setdefault(key, {"1": ""})
            out[key]["1"] = (out[key]["1"] + " " + chunk).strip()
    return out


def main() -> None:
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    books = payload["books"]
    dreams = body(21, "ON DREAMS, THAT THEY ARE GOD-SENT*")
    one, two = dreams.split("BOOK 2", 1)
    books["On Dreams I"] = sections(one, "1.")
    books["On Dreams II"] = sections(two, "2.")
    hypothetica = sections(body(37, "HYPOTHETICA*"))
    expect(hypothetica.pop("5.11")["1"].startswith("And first of all I will adduce"), "Hypothetica: Eusebius's preface")
    books["Hypothetica"] = hypothetica
    # On Providence I: what follows Eusebius's "...speaks in this way concerning matter." (before it, his words
    # and a passage he quotes from the Questions on Genesis)
    providence = paragraphs(body(38, "ON PROVIDENCE (Fragment I)"))
    cut = next(i for i, p in enumerate(providence) if p.startswith("And the Hebrew Philo, in his treatise on Providence"))
    books["On Providence I"] = {"1": {str(i): p for i, p in enumerate(providence[cut + 1:], 1)}}
    books["On Providence II"] = sections(body(39, "ON PROVIDENCE (Fragment II)"))
    # the fragments: each under its heading ("About impious men, sinners, etc."), without its page reference
    frags, heading = {}, ""
    for p in paragraphs(body(45, "FRAGMENTS")):
        m = re.match(r"(?:Page|P\.)\s*\d+\.\s*[A-Z]?\.?\s*", p)
        if m:
            frags[str(len(frags) + 1)] = (f"*{heading}*\n" if heading else "") + p[m.end():]
            heading = ""
        elif heading:                            # (a heading run on: "...and then turning" / "back again, have")
            heading += " " + p.rstrip(".")
        elif len(p) < 140 and not p.endswith((".", "?", "!")) or p.startswith("About "):
            heading = p.rstrip(".")
        elif frags:
            frags[str(len(frags))] += "\n" + p
    books["Fragments of Philo"] = {"1": frags}
    for name in ("On Dreams I", "On Dreams II", "Hypothetica", "On Providence I", "On Providence II", "Fragments of Philo"):
        n = sum(map(len, books[name].values()))
        expect(n >= (2 if name == "On Providence I" else 5), f"{name}: {n} passages")     # (I is two paragraphs)
        print(f"  {name}: {len(books[name])} chapters, {n} passages")
    expect(len(books["On Dreams I"]) > 200 and len(books["On Dreams II"]) > 250, "On Dreams sections")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
