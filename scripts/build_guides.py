"""
The two PDF guides to send to people (printed from HTML by Microsoft Edge or Chrome):

  python scripts/build_guides.py              both, into guides/ (not kept in git)
  python scripts/build_guides.py features     ScriptureBot features.pdf: INTRODUCTION.md, every command explained
  python scripts/build_guides.py library      ScriptureBot library.pdf: every work in !books, each with a command
                                              that opens it
  ... --out C:/somewhere                      somewhere else

Every command in the library guide is tried against the bot first, and the build stops if one
doesn't work (the online collections, Sefaria's and the hadith, need the internet for that).
"""
import argparse
import datetime
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]

STYLE = """
:root { --ink:#2b2418; --muted:#6b5d45; --gold:#a8822e; --rule:#e3d6b8; --code:#f4ecdb; }
body { font-family: Georgia, "Times New Roman", "Segoe UI Emoji", serif; color: var(--ink); margin: 0; }
.cover { display: flex; flex-direction: column; justify-content: center; text-align: center; break-after: page; }
.cover .mark { font-family: "Segoe UI Emoji", sans-serif; }
.cover .sub { color: var(--muted); font-style: italic; margin: 0 auto; }
.cover .rule { width: 1.6in; border-top: 2px solid var(--gold); margin: 20pt auto; }
.cover ul { list-style: none; padding: 0; columns: 2; column-gap: 0.4in; text-align: left; margin: 0 auto;
            color: var(--muted); }
.cover li { break-inside: avoid; }
.e { font-family: "Segoe UI Emoji", sans-serif; margin-right: 6pt; font-style: normal; }
code { font-family: Consolas, "Courier New", monospace; background: var(--code); padding: 0.5pt 3pt;
       border-radius: 3px; white-space: nowrap; }
"""


def to_pdf(page: str, out: Path) -> Path:
    """Print an HTML page to `out` (the HTML is kept beside it, to look at in a browser)."""
    browser = next((b for b in BROWSERS if Path(b).exists()), None) or shutil.which("msedge") or shutil.which("chrome")
    if not browser:
        sys.exit("Needs Microsoft Edge or Google Chrome to print the PDF.")
    page_path = out.with_suffix(".html")
    page_path.write_text(page, encoding="utf-8")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", page_path.as_uri()], check=True, timeout=600)
    print(f"{out} ({out.stat().st_size // 1000:,} kB)")
    return out


def inline(s: str) -> str:
    """The introduction's markdown, inline: `code`, **bold**, *italics* (code first, so **`!x`** stays bold)."""
    codes = []

    def stash(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    s = re.sub(r"`([^`]+)`", stash, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return re.sub("\x00(\\d+)\x00", lambda m: codes[int(m.group(1))], s)


def _titled(title: str) -> str:
    emoji, _, words = title.partition(" ")
    return f"<span class='e'>{html.escape(emoji)}</span>{html.escape(words)}"


# ── the features guide ──────────────────────────────────────────────────────

# INTRODUCTION.md is written for people in a server with the bot; the guide goes to people without one
FOR_OUTSIDERS = [
    ("that lives in this server.", "that lives in your Discord server."),
    ("The messages below are the full tour", "The pages below are the full tour"),
    ("where I announce my updates (like this channel);", "where I announce my updates;"),
    ("Below are my most recent updates — new ones will appear here as they happen. Welcome! 📖", ""),
]


def features(out_dir: Path) -> Path:
    text = re.sub(r"<!--.*?-->\s*", "", (ROOT / "INTRODUCTION.md").read_text(encoding="utf-8"))
    for old, new in FOR_OUTSIDERS:
        if old not in text:
            sys.exit(f"INTRODUCTION.md changed: update FOR_OUTSIDERS ({old!r})")
        text = text.replace(old, new)
    sections = [(t.strip(), b.strip()) for t, _, b in
                (block.partition("\n") for block in re.split(r"^## ", text, flags=re.M)[1:])]

    def body_html(body):
        out, bullets = [], []
        for line in body.split("\n") + [""]:
            line = line.rstrip()
            if line.startswith("• "):
                bullets.append(inline(line[2:]))
                continue
            if bullets:
                out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
                bullets = []
            if line:
                out.append(f"<p>{inline(line)}</p>")
        return "\n".join(out)

    toc = "".join(f"<li>{_titled(t)}</li>" for t, _ in sections)
    content = "".join(f"<section><h2>{_titled(t)}</h2>{body_html(b)}</section>" for t, b in sections)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>ScriptureBot Features</title>
<style>{STYLE}
@page {{ size: Letter; margin: 0.75in 0.8in; }}
body {{ font-size: 10.5pt; line-height: 1.5; }}
.cover {{ height: 9.2in; }}
.cover .mark {{ font-size: 54pt; }}
.cover h1 {{ font-size: 38pt; margin: 10pt 0 6pt; letter-spacing: 0.5pt; }}
.cover .sub {{ font-size: 14pt; max-width: 5in; }}
.cover ul {{ max-width: 5.6in; font-size: 10.5pt; }}
.cover li {{ margin: 3pt 0; }}
.cover .contents {{ font-variant: small-caps; letter-spacing: 1pt; color: var(--gold); margin-bottom: 8pt; }}
section {{ margin-bottom: 18pt; }}
h2 {{ font-size: 17pt; margin: 22pt 0 8pt; padding-bottom: 4pt; border-bottom: 1.5px solid var(--rule); break-after: avoid; }}
section:first-of-type h2 {{ margin-top: 0; }}
p {{ margin: 0 0 7pt; orphans: 3; widows: 3; }}
ul {{ margin: 0 0 8pt; padding-left: 16pt; }}
li {{ margin-bottom: 3pt; }}
code {{ font-size: 9pt; }}
</style></head><body>
<div class="cover"><div class="mark">📖</div><h1>ScriptureBot</h1>
<div class="sub">A Discord bot that brings the Bible, and the sacred and ancient texts of the world, into your server</div>
<div class="rule"></div><div class="contents">Contents</div><ul>{toc}</ul></div>
{content}
</body></html>"""
    return to_pdf(page, out_dir / "ScriptureBot features.pdf")


# ── the library guide ───────────────────────────────────────────────────────

# How each collection is cited where it isn't plain chapter:verse. Every command here is tried first.
NOTES = {
    "📖 The Bible": "Chapter and verse: `!verse John 3:16`, a range `!verse Genesis 1:1-5`, across chapters "
                   "`!verse John 7:53-8:11`, or a whole chapter `!verse Psalm 23`. Add a translation's short name "
                   "for another of the 40-odd translations, `!verse John 3:16 ESV`, or several to compare them, "
                   "`!verse John 3:16 KJV ESV NKJV`; `!translations` lists them all.",
    "Apocrypha (KJV)": "The Epistle of Jeremiah is chapter 6 of Baruch in the King James Bible: "
                       "`!verse Epistle of Jeremiah 1:5` and `!verse Baruch 6:5` are the same verse.",
    "Mishnah": "Tractate, chapter and mishnah: `!verse Berakhot 1:1`. These come from Sefaria's online library.",
    "Tosefta": "Tractate, chapter and halakhah: `!verse Tosefta Berakhot 1:1` (from Sefaria).",
    "Babylonian Talmud": "Tractate and page (daf), side a or b: `!verse Berakhot 2a`, or one section of it: "
                         "`!verse Berakhot 2a:3` (from Sefaria).",
    "Jerusalem Talmud": "Tractate, chapter and halakhah: `!verse Jerusalem Talmud Berakhot 1:1` (from Sefaria).",
    "Targumim": "The Aramaic translations, by the Bible's chapter and verse: `!verse Targum Onkelos Genesis 1:1`.",
    "Midrash": "Section and subsection: `!verse Bereshit Rabbah 1:1` (from Sefaria).",
    "Maimonides": "Chapter and halakhah: `!verse Mishneh Torah, Foundations of the Torah 1:1` (from Sefaria).",
    "Kabbalah": "The Zohar by parashah and segment: `!verse Zohar Bereshit 5`. Anything else in Sefaria's "
                "library in English works by its name there too, such as `!verse Rashi on Genesis 1:1`.",
    "Quran": "Surah and verse: `!verse Quran 2:255`, in Abdel Haleem's translation. Name one of the 52 other "
             "translations after it for that one, `!verse Quran 2:255 arberry`; `!help islamic` lists them.",
    "Hadith": "Collection and hadith number: `!verse Sahih al-Bukhari 1`.",
    "Sufi & Persian Poetry": "Rumi's Masnavi by book and story: `!verse Masnavi 1.0` is the song of the reed flute.",
    "Platonic": "Plato by the Stephanus page-and-section numbers printed in every edition: "
                              "`!verse Republic 514a`, or a stretch, `!verse Republic 514a-515c`.",
    "Epic Poetry": "Homer by book and line: `!verse Iliad 6.440`.",
    "Aristotelian": "Works in several books by book.chapter: `!verse Physics 8.10:1`.",
    "The Perseus Library": "By the book and section numbers scholars use: "
                           "`!verse History of the Peloponnesian War 2.40`.",
    "Buddhist": "The whole Pali Canon by its standard numbers too, from SuttaCentral: `!verse MN 1`, "
                "`!verse SN 56.11`.",
    "Bhagavad Gita": "Chapter and verse, in Shri Purohit Swami's translation: `!verse Gita 2:47`. Name another "
                     "translation or a commentary after it: `!verse Gita 2:47 sivananda` (`!help gita` lists them).",
    "Upanishads": "`!verse Chandogya Upanishad 6.8:7`, the famous \"thou art that\".",
    "🪯 Sikh": "By page (ang) and line, as Sikhs cite it: `!verse Guru Granth Sahib 1:1`; "
              "the Dasam Granth by page: `!verse Dasam Granth 1`.",
    "🤚 Jain": "By book, lecture and lesson: `!verse Akaranga Sutra 1.1.1`.",
    "Confucius & Mencius": "`!verse Analects 2.4`; Mencius by book, part and chapter: `!verse Mencius 6.1.2`.",
    "Medieval Classics": "Dante by canto and line: `!verse Inferno 1.1`.",
    "Swedenborg": "By his own section numbers: `!verse Heaven and Hell 51`.",
    "The Reformation": "Calvin's Institutes by book, chapter and section: `!verse Calvin's Institutes 1.1.1`.",
    "Mesopotamian": "Gilgamesh by tablet and section: `!verse Gilgamesh 11:1`.",
    "Canaanite": "The Baal Cycle by episode and section: `!verse Baal 1:1`.",
    "Church History": "Bede by book and chapter: `!verse Bede 3.5:1`. The Golden Legend has a chapter for each "
                      "life, in its own order (`!verse Golden Legend 54` is St Benedict); "
                      "`!saint` finds a saint's life by name.",
}
HOW_TO_EXAMPLES = ["Jn 3:16", "Confessions 1.1:1", "Genesis 1:1-5", "Against Heresies 3.3:1", "Heaven and Hell 51",
                   "Bede 3.5:1", "Adv Haer 4.20:7"]
# the online collections, cited as !help documents them (tried live, one per collection)
ONLINE = {"Mishnah": "{} 1:1", "Babylonian Talmud": "{} 2a", "Jerusalem Talmud": "{} 1:1", "Tosefta": "{} 1:1",
          "Targumim": "{} 1:1", "Midrash": "{} 1:1", "Maimonides": "{} 1:1"}


def library_rows(lookup, books) -> list:
    """[{"path", "name", "example"}] for every work in the !books tree, each example tried against the bot."""
    def works(ref):
        try:
            return bool(lookup.get_verse(ref, _quran_api=False).get("found"))
        except Exception:
            return False

    def local_example(name):
        corpus, canon = lookup._resolve_book(name)
        if canon is None:
            return None
        chapters = lookup._data[corpus][canon]
        keys = [c for c, v in chapters.items() if v]
        keys = sorted(keys[:6], key=lambda c: (not c.isdigit(), keys.index(c)))      # "1" before "Pref.1"
        keys += [k for k in ("1.1", "1") if k in chapters and k not in keys]        # (after a preface)
        for first in keys:
            verse = next(iter(chapters[first])) if isinstance(chapters[first], dict) else "1"
            for ref in (f"{name} {first}:{verse}", f"{name} {first}", f"{canon} {first}:{verse}", f"{canon} {first}"):
                if works(ref):
                    return ref
        return None

    def online_example(path, name):
        for key, form in ONLINE.items():
            if key in path:
                return form.format(name), True
        if "Hadith" in path:                    # by hadith number (Sahih Muslim's first two have no English)
            return next((f"{name} {n}" for n in (1, 3, 5) if lookup.get_verse(f"{name} {n}").get("found")), None), True
        if m := re.match(r"Quran (\d+) — ", name):
            return f"Quran {m.group(1)}:1", True
        if m := re.match(r"(Gilgamesh|Baal) (\d+) — ", name):
            return f"{m.group(1)} {m.group(2)}:1", False
        if name.startswith("Zohar "):
            return f"{name} 1", True
        if "Kabbalah" in path:
            return f"{name} 1:1", True
        return None, False

    rows, failures, checked = [], [], set()

    def walk(node, path):
        for item in node:
            if isinstance(item, tuple):
                walk(item[1], path + [item[0]])
                continue
            example = local_example(item)
            if example is None and item == "Epistle of Jeremiah":
                example = "Baruch 6:1"
            if example is None:
                example, online = online_example(path, item)
                collection = path[2] if len(path) > 2 else path[-1]
                if example and (not online or collection not in checked):
                    checked.add(collection)
                    if not lookup.get_verse(example).get("found"):
                        example = None
            if example is None:
                failures.append(f"{' > '.join(path)} > {item}")
            rows.append({"path": path, "name": item, "example": example})
    walk(books.ROOT_BOOKS_TREE, [])
    if failures:
        sys.exit("No working command for:\n  " + "\n  ".join(failures))
    return rows


def check_notes(lookup):
    from translation_lookup import TRANSLATION_SUFFIXES, get_parallel, get_translation

    def found(ref):                   # as !verse does it: a translation's name at the end goes to bolls.life
        tokens, names = ref.split(), []
        while tokens and tokens[-1].lower() in TRANSLATION_SUFFIXES:
            names.insert(0, tokens.pop())
        result = (get_parallel(" ".join(tokens), names) if len(names) > 1 else
                  get_translation(" ".join(tokens), names[0]) if names else lookup.get_verse(ref))
        return result.get("found")
    refs = [r for note in NOTES.values() for r in re.findall(r"`!verse ([^`]+)`", note)] + HOW_TO_EXAMPLES
    bad = [r for r in refs if not found(r)]
    if bad or not lookup.random_verse_from_book("Proverbs").get("found"):
        sys.exit(f"Commands in the guide's notes that don't work: {bad}")


def library(out_dir: Path) -> Path:
    import bot  # noqa: F401  (loads the library and builds the !books tree)
    from bot_commands import books
    from core import lookup
    check_notes(lookup)
    rows = library_rows(lookup, books)
    surahs = [r for r in rows if "Quran" in r["path"]]
    rows = [r for r in rows if "Quran" not in r["path"]]
    if surahs:                                         # the 114 surahs are one entry
        rows.insert(next(i for i, r in enumerate(rows) if "☪️ Islamic" in r["path"]),
                    {"path": surahs[0]["path"], "name": "The Quran (114 surahs)", "example": "Quran 2:255"})

    def note_for(path):
        for key, note in NOTES.items():
            if any(key == p or (key in p and not key.startswith(("📖", "🪯", "🤚"))) for p in path):
                yield key, note

    body, toc, last, cols, seen = [], [], [None] * 4, False, set()
    for r in rows:
        path = r["path"]
        group, category = path[0], path[1]
        collection = path[2] if len(path) > 2 else ""
        sub = " · ".join(path[3:])
        if cols and (group, category, collection) != tuple(last[:3]):
            body.append("</div>")
            cols = False
        if group != last[0]:
            body.append(f"<h1>{_titled(group)}</h1>")
            toc.append(f"<li class='g'>{_titled(group)}</li>")
            last = [group, None, None, None]
        if category != last[1]:
            body.append(f"<h2>{_titled(category)}</h2>")
            toc.append(f"<li>{html.escape(category.partition(' ')[2])}</li>")
            last[1:] = [category, None, None]
        if collection != last[2]:
            if collection:
                body.append(f"<h3>{html.escape(collection)}</h3>")
            last[2:] = [collection, None]
            for key, note in note_for(path[1:3]):
                if key not in seen:
                    seen.add(key)
                    body.append(f"<p class='note'>{inline(note)}</p>")
        if not cols:
            body.append("<div class='cols'>")
            cols = True
        if sub != last[3]:
            if sub:
                body.append(f"<div class='sub'>{html.escape(sub)}</div>")
            last[3] = sub
        body.append(f"<div class='w'><span class='n'>{html.escape(r['name'])}</span>"
                    f"<code>!verse {html.escape(r['example'])}</code></div>")
    if cols:
        body.append("</div>")
    if set(NOTES) - seen:
        sys.exit(f"Notes for collections that aren't in !books any more: {set(NOTES) - seen}")

    day = datetime.date.today()
    works = len(rows) + max(len(surahs) - 1, 0)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>ScriptureBot Library</title>
<style>{STYLE}
@page {{ size: Letter; margin: 0.65in 0.6in; }}
body {{ font-size: 9pt; line-height: 1.35; }}
.cover {{ height: 9.4in; }}
.cover .mark {{ font-size: 50pt; }}
.cover h1 {{ font-size: 36pt; margin: 8pt 0 4pt; border: 0; break-before: avoid; }}
.cover .sub {{ font-size: 14pt; }}
.cover ul {{ max-width: 6in; font-size: 9.5pt; }}
.cover li {{ margin: 1.5pt 0; }}
.cover li.g {{ color: var(--gold); font-variant: small-caps; letter-spacing: 0.5pt; margin-top: 8pt; }}
.how {{ break-after: page; font-size: 10.5pt; line-height: 1.5; }}
.how h1 {{ break-before: avoid; }}
.how p {{ margin: 0 0 8pt; }}
.how li {{ margin-bottom: 5pt; }}
h1 {{ font-size: 20pt; margin: 0 0 10pt; padding-bottom: 4pt; border-bottom: 2px solid var(--gold); break-before: page; }}
h2 {{ font-size: 14pt; margin: 14pt 0 4pt; padding-bottom: 2pt; border-bottom: 1px solid var(--rule); break-after: avoid; }}
h3 {{ font-size: 10.5pt; margin: 9pt 0 3pt; color: var(--muted); font-variant: small-caps; letter-spacing: 0.4pt;
      break-after: avoid; }}
.note {{ margin: 0 0 5pt; padding: 4pt 7pt; background: #faf5ea; border-left: 2px solid var(--gold);
         font-size: 8.8pt; break-inside: avoid; }}
.cols {{ columns: 2; column-gap: 0.3in; column-rule: 0.5px solid var(--rule); margin-bottom: 4pt; }}
.sub {{ font-weight: bold; margin: 6pt 0 1pt; font-size: 9pt; break-after: avoid; }}
.w {{ display: flex; justify-content: space-between; gap: 10pt; padding: 1.2pt 0;
      border-bottom: 0.5px dotted #e6dcc6; break-inside: avoid; }}
.w .n {{ flex: 1; }}
code {{ font-size: 8pt; }}
.w code {{ align-self: flex-start; }}
.how code, .note code {{ font-size: 8.4pt; }}
</style></head><body>
<div class="cover"><div class="mark">📚</div><h1>The ScriptureBot Library</h1>
<div class="sub">Every work in the library, and how to look it up</div><div class="rule"></div>
<ul>{''.join(toc)}</ul></div>
<div class="how">
  <h1>How to look things up</h1>
  <p>Every work in this guide can be read in Discord with <code>!verse</code> (or <code>/verse</code>), followed by the
  work and a place in it. Beside each work is a command that opens it, so copy that and change the numbers.</p>
  <ul>
    <li><b>Chapter and verse</b>, for most works: <code>!verse John 3:16</code>, <code>!verse Confessions 1.1:1</code>.
    A range works too: <code>!verse Genesis 1:1-5</code>.</li>
    <li><b>Works in several books</b> take the book first, then the chapter, then the section:
    <code>!verse Against Heresies 3.3:1</code> is Irenaeus, Book III, chapter 3, section 1.</li>
    <li><b>Works numbered straight through</b> take one number: <code>!verse Heaven and Hell 51</code>.</li>
    <li><b>Some traditions have their own systems</b>: the Talmud by page, Plato by Stephanus number, Homer by line,
    the hadith by number. Each collection's way is explained at the top of its section.</li>
    <li><b>Just the name</b> gives a random passage from that work: <code>!verse Proverbs</code>.</li>
    <li><b>Short names and abbreviations</b> work for the common ones: <code>!verse Jn 3:16</code>,
    <code>!verse Bede 3.5:1</code>, <code>!verse Adv Haer 4.20:7</code>. A name I don't know gets a
    "did you mean" with the likeliest books to choose from.</li>
  </ul>
  <p><b>Browsing:</b> <code>!books</code> opens a menu of the whole library by tradition, collection and book, and
  <code>!books Augustine</code> lists one author's works. <code>!search</code> finds a word or phrase anywhere:
  <code>!search shepherd</code>, or in one tradition, <code>!search nirvana in:buddhist</code>.</p>
  <p><b>Online collections.</b> The Talmud, Mishnah, Midrash and other rabbinic works come from Sefaria's library;
  the hadith, the Quran's translations, the Pali Canon and some Sikh scriptures come from other online libraries.
  They need those sites to be up; everything else is stored in the bot.</p>
  <p style="color:var(--muted); font-size:9pt">{works:,} works. Every command in this guide was checked against the
  bot on {day:%B} {day.day}, {day.year}.</p>
</div>
{''.join(body)}
</body></html>"""
    return to_pdf(page, out_dir / "ScriptureBot library.pdf")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("which", nargs="?", choices=["features", "library", "all"], default="all")
    parser.add_argument("--out", type=Path, default=ROOT / "guides")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.which in ("features", "all"):
        features(args.out)
    if args.which in ("library", "all"):
        library(args.out)
