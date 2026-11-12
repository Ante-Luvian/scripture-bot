"""
The Latin of the Glossa Ordinaria from Gloss-e (IRHT-CNRS: Martin Morard's edition of the editio princeps, Strasbourg
1480/81, gloss-e.irht.cnrs.fr), a book at a time, for translating -> scripts/.cache/glossa/<NN>.json:

    {"book": "Ionas", "chapters": {"1": {"1": [{"id": "44_marg2907", "type": "marg", "lemma": "ET FACTUM EST",
                                                "latin": "Ad ea que in mente prophete..."}, ...]}},
     "prologues": [{"id": ..., "title": "Prologus ‘Sanctum Ionam’", "latin": ...}]}

A verse's glosses in order: marginal ("marg", the longer comments, most from the Fathers) and interlinear ("interl",
the short ones between the lines), each with the words of the verse it explains (its lemma; for an interlinear gloss,
the phrase of the Bible text it sits over). The editor's apparatus (sources, variants) is left out.

    python scripts/fetch_glossa.py 44          (Jonah; the numbers are Gloss-e's: python scripts/fetch_glossa.py list)
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache" / "glossa"
SITE = "https://gloss-e.irht.cnrs.fr/php/"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}


def get(url: str, name: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(SITE + url, headers=UA), timeout=120).read())
        time.sleep(1.5)
    return f.read_text(encoding="utf-8", errors="replace")


def text(markup: str) -> str:
    markup = re.sub(r"(?s)<sup[^>]*>.*?</sup>", "", markup)            # (note marks, "marg.|")
    markup = re.sub(r'(?s)<span type="desc">.*?</span>', "", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", markup))).strip().replace(" .", ".") \
        .replace(" ,", ",").replace(" :", ":").replace(" ;", ";")


def books() -> dict:
    page = get("livres-liste.php?id=glo", "list.html")
    return {n: html.unescape(name).strip("<> *") for n, name in
            re.findall(r'numLivre=(\d+)"><\d+\.\s*-?\s*([^<]+?)\s*>?</a>', page)}


def chapter(n: str, ch: str) -> dict:
    """{verse: [gloss, ...]} for one chapter page."""
    page = get(f"editions_chapitre.php?id=liber&numLivre={n}&chapitre={ch}", f"{ch}.html")
    start = page.find("id='glose_example'")
    body = page[start:]
    verses, cur, last_bible = {}, None, ""
    # the page in order: a verse's number, then its units -- a phrase of the Bible, or a gloss
    for m in re.finditer(r'(?s)<div type="verset" class="verset">(.*?)</div>|<div class="(bible|marg|interl)"><span '
                         r'id="([^"]+)"/>(.*?)</div>', body):
        if m[1] is not None:
            v = re.search(r"(\d+),(\d+)", text(m[1]))
            if v:
                cur = verses.setdefault(v[2], [])
            continue
        kind, gid, inner = m[2], m[3], m[4]
        if cur is None:
            continue
        if kind == "bible":
            last_bible = text(inner)
            continue
        latin = text(inner)
        # the words it explains, as the edition prints them, in capitals before the gloss: "ET FACTUM EST. Ad ea que..."
        m2 = re.match(r"((?:[A-Z]{1,}[’']?\s*)+)\.\s+(.*)$", latin, re.S) if kind == "marg" else None
        if m2 and len(m2[1].split()) <= 12:
            lemma, latin = m2[1].strip(), m2[2].strip()
        else:
            lemma = ""
        cur.append({"id": gid, "type": kind, "lemma": lemma or last_bible, "latin": latin})
    return verses


def book(n: str) -> dict:
    page = get(f"editions.php?id=glo&numLivre={n}", f"book{n}.html")
    out = {"book": books().get(n, n), "chapters": {}, "prologues": []}
    for ch, title in re.findall(r"editions_chapitre\.php\?id=liber&numLivre=\d+&chapitre=([^']+)'>(.*?)</a>", page):
        title = text(title)
        if "Prol" in ch:
            continue                    # (Jerome's prefaces, not glosses on verses: not yet)
        if False:
            p = get(f"editions_chapitre.php?id=liber&numLivre={n}&chapitre={ch}", f"{ch}.html")
            start = p.find("id='glose_example'")
            body = re.sub(r'(?s)<div class="apparat_[a-z]+">.*?</div>', "", p[start:])
            paras = [text(x) for x in re.findall(r"(?s)<p[^>]*>(.*?)</p>", body)]
            out["prologues"].append({"id": ch, "title": re.sub(r"^<[^>]*>\s*", "", title),
                                     "latin": "\n".join(x for x in paras if x)})
        else:
            m = re.search(r"_(\d+)$", ch)
            if m:
                out["chapters"][m[1]] = chapter(n, ch)
    return out


def main():
    if sys.argv[1:2] == ["list"]:
        for n, name in books().items():
            print(n, name)
        return
    for n in sys.argv[1:]:
        data = book(n.zfill(2))
        f = CACHE / f"{n.zfill(2)}.json"
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        glosses = sum(len(g) for c in data["chapters"].values() for g in c.values())
        words = sum(len(x["latin"].split()) for c in data["chapters"].values() for g in c.values() for x in g)
        print(f"{n} {data['book']}: {len(data['chapters'])} chapters, {glosses} glosses, {words} Latin words, "
              f"{len(data['prologues'])} prologues -> {f}")


if __name__ == "__main__":
    main()
