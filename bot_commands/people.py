"""
!who and !place: the people and places of the Bible (data/people_places/,
built by scripts/build_people_places.py from Theographic Bible Metadata).
  !who Ruth               who she was, her family, every verse naming her
  !who Mary               several Marys: pick one from the list
  !place Bethel           where it is (a map card), what happened there, its verses
  !place Galaad           found by any Bible's spelling (Hebrew, Septuagint, Vulgate, Douay-Rheims, NRSV)
  !place Acts             every place a book names, on one map (or a passage: !place Genesis 12-13)
Names in the family lists open with the menu under the card, so you can walk
a family tree (Ruth -> Obed -> Jesse -> David).
"""
import asyncio
import functools
import json
import re
import unicodedata

import discord
from discord import app_commands

from core import ROOT, bot, log, lookup

DATA_PATH = ROOT / "data" / "people_places" / "people_places.json"
NAMES_PATH = ROOT / "data" / "people_places" / "place_names.json"      # scripts/build_place_names.py
APOCRYPHA_PATH = ROOT / "data" / "people_places" / "apocrypha_places.json"   # the same
# the Bibles whose spellings a place card shows, in the order it shows them
NAME_LABELS = [("hebrew", "Hebrew"), ("greek", "Greek"), ("latin", "Latin (Vulgate)"), ("kjv", "KJV"),
               ("douay", "Douay-Rheims"), ("nrsv", "NRSV")]
SOURCE = "Theographic, Easton, OpenBible.info"
PERSON_COLOR = discord.Color.from_rgb(150, 90, 40)
PLACE_COLOR = discord.Color.from_rgb(60, 120, 90)
SHOW_VERSES = 40


@functools.lru_cache(maxsize=1)
def data() -> dict:
    d = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    try:
        names = json.loads(NAMES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        names = {}
    try:                                                # the places only the Apocrypha name (Bethulia, Modein)
        d["places"].update(json.loads(APOCRYPHA_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    for slug, p in d["places"].items():
        p["slug"] = slug
        p["names"] = names.get(slug, {})
        p["apocrypha"] = p["names"].get("apocrypha", [])
    for slug, p in d["people"].items():
        p["slug"] = slug
    # who was born / died where, for the place cards
    for slug, p in d["people"].items():
        for key, label in (("born", "born"), ("died", "died")):
            for place in p[key]:
                if place in d["places"]:
                    d["places"][place].setdefault(label + "_here", []).append(slug)
    return d


def _norm(text: str) -> str:
    """Lower case, without accents or vowel points, in any script: "Γαλαάδ" -> "γαλααδ", "Ægyptus" -> "aegyptus"."""
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch) and unicodedata.category(ch) != "Lm")
    text = text.lower().replace("æ", "ae").replace("œ", "oe").replace("ς", "σ").replace("'", "").replace("’", "")
    text = re.sub(r"[^\w() ]+|_", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _bare(name: str) -> str:
    return _norm(re.sub(r"\s*\(.*\)$", "", name))


@functools.lru_cache(maxsize=2)
def _index(kind: str) -> dict:
    """normalised name -> [slug, ...]: each entity under its full title, its bare name and aliases."""
    index: dict = {}
    for slug, e in data()[kind].items():
        names = {_norm(e["name"]), _bare(e["name"]), *(_norm(a) for a in e.get("also", []))}
        if kind == "people":
            names.add(_norm(e["short"]))
            words = re.sub(r"\s*\(.*\)$", "", e["name"]).split()
            if len(words) == 2 and words[1][0].isupper():      # "Simon Peter" is also just "Peter"
                names.add(_norm(words[1]))
        for n in names:
            if n:
                index.setdefault(n, []).append(slug)
    return index


def spellings(slug: str) -> dict:
    """A place's name in each Bible, {label: spelling}, and its spellings in the Apocrypha."""
    n = data()["places"][slug]["names"]
    out = {}
    for key, title in NAME_LABELS:
        value = n.get(key)
        if isinstance(value, dict):
            out[title] = value["text"]
            if value.get("translit"):
                out[title + " (in letters)"] = value["translit"]
        elif value:
            out[title] = value
    for i, s in enumerate(n.get("apocrypha_spellings", [])):
        out[f"Apocrypha {i}"] = s
    return out


@functools.lru_cache(maxsize=1)
def _spelling_index() -> dict:
    """normalised spelling -> [slug, ...]: each place under its other Bibles' names (Galaad, Γαλαάδ, גלעד)."""
    index: dict = {}
    for slug in data()["places"]:
        for s in spellings(slug).values():
            n = _norm(s)
            if n and slug not in index.get(n, []):
                index.setdefault(n, []).append(slug)
    return index


def spelled_as(slug: str, query: str) -> list:
    """Which Bibles spell this place as `query` ("Galaad": the Vulgate and the Douay-Rheims)."""
    q = _norm(query)
    said = {"Latin (Vulgate)": "the Vulgate"}
    out = []
    for k, v in spellings(slug).items():
        if _norm(v) == q:
            k = "the Apocrypha" if k.startswith("Apocrypha") else k.replace(" (in letters)", "")
            k = said.get(k, k if k.startswith("the ") else "the " + k)
            if k not in out:
                out.append(k)
    return out


def weight(kind: str, slug: str) -> int:
    e = data()[kind][slug]
    return len(e["verses"]) + len(e.get("apocrypha", []))


def find(kind: str, query: str, prefix: bool = True) -> list:
    """Matching slugs, most-mentioned first. (A slug itself, from autocomplete, is an exact match.) `prefix`: if
    no name matches, names that begin with the query ("Nebuchad")."""
    if query.strip() in data()[kind]:
        return [query.strip()]
    q = _norm(query)
    q = re.sub(r"^(the|saint|st) ", "", q)
    if not q:
        return []
    index = _index(kind)
    slugs = list(index.get(q, []))
    if not slugs and kind == "places":                   # another Bible's spelling: Galaad, Bethsura, Γαλααδ
        slugs = list(_spelling_index().get(q, []))
    if not slugs and prefix:
        # "John the Baptist" -> the John whose title has "Baptist"; or a prefix ("Nebuchad")
        slugs = [s for n, ss in index.items() if n.startswith(q) for s in ss]
    return sorted(set(slugs), key=lambda s: -weight(kind, s))


def label(kind: str, slug: str) -> str:
    """A name that tells this one apart from others of the same name."""
    e = data()[kind][slug]
    if "(" in e["name"]:
        return e["name"]
    others = len(_index(kind).get(_norm(e["name"]), [])) > 1
    if kind == "people" and others:
        father = e["father"][0] if e["father"] else None
        if father:
            rel = "daughter" if e.get("gender") == "Female" else "son"
            return f"{e['name']}, {rel} of {data()['people'][father]['name']}"
    if others and e["verses"]:
        return f"{e['name']} ({e['verses'][0]})"
    return e["name"]


def compact_refs(refs: list, limit: int = SHOW_VERSES) -> str:
    """['Genesis 12:8', 'Genesis 13:3', 'Joshua 7:2'] -> 'Genesis 12:8; 13:3 · Joshua 7:2'"""
    groups, order = {}, []
    for ref in refs[:limit]:
        book, cv = ref.rsplit(" ", 1)
        if book not in groups:
            order.append(book)
        groups.setdefault(book, []).append(cv)
    text = " · ".join(f"{b} {'; '.join(groups[b])}" for b in order)
    if len(refs) > limit:
        text += f" … and {len(refs) - limit} more"
    if len(text) > 1020:
        text = text[:1000].rsplit(" ", 1)[0] + " …"
    return text


# ── people ──────────────────────────────────────────────────────────────────

def _names(slugs: list, limit: int = 12) -> str:
    people = data()["people"]
    names = [people[s]["name"] for s in slugs if s in people]
    return ", ".join(names[:limit]) + (f" and {len(names) - limit} more" if len(names) > limit else "")


def person_embed(slug: str) -> discord.Embed:
    p = data()["people"][slug]
    embed = discord.Embed(title=f"👤 {p['name']}", description=p["about"] or None, color=PERSON_COLOR)
    family = []
    for key, title in (("father", "Father"), ("mother", "Mother"), ("partners", "Married to"),
                       ("children", "Children"), ("siblings", "Brothers and sisters")):
        if p[key]:
            family.append(f"**{title}:** {_names(p[key])}")
    if family:
        embed.add_field(name="Family", value="\n".join(family)[:1024], inline=False)
    places = data()["places"]
    life = []
    if p["groups"]:
        life.append(f"**Of the** {', '.join(p['groups'])}")
    if p["born"]:
        life.append("**Born in** " + ", ".join(places[s]["name"] for s in p["born"] if s in places))
    if p["died"]:
        life.append("**Died in** " + ", ".join(places[s]["name"] for s in p["died"] if s in places))
    if p["also"]:
        life.append("**Also called** " + ", ".join(p["also"]))
    if life:
        embed.add_field(name="Life", value="\n".join(life)[:1024], inline=False)
    if p["verses"]:
        embed.add_field(name=f"Named in {len(p['verses'])} verse{'s' if len(p['verses']) != 1 else ''}",
                        value=compact_refs(p["verses"]), inline=False)
    embed.set_footer(text=f"{SOURCE} · !verse <reference> to read one")
    return embed


class PersonView(discord.ui.View):
    """A menu of this person's family: choosing one shows them in place of this card."""

    def __init__(self, slug: str):
        super().__init__(timeout=600)
        p = data()["people"][slug]
        options, seen = [], set()
        for key, rel in (("father", "father"), ("mother", "mother"), ("partners", "spouse"),
                         ("children", "child"), ("siblings", "sibling")):
            for s in p[key]:
                if s in seen or s not in data()["people"] or len(options) == 25:
                    continue
                seen.add(s)
                options.append(discord.SelectOption(label=label("people", s)[:100], value=s,
                                                    description=f"{p['name']}'s {rel}"[:100]))
        if options:
            select = discord.ui.Select(placeholder="Family: see someone else…", options=options)
            select.callback = self._chosen
            self.add_item(select)
            self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        slug = self.select.values[0]
        await interaction.response.edit_message(embed=person_embed(slug), view=PersonView(slug))


# ── places ──────────────────────────────────────────────────────────────────

def located_places() -> list:
    return [dict(p, weight=len(p["verses"]) + len(p["apocrypha"])) for p in data()["places"].values()
            if p["lat"] is not None]


def place_embed(slug: str, with_map: bool) -> discord.Embed:
    p = data()["places"][slug]
    embed = discord.Embed(title=f"📍 {p['name']}", description=p["about"] or None, color=PLACE_COLOR)
    facts = []
    if p["kind"]:
        facts.append(f"**Kind:** {p['kind']}")
    if p["within"]:
        facts.append("**Part of:** " + ", ".join(data()["places"][s]["name"] for s in p["within"]
                                                 if s in data()["places"]))
    if p["lat"] is not None:
        where = f"{abs(p['lat']):.3f}°{'N' if p['lat'] >= 0 else 'S'}, {abs(p['lon']):.3f}°{'E' if p['lon'] >= 0 else 'W'}"
        facts.append(f"**Location:** {where}" + (" (approximate: the site is uncertain)" if p["approx"] else ""))
    else:
        facts.append("**Location:** not known")
    if p.get("born_here"):
        facts.append("**Born here:** " + _names(p["born_here"], 8))
    if p.get("died_here"):
        facts.append("**Died here:** " + _names(p["died_here"], 8))
    embed.add_field(name="Facts", value="\n".join(facts)[:1024], inline=False)
    names = names_field(slug)
    if names:
        embed.add_field(name="In each Bible", value=names, inline=False)
    if p["verses"]:
        embed.add_field(name=f"Named in {len(p['verses'])} verse{'s' if len(p['verses']) != 1 else ''}",
                        value=compact_refs(p["verses"]), inline=False)
    if p["apocrypha"]:
        n = len(p["apocrypha"])
        embed.add_field(name=f"In the Apocrypha: {n} verse{'s' if n != 1 else ''}",
                        value=compact_refs(p["apocrypha"], 25), inline=False)
    if with_map:
        embed.set_image(url="attachment://map.png")
    if p["verses"]:
        source = SOURCE
    else:                                               # a place only the Apocrypha name: its site from Pleiades
        source = "Pleiades (the site) · the Apocrypha" if p.get("pleiades") else "the Apocrypha"
    embed.set_footer(text=f"{source} · map: Natural Earth")
    return embed


def names_field(slug: str) -> str:
    """The place's name in the Hebrew, the Septuagint's Greek, the Vulgate's Latin, the KJV, the Douay-Rheims
    and the NRSV, where they're known; the same name twice only once."""
    n = data()["places"][slug]["names"]
    lines, english = [], []
    for key, title in NAME_LABELS:
        value = n.get(key)
        if not value:
            continue
        if isinstance(value, dict):
            lines.append(f"**{title}:** {value['text']} ({value['translit']})" if value.get("translit")
                         else f"**{title}:** {value['text']}")
        elif key in ("kjv", "douay", "nrsv"):
            english.append((title, value))
        else:
            lines.append(f"**{title}:** {value}")
    if english:
        shown = {}
        for title, value in english:                  # "KJV, NRSV: Gilead · Douay-Rheims: Galaad"
            shown.setdefault(value[:1].upper() + value[1:], []).append(title)
        lines.append(" · ".join(f"**{', '.join(t)}:** {v}" for v, t in shown.items()))
    if n.get("apocrypha_spellings"):
        lines.append("**In the Apocrypha:** " + ", ".join(n["apocrypha_spellings"]))
    if len(lines) == 1 and not n.get("hebrew") and not n.get("greek") and not n.get("latin") \
            and len({v for _, v in english}) <= 1:
        return ""                                       # (only the English name the title already gives)
    return "\n".join(lines)[:1024]


async def map_file(slug: str) -> "discord.File | None":
    p = data()["places"][slug]
    if p["lat"] is None:
        return None
    import bible_map
    try:
        places = located_places()
        me = next(x for x in places if x["slug"] == slug)
        buf = await asyncio.to_thread(bible_map.render_map, me, places)
    except Exception:
        log.exception(f"Couldn't draw the map for {slug}")
        return None
    return discord.File(buf, filename="map.png")


async def send_place(target, slug: str) -> None:
    """`target`: a context (sends) or an interaction (replies)."""
    file = await map_file(slug)
    embed = place_embed(slug, with_map=file is not None)
    kwargs = {"embed": embed, **({"file": file} if file else {})}
    if isinstance(target, discord.Interaction):
        await target.followup.send(**kwargs)
    else:
        await target.send(**kwargs)


# ── family trees ────────────────────────────────────────────────────────────

def descent(ancestors: list, descendants: list) -> "list | None":
    """The shortest line from one of `ancestors` down to one of `descendants`
    (slugs), through fathers before mothers; None if there isn't one. The
    descendants are tried best-known first: "Jesus" means Jesus Christ, though
    a Joshua (also "Jesus" in Greek) may have a shorter line."""
    people = data()["people"]
    for start in descendants:
        prev, frontier = {start: None}, [start]
        found = None
        while frontier and not found:
            nxt = []
            for slug in frontier:
                for parent in people[slug]["father"] + people[slug]["mother"]:
                    if parent in people and parent not in prev:
                        prev[parent] = slug
                        nxt.append(parent)
                        if parent in ancestors:
                            found = parent
                            break
                if found:
                    break
            frontier = nxt
        if found:
            line = [found]
            while prev[line[-1]]:
                line.append(prev[line[-1]])
            return line
    return None


def _pick(query: str) -> list:
    """Candidates for a name in a tree request, best known first."""
    return find("people", query)[:6]


async def send_tree(ctx, query: str) -> None:
    import family_tree
    query = query.strip()
    if not query:
        await ctx.send("Usage: `!tree David` (a family tree), or `!tree Abraham to David` (a line of descent).")
        return
    parts = re.split(r"\s+to\s+", query, maxsplit=1, flags=re.I)
    people = data()["people"]
    if len(parts) == 2:
        first, second = _pick(parts[0]), _pick(parts[1])
        for name, found in ((parts[0], first), (parts[1], second)):
            if not found:
                await ctx.send(f"I don't know anyone in the Bible called **{name}**.")
                return
        line = descent(first, second) or descent(second, first)
        if not line:
            await ctx.send(f"I can't find a line of descent between **{label('people', first[0])}** and "
                           f"**{label('people', second[0])}**. The records only join parents and children where "
                           f"the Bible names them.")
            return
        buf = await asyncio.to_thread(family_tree.lineage_chart, line, people)
        names = " → ".join(family_tree.short_name(people[s]) for s in line)
        embed = discord.Embed(title=f"🌳 From {family_tree.short_name(people[line[0]])} to "
                                    f"{family_tree.short_name(people[line[-1]])}",
                              description=f"**{len(line)} generations:** {names}"[:4000], color=PERSON_COLOR)
    else:
        slugs = find("people", query)
        if not slugs:
            await ctx.send(f"I don't know anyone in the Bible called **{query}**.")
            return
        slug = slugs[0]
        buf = await asyncio.to_thread(family_tree.family_chart, slug, people)
        p = people[slug]
        embed = discord.Embed(title=f"🌳 The family of {p['name']}", color=PERSON_COLOR)
        line = family_tree.paternal_line(slug, people, limit=200)
        if line:
            embed.description = (f"{len(line)} generation{'s' if len(line) != 1 else ''} of fathers on record, back to "
                                 f"**{family_tree.short_name(people[line[-1]])}**. "
                                 f"Trace any line with `!tree {family_tree.short_name(people[line[-1]])} to "
                                 f"{family_tree.short_name(p)}`; more about anyone with `!who`.")
        note = _others_note("people", slugs, "tree") if not _clear_winner("people", slugs) else ""
        if note:
            await ctx.send(note)
    embed.set_image(url="attachment://tree.png")
    embed.set_footer(text="Theographic Bible Metadata · from the Bible's genealogies and family records")
    await ctx.send(embed=embed, file=discord.File(buf, filename="tree.png"))


# ── choosing among namesakes ────────────────────────────────────────────────

class Picker(discord.ui.View):
    def __init__(self, kind: str, slugs: list):
        super().__init__(timeout=300)
        self.kind = kind
        options = [discord.SelectOption(label=label(kind, s)[:100], value=s,
                                        description=f"named in {weight(kind, s)} verse(s)")
                   for s in slugs[:25]]
        select = discord.ui.Select(placeholder="Which one?", options=options)
        select.callback = self._chosen
        self.add_item(select)
        self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        slug = self.select.values[0]
        if self.kind == "people":
            await interaction.response.send_message(embed=person_embed(slug), view=PersonView(slug))
        else:
            await interaction.response.defer(thinking=True)
            await send_place(interaction, slug)


def _clear_winner(kind: str, slugs: list) -> bool:
    """One of several namesakes so much better known that it's surely the one meant."""
    return len(slugs) == 1 or weight(kind, slugs[0]) >= 4 * max(weight(kind, slugs[1]), 1)


def _others_note(kind: str, slugs: list, command: str) -> str:
    rest = slugs[1:6]
    if not rest:
        return ""
    return (f"Also by this name: " + "; ".join(label(kind, s) for s in rest)
            + (" …" if len(slugs) > 6 else "") + f" — `!{command} <name (which one)>` or `!{command} <name> all`")


async def lookup_person(ctx, query: str) -> None:
    query = query.strip()
    want_all = query.lower().endswith(" all")
    query = query[:-4] if want_all else query
    if not query:
        await ctx.send("Usage: `!who <name>` — e.g. `!who Ruth`, `!who Mary`, `!who John the Baptist`.")
        return
    slugs = find("people", query)
    if not slugs:
        await ctx.send(f"I don't know anyone in the Bible called **{query}**. "
                       f"Try `!dictionary {query}` or check the spelling.")
        return
    if not want_all and _clear_winner("people", slugs):
        embed = person_embed(slugs[0])
        note = _others_note("people", slugs, "who")
        content = note or None
        await ctx.send(content=content, embed=embed, view=PersonView(slugs[0]))
        return
    lines = [f"• **{label('people', s)}** — named in {weight('people', s)} verse(s)" for s in slugs[:25]]
    embed = discord.Embed(title=f"👤 {len(slugs)} people called {query.title()}",
                          description="\n".join(lines), color=PERSON_COLOR)
    embed.set_footer(text="Pick one below")
    await ctx.send(embed=embed, view=Picker("people", slugs))


def _and(items: list) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


@functools.lru_cache(maxsize=1)
def _place_books() -> set:
    return {r.rsplit(" ", 1)[0] for p in data()["places"].values() for r in p["verses"] + p["apocrypha"]}


_PASSAGE = re.compile(r"^\s*(.+?)(?:\s+(\d{1,3})(?::(\d{1,3}))?(?:\s*[-–—]\s*(\d{1,3})(?::(\d{1,3}))?)?)?\s*$")


def book_query(query: str) -> "tuple | None":
    """A book, or a passage of one, whose places to map: (book, first (chapter, verse), last (chapter, verse)),
    None for the whole book. "Acts" -> ("Acts", None, None); "Genesis 12" -> ("Genesis", (12, 0), (12, 999));
    "1 Maccabees 4:36-61" -> ("1 Maccabees", (4, 36), (4, 61)); "Genesis 12-13", "Acts 13:1-14:28" likewise."""
    m = _PASSAGE.match(query)
    if not m:
        return None
    name, c1, v1, x, v2 = m.groups()
    try:
        corpus, book = lookup._resolve_book(name)
    except Exception:
        return None
    if book not in _place_books():
        return None
    if not c1:
        return book, None, None
    c1 = int(c1)
    if v1 is None:                                   # Genesis 12 / Genesis 12-13
        c2 = int(x) if x and v2 is None else c1
        return book, (c1, 0), (c2, 999)
    v1 = int(v1)
    if x is None:                                    # Genesis 12:8
        return book, (c1, v1), (c1, v1)
    if v2 is None:                                   # 1 Maccabees 4:36-61
        return book, (c1, v1), (c1, int(x))
    return book, (c1, v1), (int(x), int(v2))         # Acts 13:1-14:28


def _where(book: str, start, end) -> str:
    if start is None:
        return book
    (c1, v1), (c2, v2) = start, end
    if v1 == 0:
        return f"{book} {c1}" if c1 == c2 else f"{book} {c1}-{c2}"
    if (c1, v1) == (c2, v2):
        return f"{book} {c1}:{v1}"
    return f"{book} {c1}:{v1}-{v2}" if c1 == c2 else f"{book} {c1}:{v1}-{c2}:{v2}"


def book_places(book: str, start=None, end=None) -> list:
    """[(slug, how many verses of the book, or of the passage from `start` to `end`, name it)], most-named first."""
    counts = {}
    for slug, p in data()["places"].items():
        for ref in p["verses"] + p["apocrypha"]:
            b, cv = ref.rsplit(" ", 1)
            if b != book:
                continue
            if start is not None:
                c, v = (int(x) for x in cv.split(":"))
                if not start <= (c, v) <= end:
                    continue
            counts[slug] = counts.get(slug, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], data()["places"][x[0]]["name"]))


def passage_order(book: str, start, end) -> list:
    """[((chapter, verse), [slug, ...]), ...]: the places of a passage verse by verse, in the verses' order."""
    verses = {}
    for slug, p in data()["places"].items():
        for ref in p["verses"] + p["apocrypha"]:
            b, cv = ref.rsplit(" ", 1)
            if b == book:
                c, v = (int(x) for x in cv.split(":"))
                if start <= (c, v) <= end:
                    verses.setdefault((c, v), []).append(slug)
    return [(cv, sorted(s, key=lambda x: -weight("places", x))) for cv, s in sorted(verses.items())]

async def send_book_map(ctx, book: str, start=None, end=None) -> None:
    """Every place a book (or a passage of it) names, on one map, and listed by how often."""
    where = _where(book, start, end)
    found = book_places(book, start, end)
    if not found:
        count = lookup.chapter_count(book) or 0
        bad = start is not None and count and not (1 <= start[0] <= count and 1 <= end[0] <= count) \
            or start is not None and start > end
        if bad and start <= end:
            await ctx.send(f"**{book}** has no chapter {max(start[0], end[0]) if start[0] >= 1 else start[0]}: "
                           f"it has {count}.")
        elif bad:
            await ctx.send(f"**{where}** runs backwards: try `!place {_where(book, end, start)}`.")
        else:
            await ctx.send(f"**{where}** names no places I know of.")
        return
    places = data()["places"]
    spots = [dict(places[s], count=n) for s, n in found if places[s]["lat"] is not None]
    file = None
    if spots:
        import bible_map
        try:
            buf = await asyncio.to_thread(bible_map.render_places, f"The places of {where}", spots)
            file = discord.File(buf, filename="map.png")
        except Exception:
            log.exception(f"Couldn't draw the map for {where}")
    unknown = len(found) - len(spots)

    bare = {s: re.sub(r"\s*\(.*\)$", "", places[s]["name"]) for s, _ in found}
    counts = list(bare.values())

    def name(s):                                    # the plain name, unless the list has two (Bethel (of Palestine))
        return bare[s] if counts.count(bare[s]) == 1 else label("places", s)
    listing = ""
    if start is not None:
        # a passage: the places verse by verse, in the order they come, if that fits
        lines = [f"**{c}:{v}** " + ", ".join(name(s) for s in slugs) for (c, v), slugs in passage_order(book, start, end)]
        listing = "\n".join(lines)
        if len(listing) <= 3600:
            head = f"**{len(found)} place{'s' if len(found) != 1 else ''}** named in {where}, in order" \
                   + (f" ({unknown} with no known site, so not on the map)" if unknown else "") + ":"
        else:
            listing = ""
    if not listing:
        head = f"**{len(found)} place{'s' if len(found) != 1 else ''}** named in {where}, the most often first" \
               + (f" ({unknown} with no known site, so not on the map)" if unknown else "") + ":"
        listing = " · ".join(f"{name(s)} ({n})" for s, n in found)
        if len(listing) > 3600:
            listing = listing[:3600].rsplit(" · ", 1)[0] + " …"
    embed = discord.Embed(title=f"🗺️ The places of {where}", description=head + "\n" + listing,
                          color=PLACE_COLOR)
    if file:
        embed.set_image(url="attachment://map.png")
    embed.set_footer(text=f"{SOURCE} · map: Natural Earth · !place <name> for one of them")
    await ctx.send(embed=embed, **({"file": file} if file else {}))

async def lookup_place(ctx, query: str) -> None:
    query = query.strip()
    want_all = query.lower().endswith(" all")
    query = query[:-4] if want_all else query
    if not query:
        await ctx.send("Usage: `!place <name>` — e.g. `!place Bethel`, `!place Sea of Galilee`, `!place Rome` — "
                       "or a book or passage for a map of every place it names: `!place Acts`, `!place 1 Maccabees 4:36-61`.")
        return
    slugs = find("places", query, prefix=False)
    if not slugs:
        book = book_query(query)
        if book:
            await send_book_map(ctx, *book)
            return
        slugs = find("places", query)
    if not slugs:
        await ctx.send(f"I don't know a place in the Bible called **{query}**. "
                       f"Try `!dictionary {query}` or check the spelling.")
        return
    if not want_all and _clear_winner("places", slugs):
        note = _others_note("places", slugs, "place")
        spelled = spelled_as(slugs[0], query) if _norm(query) not in _index("places") else []
        if spelled:
            name = re.sub(r"\s*\(.*\)$", "", data()["places"][slugs[0]]["name"])
            note = (f"**{query.strip()}** is how {_and(spelled)} spell{'s' if len(spelled) == 1 else ''} "
                    f"**{name}**." + (f"\n{note}" if note else ""))
        if note:
            await ctx.send(note)
        await send_place(ctx, slugs[0])
        return
    lines = [f"• **{label('places', s)}** — named in {weight('places', s)} verse(s)" for s in slugs[:25]]
    embed = discord.Embed(title=f"📍 {len(slugs)} places called {query.title()}",
                          description="\n".join(lines), color=PLACE_COLOR)
    embed.set_footer(text="Pick one below")
    await ctx.send(embed=embed, view=Picker("places", slugs))


@bot.command(name="who", aliases=["person", "whois"])
async def cmd_who(ctx, *, name: str = ""):
    """Who someone in the Bible was: family, tribe, and every verse naming them.
    Usage: !who Ruth
           !who Mary            — pick from the Marys
           !who John all        — list every John"""
    await lookup_person(ctx, name)


@bot.command(name="place", aliases=["where", "map"])
async def cmd_place(ctx, *, name: str = ""):
    """A place in the Bible on a map, with what it was, its name in each Bible and every verse naming it.
    Usage: !place Bethel
           !place Galaad          (any Bible's spelling: Vulgate, Septuagint, Hebrew, Douay-Rheims)
           !place Acts            (every place a book names, on one map)
           !place Genesis 12      (a chapter's places; or a passage: !place 1 Maccabees 4:36-61)"""
    async with ctx.typing():
        await lookup_place(ctx, name)


@bot.command(name="tree", aliases=["familytree", "lineage", "genealogy"])
async def cmd_tree(ctx, *, query: str = ""):
    """A family tree picture, or a line of descent from one person to another.
    Usage: !tree David            — David among his family
           !tree Abraham to David — every generation between them"""
    async with ctx.typing():
        await send_tree(ctx, query)


def _autocomplete(kind: str):
    async def complete(interaction: discord.Interaction, current: str) -> list:
        q = _norm(current)
        if not q:
            return []
        slugs = sorted({s for n, ss in _index(kind).items() if n.startswith(q) for s in ss},
                       key=lambda s: -weight(kind, s))[:25]
        return [app_commands.Choice(name=label(kind, s)[:100], value=s) for s in slugs]
    return complete


@bot.tree.command(name="who", description="Who someone in the Bible was: family, tribe, and the verses naming them")
@app_commands.describe(name="e.g. Ruth, Mary Magdalene, Nebuchadnezzar")
@app_commands.autocomplete(name=_autocomplete("people"))
async def who_slash(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await lookup_person(ctx, name)


@bot.tree.command(name="tree", description="A family tree, or the line of descent from one person to another")
@app_commands.describe(person="Whose family, e.g. David, Ruth, Moses",
                       down_to="Optional: a descendant, to show every generation between them")
@app_commands.autocomplete(person=_autocomplete("people"), down_to=_autocomplete("people"))
async def tree_slash(interaction: discord.Interaction, person: str, down_to: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_tree(ctx, f"{person} to {down_to}" if down_to else person)


@bot.tree.command(name="place", description="A place in the Bible on a map, with the verses naming it")
@app_commands.describe(name="e.g. Bethel, Galaad, Sea of Galilee, or a book for its places: Acts")
@app_commands.autocomplete(name=_autocomplete("places"))
async def place_slash(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await lookup_place(ctx, name)
