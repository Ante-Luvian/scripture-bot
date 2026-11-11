"""
The readings from the Fathers and saints in the Roman Breviary's Matins, in English, from the Divinum Officium
project (github.com/DivinumOfficium/divinum-officium, web/www/horas/English) -> data/patristics/breviary_readings.json,
one book, "Readings from the Breviary".

Matins has three nocturns of lessons: the first is Scripture; on Sundays and feasts the second is a sermon or treatise
of a Father (or, on a saint's day, the saint's life), the third the day's Gospel and a Father's homily on it. Kept here:
every lesson that opens with whose it is ("From the Sermons of Pope St. Leo (the Great)", "Homily by St. Bede the
Venerable"), with the lessons that continue it. Left out: Scripture, the saints' lives (no author heading), the
responsories and rubrics.

A chapter a day, in the order of the year: the seasons (Advent to the last Sunday after Pentecost), then the saints'
days (1 January to 31 December), then the Commons (the offices shared by kinds of saints). A verse a reading: its
heading in italics, where it's from, and for a homily the Gospel it explains. A reading found word for word on an
earlier day (the variant offices "Adv1-0o", "Pent03-1Feria"...) is kept once.

    python scripts/build_breviary.py
"""
import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = Path(__file__).resolve().parent / ".cache" / "divinum_officium"
ENGLISH = REPO / "web" / "www" / "horas" / "English"
OUT = ROOT / "data" / "patristics" / "breviary_readings.json"
BOOK = "Readings from the Breviary"

HEAD = re.compile(r"^(?:A\s+|The Lesson is taken\s+)?(?:From|Homily|Sermon|Treatise|Commentary|Exposition|Discourse|"
                  r"Tract|Instruction|Letter|Epistle|Book|On the duties of the Clergy)\b", re.I)
NOT_A_FATHER = re.compile(r"(?i)^(?:lesson )?from the (?:holy )?gospel|^lesson from|^from the (?:book|letter|acts|"
                          r"first|second|third|epistle|prophet|lamentation|apocalypse|canticle|song)")
ORD = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh",
       "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth", "Nineteenth",
       "Twentieth", "Twenty-first", "Twenty-second", "Twenty-third", "Twenty-fourth"]
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def fetch():
    """The project's English texts (a sparse, shallow clone; scripts/.cache, not in git)."""
    if not ENGLISH.exists():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                        "https://github.com/DivinumOfficium/divinum-officium.git", str(REPO)], check=True)
        subprocess.run(["git", "-C", str(REPO), "sparse-checkout", "set", "web/www/horas/English"], check=True)


def tempora_name(code: str) -> "tuple[tuple, str] | None":
    """(sort key, English name) for a season's file: "Adv1-0" -> First Sunday of Advent."""
    m = re.fullmatch(r"(Adv|Epi|Quadp|Quad|Pasc|Pent)(\d+)-(\d)", code)
    if m:
        season, w, d = m[1], int(m[2]), int(m[3])
        order = ["Adv", "Nat", "Epi", "Quadp", "Quad", "Pasc", "Pent"].index(season)
        if season == "Quadp":
            sunday = ["", "Septuagesima", "Sexagesima", "Quinquagesima"][w]
            name = f"{sunday} Sunday" if d == 0 else ("Ash Wednesday" if (w, d) == (3, 3) else
                                                          f"{DAYS[d]} after {sunday}")
        elif season == "Pasc" and w == 0:
            name = "Easter Sunday" if d == 0 else f"Easter {DAYS[d]}"
        elif season == "Pasc" and (w, d) == (5, 4):
            name = "The Ascension"
        elif season == "Pasc" and w == 7:
            name = "Pentecost Sunday" if d == 0 else f"{DAYS[d]} in Whitsun Week"
        elif season == "Quad" and w == 5 and d == 0:
            name = "Passion Sunday"
        elif season == "Quad" and w == 6:
            name = "Palm Sunday" if d == 0 else f"{DAYS[d]} in Holy Week"
        else:
            where = {"Adv": "of Advent", "Epi": "after the Epiphany", "Quad": "of Lent", "Pasc": "after Easter",
                     "Pent": "after Pentecost"}[season]
            name = f"{ORD[w]} Sunday {where}" if d == 0 else f"{DAYS[d]} of the {ORD[w].lower()} week {where}"
        return (1, order, w, d), name
    m = re.fullmatch(r"Nat(\d\d)", code)
    if m:
        n = int(m[1])
        return ((1, 1, 0, n) if n >= 24 else (1, 1, 1, n)), (f"{n} December" if n >= 24 else f"{n} January")
    m = re.fullmatch(r"Nat(\d)-0", code)
    if m:
        return (1, 1, 2, int(m[1])), ["", "Sunday within the Octave of Christmas", "Sunday of the Holy Name"][int(m[1])]
    m = re.fullmatch(r"(\d\d)(\d)-(\d)", code)                          # (the Sundays of August to November)
    if m:
        month, w, d = int(m[1]), int(m[2]), int(m[3])
        name = f"{ORD[w]} Sunday of {MONTHS[month]}" if d == 0 else f"{DAYS[d]} of the {ORD[w].lower()} week of {MONTHS[month]}"
        return (1, 7, month, w * 10 + d), name
    return None


def day_name(folder: str, stem: str, text: str) -> "tuple[tuple, str]":
    officium = re.search(r"(?m)^\[Officium\]\s*\n(.+)", text)
    title = officium[1].strip() if officium else ""
    base = re.match(r"[^a-z]*\d(?:-\d)?|[A-Za-z]+\d+(?:-\d)?", stem)
    if folder == "Tempora":
        found = tempora_name(re.sub(r"(?<=\d)[A-Za-z]+$", "", stem))
        if found:
            return found
        return (1, 9, 0, 0), title or stem
    if folder == "Sancti":
        m = re.match(r"(\d\d)-(\d\d)", stem)
        if m:
            date = f"{int(m[2])} {MONTHS[int(m[1])]}"
            return (2, int(m[1]), int(m[2]), 0), f"{date}: {title}" if title else date
    latin = {"Commune Apostolorum": "Common of Apostles", "Commune Evangelistarum": "Common of Evangelists",
             "In Festis Beatae Mariae Virginis": "Common of Feasts of the Blessed Virgin Mary",
             "Commune Plurimorum Martyrum Pontificum": "Common of Many Martyr Bishops"}   # (left in Latin there)
    return (3, 0, 0, 0), latin.get(title, title or stem)


def tidy(line: str) -> str:
    line = line.replace("(the Great,)", "(the Great)").replace(",)", ")")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def readings_of(text: str) -> list:
    """[(heading, source, gospel, text)] for the day's readings from the Fathers."""
    lessons = dict(re.findall(r"(?ms)^\[Lectio(\d+)\][ \t]*\n(.*?)(?=^\[|\Z)", text))
    out, cur = [], None
    for n in sorted(lessons, key=int):
        lines = [l.strip() for l in lessons[n].strip().split("\n") if l.strip()]
        if not lines or lines[0].startswith("@"):
            cur = None
            continue
        gospel = ""
        if "_" in lines:                                            # (the Gospel, then the homily on it)
            g = lines[:lines.index("_")]
            gospel = next((l[1:].strip() for l in g if l.startswith("!")), "")
            lines = lines[lines.index("_") + 1:]
        first = lines[0] if lines else ""
        if HEAD.match(first) and not NOT_A_FATHER.match(first):
            src = lines[1][1:].strip() if len(lines) > 1 and lines[1].startswith("!") else ""
            body = lines[2:] if src else lines[1:]
            cur = [tidy(first), tidy(src), gospel, body_text(body)]
            out.append(cur)
        elif cur is not None and first and not first.startswith("!") and not NOT_A_FATHER.match(first):
            cur[3] += "\n" + body_text(lines)
        else:
            cur = None
    return [r for r in out if r[3].strip()]


def body_text(lines: list) -> str:
    keep = [l for l in lines if not re.match(r"[$&@!]", l)]           # (the project's macros and references)
    t = "\n".join(re.sub(r"\s+", " ", html.unescape(l)) for l in keep)
    t = t.replace("*", "")                                              # (a chanting mark, not emphasis)
    return t.strip()


def main():
    fetch()
    days, seen = [], set()
    for folder in ("Tempora", "Sancti", "Commune"):
        for f in sorted((ENGLISH / folder).glob("*.txt")):
            text = f.read_text(encoding="utf-8", errors="replace")
            found = []
            for head, src, gospel, body in readings_of(text):
                key = re.sub(r"\W+", "", body.lower())[:400]
                if key in seen:
                    continue
                seen.add(key)
                found.append((head, src, gospel, body))
            if found:
                key, name = day_name(folder, f.stem, text)
                days.append((key, f.stem, name, found))
    days.sort(key=lambda d: (d[0], d[1]))
    chapters, notes = {}, {}
    for i, (_, stem, name, found) in enumerate(days, 1):
        verses = {}
        for j, (head, src, gospel, body) in enumerate(found, 1):
            lead = [f"*{name}*"] if j == 1 else []
            lead.append(f"*{head}*" + (f" ({src})" if src else ""))
            if gospel:
                lead.append(f"*On {gospel}*")
                notes[f"{i}:{j}"] = {"gospel": gospel}
            verses[str(j)] = "\n".join(lead + [body])
        chapters[str(i)] = verses
    data = {"source": "the Roman Breviary in English (Divinum Officium)", "books": {BOOK: chapters}, "gospels": notes}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(c) for c in chapters.values())
    print(f"{BOOK}: {len(chapters)} days, {n} readings ({len(notes)} on a Gospel) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
