"""
Download English Qur'an commentaries (tafsir) into data/tafsir/, one file each, for the 📖 Commentary button under
Qur'an verses (bot_commands/tafsir.py). Not kept in git: this script fetches them again (~25 MB).

From spa5k's tafsir_api (github.com/spa5k/tafsir_api, served by jsDelivr), only the editions whose text checked out
(2026-11-10): its altafsir.com copies are scrambled (the "Jalalayn" there is Kashani's commentary, the Wahidi and
Kashani files for surah 1 are both al-Qushayri) or have hundreds of characters lost as U+FFFD, so the Jalalayn
and Ibn Kathir come from its copies of quran.com's QUL, which are clean.

    jalalayn   Tafsir al-Jalalayn, trans. Feras Hamza (QUL resource 573)
    ibnkathir  Tafsir Ibn Kathir (abridged), Darussalam (QUL resource 35); one commentary covers a run of verses,
               so each run is kept once, on its first verse, with the verses it covers
    ibnabbas   Tanwir al-Miqbas min Tafsir Ibn 'Abbas, trans. Mokrane Guezzou (from altafsir.com)

Each file: {"name", "source", "surahs": {surah: {ayah: text}}} -- an ayah with nothing of its own isn't there.

    python scripts/fetch_tafsir.py
    python scripts/fetch_tafsir.py --altafsir   (al-Wahidi, al-Tustari and al-Kashani from altafsir.com; hours)
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "tafsir"
OUT = ROOT / "data" / "tafsir"
CDN = "https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir/"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
EDITIONS = {
    "jalalayn": ("tafsir-al-jalalayn", "Tafsir al-Jalalayn", "al-Mahalli and al-Suyuti, trans. Feras Hamza"),
    "ibnkathir": ("en-tafisr-ibn-kathir", "Tafsir Ibn Kathir", "Ibn Kathir, abridged (Darussalam)"),
    "ibnabbas": ("en-tafsir-ibn-abbas", "Tanwir al-Miqbas", "attributed to Ibn 'Abbas, trans. Mokrane Guezzou"),
}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def rows(slug: str, surah: int) -> list:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{slug}_{surah}.json"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(f"{CDN}{slug}/{surah}.json", headers=UA),
                                             timeout=60).read())
        time.sleep(0.3)
    d = json.loads(f.read_text(encoding="utf-8"))
    return d["ayahs"] if isinstance(d, dict) else d


def tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", (text or "").replace("\r", "")).strip()
    return re.sub(r"\n{3,}", "\n\n", re.sub(r" *\n *", "\n", text))


def mend(text: str) -> str:
    """Characters the Ibn 'Abbas copy lost as U+FFFD, which their place tells: "vis-�-vis" is à; one against a
    bracket ("(�so that", "mankind�)", "[�]") or between spaces is an ellipsis (a verse quoted in part); one before a
    word opens a quotation; one after a word closes the quotation that is open (even before a bracket: "(say not
    “Three”)"), and if none is open, it's an ellipsis."""
    text = text.replace("vis-�-vis", "vis-à-vis")
    out, open_quote = [], False
    for i, ch in enumerate(text):
        if ch != "�":
            out.append(ch)
            if ch in "“”":
                open_quote = ch == "“"
            continue
        before, after = text[i - 1] if i else " ", text[i + 1] if i + 1 < len(text) else " "
        if before.isspace() and after.isspace():
            out.append("…")
        elif open_quote and not before.isspace():
            out.append("”")
            open_quote = False
        elif before in "([" or after in ")]":
            out.append("…")
        elif before.isspace() or before in "“‘\"'—-:":
            out.append("“")
            open_quote = True
        else:
            out.append("…")
    return "".join(out)


def build(key: str) -> dict:
    slug, name, source = EDITIONS[key]
    surahs = {}
    for s in range(1, 115):
        verses, last = {}, None
        for r in sorted(rows(slug, s), key=lambda r: int(r["ayah"])):
            expect(int(r.get("surah", s)) == s, f"{key} {s}: a row of surah {r.get('surah')}")
            text = tidy(mend(r.get("text") or ""))
            if not text:
                continue
            a = int(r["ayah"])
            if last and text == verses[last]["text"]:          # (Ibn Kathir: one commentary for a run of verses)
                verses[last]["to"] = a
                continue
            verses[a] = {"text": text, "to": a}
            last = a
        surahs[str(s)] = {str(a): (v["text"] if v["to"] == a else {"text": v["text"], "to": v["to"]})
                          for a, v in verses.items()}
    return {"name": name, "source": source, "surahs": surahs}


# ── altafsir.com itself (2026-11-11): its pages are clean where spa5k's copies of them are not. A page holds one
# verse's commentary; most verses have none, and which do can't be known without asking, so every verse is asked
# for (resumably: scripts/.cache/altafsir/<key>_<surah>.json). The pages mix UTF-8 with stray Windows-1252 bytes
# (the dashes and quotes), read as such.
ALTAFSIR = {
    "wahidi": (86, "Asbab al-Nuzul", "al-Wahidi, trans. Mokrane Guezzou"),
    "tustari": (93, "Tafsir al-Tustari", "Sahl al-Tustari, trans. Annabel Keeler and Ali Keeler"),
    "qushayri": (108, "Lata'if al-Isharat", "al-Qushayri, trans. Kristin Zahra Sands"),
    "kashani": (107, "Tafsir al-Kashani", "al-Kashani, trans. Feras Hamza"),
}
FIRST_FETCH_SOUND = {"wahidi", "tustari"}   # (scripts/.cache/altafsir/: which verses have commentary, first pages)
DENSE = {"kashani"}
# the surahs a commentary's English on altafsir.com goes to: Hamza's Kashani there stops after al-Kahf (18); every
# later surah's pages are empty (checked 2026-11-11 at 19, 20, 21, 24, 36, 50, 55, 67, 78, 93, 96, 103 and 112)
COVERS = {"kashani": 18}           # commentaries on nearly every verse: a surah with nothing means the site failed
AYAHS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118,
         64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45,
         60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50,
         40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7,
         3, 6, 3, 5, 4, 5, 6]
assert sum(AYAHS) == 6236 and len(AYAHS) == 114


def _cp1252(err):
    return err.object[err.start:err.end].decode("cp1252", "replace"), err.end


def altafsir_page(no: int, surah: int, ayah: int, page: int = 1) -> "tuple[str, int]":
    """(the text of one page of a verse's commentary, how many pages it has). A long commentary is split into pages
    of ~2,300 characters ("&Page=2&Size=1"); each page links to all the others, so the highest is the count."""
    import codecs
    import html as htmllib
    codecs.register_error("cp1252-fallback", _cp1252)
    url = (f"https://www.altafsir.com/Tafasir.asp?tMadhNo=0&tTafsirNo={no}&tSoraNo={surah}&tAyahNo={ayah}"
           f"&tDisplay=yes" + (f"&Page={page}&Size=1" if page > 1 else "") + "&LanguageID=2")
    for attempt in range(5):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
            break
        except Exception:
            time.sleep(10 * (attempt + 1))
    else:
        raise SystemExit(f"altafsir {no} {surah}:{ayah}: no answer")
    html_ = raw.decode("utf-8", "cp1252-fallback")
    expect("ArraySoraAyah" in html_, f"altafsir {no} {surah}:{ayah}: not one of its pages")
    # (the text ends at the copyright line, or -- Kashani's pages -- at the paging links)
    m = re.search(r"(?s)<font class='TextResultEnglish'>(.*?)(?:<hr size='1'><span class='CopyRight'>|<LABEL\b)", html_)
    if "id=AyahText" not in html_ or not m:                   # (a verse with no commentary)
        return "", 0
    pages = max([page] + [int(x) for x in re.findall(r"InnerLink_onchange\(\d+,(\d+),\d+\)", html_)])
    # (the site's pages carry someone's injected <script> tags: none of that, and nothing like a link, may get in)
    body = re.sub(r"(?is)<script\b.*?</script>|<script\b[^>]*>", "", m.group(1))
    body = re.sub(r"(?is)<span[^>]*font-family:\s*Andalus[^>]*>.*?</span>", "", body)   # (Arabic, mis-encoded)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    text = tidy(htmllib.unescape(re.sub(r"<[^>]+>", "", body)))
    expect(not re.search(r"(?i)https?:|www\.|\.js\b|jsdelivr|<\w", text), f"altafsir {no} {surah}:{ayah}: {text[:80]!r}")
    return text, pages


def altafsir_verse(no: int, surah: int, ayah: int) -> str:
    """A verse's whole commentary: its pages joined."""
    text, pages = altafsir_page(no, surah, ayah)
    parts = [text] if text else []
    for p in range(2, pages + 1):
        time.sleep(0.4)
        more, _ = altafsir_page(no, surah, ayah, p)
        expect(more, f"altafsir {no} {surah}:{ayah}: page {p} of {pages} empty")
        parts.append(more)
    return "\n\n".join(parts)


def fetch_altafsir(key: str, workers: int = 3) -> None:
    """Every verse's commentary, all its pages (scripts/.cache/altafsir2/). Where the first fetch (2026-11-11, first
    pages only, scripts/.cache/altafsir/) already found which verses have commentary, only those are asked again."""
    from concurrent.futures import ThreadPoolExecutor
    no = ALTAFSIR[key][0]
    cache, first = CACHE.parent / "altafsir2", CACHE.parent / "altafsir"
    cache.mkdir(parents=True, exist_ok=True)
    for surah, count in enumerate(AYAHS, start=1):
        f = cache / f"{key}_{surah}.json"
        if f.exists() or surah > COVERS.get(key, 114):
            continue
        old = first / f"{key}_{surah}.json"
        # (only where that first fetch was sound: Kashani's came back empty, and read as "no commentary anywhere"
        # it asked for nothing)
        ayahs = sorted(int(a) for a in json.loads(old.read_text(encoding="utf-8"))) \
            if old.exists() and key in FIRST_FETCH_SOUND else range(1, count + 1)
        with ThreadPoolExecutor(workers) as pool:
            texts = list(pool.map(lambda a: (time.sleep(0.4), altafsir_verse(no, surah, a))[1], ayahs))
        # (the site sometimes answers with pages that have no text at all, which look like verses without commentary:
        # a whole surah of Kashani's came back so on 2026-11-11. He comments on nearly every verse, so stop, unsaved.)
        expect(key not in DENSE or any(texts), f"{key} {surah}: every page empty -- the site isn't answering; rerun")
        f.write_text(json.dumps({str(a): t for a, t in zip(ayahs, texts) if t}, ensure_ascii=False), encoding="utf-8")
        print(f"  {key} {surah}: {sum(1 for t in texts if t)} of {count}", flush=True)


def build_altafsir(key: str) -> dict:
    """An altafsir commentary from its fetched pages: a passage the site shows under each verse it covers is kept
    once, on its first verse, with the verses it covers (as Ibn Kathir's)."""
    no, name, source = ALTAFSIR[key]
    cache = CACHE.parent / "altafsir2"
    surahs = {}
    for s, count in enumerate(AYAHS, start=1):
        f = cache / f"{key}_{s}.json"
        if s > COVERS.get(key, 114):
            continue
        expect(f.exists(), f"{key} {s}: not fetched (python scripts/fetch_tafsir.py --altafsir {key})")
        # (the site's transliterations write the hamza as "Ì": "QurÌān", "ḥaqāÌiq" -> "Qurʾān", "ḥaqāʾiq")
        pages = {int(a): tidy(t.replace("Ì", "ʾ")) for a, t in json.loads(f.read_text(encoding="utf-8")).items()
                 if t.strip()}
        verses, last = {}, None
        for a in sorted(pages):
            if last and pages[a] == verses[last]["text"] and a == verses[last]["to"] + 1:
                verses[last]["to"] = a
                continue
            verses[a] = {"text": pages[a], "to": a}
            last = a
        surahs[str(s)] = {str(a): (v["text"] if v["to"] == a else {"text": v["text"], "to": v["to"]})
                          for a, v in verses.items()}
    out = {"name": name, "source": source, "surahs": surahs}
    if key in COVERS:
        out["covers"] = COVERS[key]                   # (the last surah it has: bot_commands/tafsir.py says so past it)
    return out


# The altafsir commentaries in the 📖 Commentary menu. (Kashani's pages looked empty at first, 2026-11-11: their text
# ends at the paging links, not the copyright line. Al-Qushayri's one page seen had lost its commas: left out.)
ALTAFSIR_BUILT = ["wahidi", "tustari", "kashani"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["--altafsir"]:
        for key in sys.argv[2:] or ALTAFSIR_BUILT:
            fetch_altafsir(key)
        for key in ALTAFSIR_BUILT:
            data = build_altafsir(key)
            print(f"  {data['name']}: {sum(len(v) for v in data['surahs'].values())} entries")
            (OUT / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return
    for key in EDITIONS:
        data = build(key)
        n = sum(len(v) for v in data["surahs"].values())
        bad = json.dumps(data, ensure_ascii=False).count("�")
        print(f"  {data['name']}: {n} entries")
        expect(not bad, f"{key}: {bad} broken characters left")
        (OUT / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
