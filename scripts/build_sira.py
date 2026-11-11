"""
Ibn Ishaq's Sirat Rasul Allah (the Life of the Prophet, in Ibn Hisham's recension) in Edward Rehatsek's translation,
the first in English (made in Bombay, finished in 1891, given to the Royal Asiatic Society in 1898), as Michael
Edwardes abridged it for "The Life of Muhammad, Apostle of Allah" (Folio Society, 1964) -- from the transcription
hraic.org put online (2002), kept by the Internet Archive (2004), into data/quran/sira_rehatsek.json (2026-11-10).

A chapter for each of the page's 26 sections, Muhammad's early life to his last illness, their names (the page's
anchors: "night_journey") written out as titles leading verse 1 in italics. No verse numbers in the book: a verse
is a paragraph, or a run of whole sentences of a long one. Left out: Edwardes's introduction (a modern outsider's
account of Islam, not Ibn Ishaq), his two footnotes and their marks, the section headings in capitals (the titles
say them) and the page's links. His [bracketed] explanations in the text are kept, as in the book. The transcription's slips are put right (SLIPS); a letter it
lost where the word is certain is restored in [brackets].

    python scripts/build_sira.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_budge import groups               # noqa: E402
from build_pseudepigrapha import expect      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "sira"
OUT = ROOT / "data" / "quran" / "sira_rehatsek.json"
URL = "http://web.archive.org/web/20040625103910id_/http://www.hraic.org/hadith/ibn_ishaq.html"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
BOOK = "Sirat Rasul Allah"
TITLES = {
    "early_life": "His Ancestry and Early Life", "khadija": "Khadija", "revelation": "The Revelation",
    "the_helpers": "The Helpers", "night_journey": "The Night Journey",
    "permission_to_wage_war": "The Permission to Wage War", "hijra": "The Hijra", "medina": "Medina",
    "the_qibla": "The Qibla", "rajam": "The Stoning", "the_trinity": "The Trinity",
    "first_caravan": "The First Raid on a Caravan", "badr": "Badr", "uhud": "Uhud", "banu_nadir": "The Banu Nadir",
    "aisha_sufwan": "Aisha and Safwan", "the_trench": "The Trench", "banu_qurayza": "The Banu Qurayza",
    "pilgrimage": "The Pilgrimage", "khaybar": "Khaybar", "pilgrimage_of_retaliation": "The Pilgrimage of Fulfilment",
    "conquest_of_mecca": "The Conquest of Mecca", "hawazin": "The Hawazin", "byzantium": "Byzantium",
    "tabuk": "Tabuk", "last_illness": "His Last Illness and Death",
}
# the transcription's slips (each must be found)
SLIPS = {"thirteenth (lay of": "thirteenth day of", "[c- 570]*": "[c. 570].", "and He is Mary.*": "and He is Mary.",
         "Woe toyou": "Woe to you", "accordinglyl": "accordingly", "punnish": "punish", "the othert milk": "the other milk",
         "religlion": "religion", "confered": "conferred", '.,\\ml Gabriel': "and Gabriel", "we nt back": "went back",
         "occas ion": "occasion", "ikh said again": "[…] said again", "thc truth": "the truth", "rightlv": "rightly",
         "embraced raj": "embraced [the Khaz]raj", "he lept up": "he leapt up", "ma ke him": "make him",
         "encument": "incumbent", "fiftyh part": "fifth part", "anong his": "among his", "father's narne": "father's name",
         "The daughtor": "The daughter"}


def page() -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "hraic_ibn_ishaq.html"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=120).read())
        time.sleep(1)
    return f.read_bytes().decode("cp1252", errors="strict")


def text_of(fragment: str) -> str:
    s = re.sub(r"(?is)<!\[if[^>]*\]>.*?<!\[endif\]>|<o:p>.*?</o:p>", " ", fragment)
    s = re.sub(r"(?i)<br\s*/?>", " ", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = s.replace("\xad", "").replace("‑", "-").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"(?<=\w)\s+(?=[,;:!?]|\.(?!\s*\.))", "", s)


def build() -> dict:
    src = re.sub(r"(?is)<(script|style)\b.*?</\1>|<!--.*?-->", "", page())
    parts = re.split(r'(?i)<a\s+name="?([a-z_]+)"?\s*>\s*</a>', src)
    names = parts[1::2]
    expect(names[0] == "introduction" and names[1:] == list(TITLES), f"sections {names}")
    book, seen = {}, dict.fromkeys(SLIPS, 0)

    def mend(p: str) -> str:
        for slip, right in SLIPS.items():
            seen[slip] += p.count(slip)
            p = p.replace(slip, right)
        return p

    for n, (name, chunk) in enumerate(zip(names[1:], parts[4::2]), start=1):
        chunk = chunk.split('<a href="#introduction">')[0].split("</div>")[0]
        # the paragraph the anchor sits in began before it: its opening tag is in the chunk before, so this
        # chunk opens mid-paragraph -- the first <p> boundary closes it
        paras = [mend(text_of(p)) for p in re.split(r"(?i)<p\b[^>]*>|</p>|<li\b[^>]*>", chunk)]
        paras = [p for p in paras if p and p.lower() not in ("introduction", "to hadith & sira")]
        # Edwardes's footnotes ("*Muhammad and his followers...", "[*The year of an invasion...}") and the section
        # headings the book sets in capitals ("THE REVELATION": the chapter titles say it)
        notes = [p for p in paras if p.startswith(("*", "[*"))]
        expect(len(notes) <= 1, f"{name}: notes {[n[:50] for n in notes]}")
        paras = [p for p in paras if not p.startswith(("*", "[*")) and not (p.isupper() and len(p) < 80)]
        expect(paras, f"{name}: no text")
        # a paragraph broken in mid-sentence (at the book's page turns: "taking him to his") goes on in the next;
        # where a section stops in mid-sentence the transcription has a gap, marked […]
        joined = []
        for p in paras:
            if joined and not re.search(r"[.!?:;'’”\"\])…]\s*$", joined[-1]):
                joined[-1] = re.sub(r"\s*[,‘']$", "", joined[-1]) + " " + p
            else:
                joined.append(p)
        if not re.search(r"[.!?:;'’”\"\])…]\s*$", joined[-1]):
            joined[-1] += " […]"
        paras = joined
        verses = []
        for p in paras:
            verses += groups(p)
        verses[0] = f"*{TITLES[name]}*\n{verses[0]}"
        book[str(n)] = {str(k): v for k, v in enumerate(verses, start=1)}
    expect(all(seen.values()), f"slips not found {[s for s, k in seen.items() if not k]}")
    return book


def main() -> None:
    book = build()
    print(f"  {BOOK}: {len(book)} chapters, {sum(map(len, book.values()))} verses")
    OUT.write_text(json.dumps({"source": "Ibn Ishaq, trans. Edward Rehatsek, abr. Michael Edwardes (1964)",
                               "books": {BOOK: book}}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
