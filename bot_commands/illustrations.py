"""
The old illustrated editions' pictures, each tied to the passage it illustrates: Doré's La Fontaine, Rackham's,
Crane's and Milo Winter's Aesop, Crane's and Rackham's Grimm, Beardsley's Malory, Crane's Faerie Queene, the
Boydell Shakespeare (data/illustrations/<set>.json, built by scripts/build_illustrations.py; the pictures in
data/illustrations/<set>/, not in git).

There's no command for them: a 🖌️ button appears under !verse, !fable, !tale and !shakespeare wherever the
passage has a picture, named for the artist (or "Pictures" when there are several artists' to see).
"""
import functools
import hashlib
import json
import re

import discord

from core import ROOT, bot, lookup

DIR = ROOT / "data" / "illustrations"
COLOR = discord.Color.from_rgb(120, 90, 60)
MAX_SHOWN = 4                                           # (pictures to a message; more come in more messages)
REF = re.compile(r"^(?P<book>.+?) (?P<ch>\d+(?:\.\d+)*)(?::(?P<v1>\d+)(?:\s*[–-]\s*(?P<v2>\d+))?)?(?: \([^)]*\))?$")


@functools.lru_cache(maxsize=1)
def sets() -> dict:
    """{set name: its file's header (artist, work, credit)}."""
    out = {}
    for path in sorted(DIR.glob("*.json")) if DIR.exists() else []:
        d = json.loads(path.read_text(encoding="utf-8"))
        out[path.stem] = {k: v for k, v in d.items() if k != "pictures"} | {"pictures": d["pictures"]}
    return out


@functools.lru_cache(maxsize=1)
def pictures() -> list:
    """Every picture, with its set's artist and work, and a short key for the button ids: the set's two letters
    and five of the picture's own ("lf3a9c0"), which stay the same when a set is rebuilt, so old buttons still
    show the picture they showed."""
    out, keys = [], set()
    for name, s in sets().items():
        for p in s["pictures"]:
            key = s["code"] + hashlib.sha1((p.get("file") or p["image"]).encode()).hexdigest()[:5]
            if key in keys:
                raise ValueError(f"two pictures with the key {key!r}")
            keys.add(key)
            out.append({**p, "key": key, "set": name, "artist": s["artist"], "work": s["work"],
                        "credit": s.get("credit", ""), "label": s.get("label") or s["artist"].split()[-1]})
    return out


@functools.lru_cache(maxsize=1)
def by_key() -> dict:
    return {p["key"]: p for p in pictures()}


@functools.lru_cache(maxsize=1)
def by_book() -> dict:
    out = {}
    for p in pictures():
        out.setdefault(p["book"], []).append(p)
    return out


def for_passage(book: str, chapter: str, start: "int | None" = None, end: "int | None" = None) -> list:
    """The pictures of a passage (a whole chapter if no verses are given). A picture of a whole chapter (a
    fable, a tale) goes with every passage of it; one of some lines, only with the passages holding them."""
    hits = []
    for p in by_book().get(book, []):
        if str(p["chapter"]) != str(chapter):
            continue
        if start is None or p.get("start") is None or (p["start"] <= (end or start) and start <= (p.get("end") or p["start"])):
            hits.append(p)
    return hits


def for_result(result: dict) -> list:
    """The pictures for a !verse result ("Le Morte d'Arthur 1.1:2", "Hamlet 3.1:64–98", "Aesop's Fables 12")."""
    if not result.get("found") or not pictures():
        return []
    m = REF.match(result.get("reference", ""))
    if not m:
        return []
    book = lookup._resolve_book(m["book"])[1] or m["book"]
    start = int(m["v1"]) if m["v1"] else None
    return for_passage(book, m["ch"], start, int(m["v2"]) if m["v2"] else start)


class PictureButton(discord.ui.DynamicItem[discord.ui.Button], template=r"pics:(?P<keys>[a-z0-9,]+)"):
    """🖌️ under a passage: its pictures. The keys are in the custom_id, so it keeps working after a restart."""

    def __init__(self, keys: list, row: "int | None" = None):
        found = [by_key()[k] for k in keys if k in by_key()]
        labels = {p["label"] for p in found}
        label = labels.pop() if len(labels) == 1 else "Pictures"
        ids = ""
        for k in keys:                                  # (as many as fit in Discord's 100 characters)
            if len("pics:" + ids + "," + k) > 100:
                break
            ids = f"{ids},{k}" if ids else k
        super().__init__(discord.ui.Button(label=label, emoji="🖌️", style=discord.ButtonStyle.secondary, row=row,
                                           custom_id=f"pics:{ids}"))
        self.keys = ids.split(",")

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["keys"].split(","), row=item.row)

    async def callback(self, interaction: discord.Interaction):
        found = [by_key()[k] for k in self.keys if k in by_key()]
        found = [p for p in found if _local_file(p) or p.get("image")]
        if not found:
            await interaction.response.send_message("⚠️ I can't find that picture any more.", ephemeral=True)
            return
        await interaction.response.send_message(**picture_message(found[:MAX_SHOWN]))
        for i in range(MAX_SHOWN, len(found), MAX_SHOWN):           # (more than one message holds: the rest)
            await interaction.followup.send(**picture_message(found[i:i + MAX_SHOWN]))


bot.add_dynamic_items(PictureButton)


def buttons(found: list, row: "int | None" = None) -> list:
    """[the 🖌️ button] for some pictures, or [] for none."""
    found = [p for p in found if _local_file(p) or p.get("image")]
    return [PictureButton([p["key"] for p in found], row=row)] if found else []


def picture_buttons(result: dict, row: "int | None" = 2) -> list:
    """The 🖌️ button for a !verse result that has pictures (on the row with !verse's other passage buttons)."""
    return buttons(for_result(result), row=row)


def reference(p: dict) -> str:
    ref = f"{p['book']} {p['chapter']}"
    if p.get("start") is not None:
        ref += f":{p['start']}" + (f"-{p['end']}" if p.get("end") not in (None, p["start"]) else "")
    return ref


def _local_file(p: dict):
    path = ROOT / p["file"] if p.get("file") else None
    return path if path and path.exists() else None


def _attachment_name(p: dict) -> str:
    return f"{p['key']}{_local_file(p).suffix}"


def picture_embed(p: dict) -> discord.Embed:
    lines = [f"*{p['caption']}*"] if p.get("caption") else []
    if p.get("quote"):
        lines.append("\n".join(f"*{line}*" for line in p["quote"].splitlines()))
    embed = discord.Embed(title=f"🖌️ {p['title']}"[:256], url=p.get("page") or None,
                          description="\n".join(lines)[:1500] or None, color=COLOR)
    embed.add_field(name="Read it", value=f"`!verse {reference(p)}`", inline=False)
    local = _local_file(p)
    embed.set_image(url=f"attachment://{_attachment_name(p)}" if local else p["image"])
    embed.set_footer(text=f"{p['artist']}, {p['work']}" + (f" · image: {p['credit']}" if p.get("credit") else ""))
    return embed


def picture_message(shown: list) -> dict:
    """send() arguments for some pictures: their embeds, with the pictures kept here attached."""
    files = [discord.File(_local_file(p), filename=_attachment_name(p)) for p in shown if _local_file(p)]
    return {"embeds": [picture_embed(p) for p in shown], **({"files": files} if files else {})}
