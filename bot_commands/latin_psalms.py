"""
!psalm 110 chant -- a psalm chanted in Latin to a Gregorian psalm tone: sung by the
synthesised schola (or played on the organ, by its button), with the Latin as the
Breviary prints it and the Douay-Rheims English. Built by scripts/build_psalm_chant.py.

The Latin psalter numbers the psalms as the Greek and Latin Bibles do (Vulgate), mostly
one lower than the usual (Hebrew) numbers; people ask by the usual number, and the post
says both. Psalm 119 (Vulgate 118) is sung in its 22 sections, as the Breviary does.
"""
import functools
import json
import re

import discord

from core import ROOT, bot

DATA_PATH = ROOT / "data" / "psalter" / "latin_psalms.json"
AUDIO_DIR = ROOT / "data" / "psalter" / "chant"
COLOR = discord.Color.from_rgb(140, 40, 40)
ENDINGS = {"8G": "8th tone, ending G", "1D": "1st tone, ending D", "2D": "2nd tone", "3a": "3rd tone, ending a",
           "4E": "4th tone, ending E", "5a": "5th tone", "6F": "6th tone", "7c": "7th tone, ending c"}


@functools.lru_cache(maxsize=1)
def psalms() -> dict:
    if not DATA_PATH.exists():
        return {}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))["psalms"]


def vulgate(hebrew: int) -> list:
    """The Vulgate psalm(s) for a psalm by its usual (Hebrew) number."""
    if hebrew <= 8 or hebrew >= 148:
        return [hebrew]
    if hebrew in (9, 10):
        return [9]                                     # one psalm in the Vulgate
    if hebrew in (114, 115):
        return [113]
    if hebrew == 116:
        return [114, 115]                              # two in the Vulgate
    if hebrew == 147:
        return [146, 147]
    return [hebrew - 1]


def incipit(v: int) -> str:
    first = psalms()[str(v)]["latin"][0]
    return re.split(r"[,:;.*†]", first)[0].strip()


def audio_path(v: int, part: int, organ: bool):
    stem = psalms()[str(v)]["parts"][part]["file"]
    path = AUDIO_DIR / ("organ" if organ else "sung") / f"{stem}.ogg"
    return path if path.exists() else None


def _trim(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0] + "\n…"


def heading(hebrew: int, v: int, part: int) -> str:
    p = psalms()[str(v)]
    name = p["parts"][part]["name"]
    number = f"Psalm {hebrew}" + (f" ({name})" if name else "")
    vul = f"Vulgate {v}" if v != hebrew else ""
    return f"{number}" + (f" · {vul}" if vul else "") + f" · *{incipit(v)}*"


def chant_message(hebrew: int, v: int, part: int = 0, organ: bool = False) -> dict:
    """send() kwargs: the audio, the Latin and the English, and the other recording's button."""
    p = psalms()[str(v)]
    pieces = p["parts"]
    lines = p["latin"][part * 8:(part + 1) * 8] if len(pieces) > 1 else p["latin"]
    english = [t for n, t in p["english"] if len(pieces) == 1 or part * 8 < n <= (part + 1) * 8]
    how = "played on the organ" if organ else "chanted in Latin by the schola"
    content = f"{'▶️' if organ else '🎤'} **{heading(hebrew, v, part)}**, {how}, in the {ENDINGS[p['tone']]}, " \
              f"with the Gloria Patri."
    if len(pieces) > 1:
        content += f"\nPsalm 119 is sung in its 22 sections; this is {part + 1} of 22. " \
                   f"Another: `!psalm 119 chant {pieces[(part + 1) % 22]['name'].lower()}`."
    latin = discord.Embed(title=f"{heading(hebrew, v, part)}", color=COLOR,
                          description=_trim("\n".join(l.replace(" * ", " ✱ ") for l in lines)))
    latin.set_footer(text="Latin: the Breviary's psalter, with the stresses the chant follows · ✱ the mid-verse pause")
    eng = discord.Embed(title="In English (Douay-Rheims)", color=COLOR, description=_trim("\n".join(english)))
    message = {"content": content, "embeds": [latin, eng]}
    path = audio_path(v, part, organ)
    if path is None:
        message["content"] += "\n⚠️ The recording isn't available right now."
    else:
        message["file"] = discord.File(path, filename=f"Psalm_{hebrew}{'_' + pieces[part]['name'] if pieces[part]['name'] else ''}"
                                                      f"_{'organ' if organ else 'sung'}.ogg")
        other = audio_path(v, part, not organ)
        if other:
            view = discord.ui.View(timeout=None)
            view.add_item(PsalmChantButton(not organ, hebrew, v, part))
            message["view"] = view
    return message


class PsalmChantButton(discord.ui.DynamicItem[discord.ui.Button],
                       template=r"lps:(?P<kind>sung|organ):(?P<h>\d+):(?P<v>\d+):(?P<p>\d+)"):
    """The other recording (organ under the sung one, and back), posted as its own message.
    Persistent, so it works after a restart."""

    def __init__(self, organ: bool, hebrew: int, v: int, part: int):
        label, emoji = ("Organ", "▶️") if organ else ("Sung", "🎤")
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary,
                                           custom_id=f"lps:{'organ' if organ else 'sung'}:{hebrew}:{v}:{part}"))
        self.organ, self.hebrew, self.v, self.part = organ, hebrew, v, part

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["kind"] == "organ", int(match["h"]), int(match["v"]), int(match["p"]))

    async def callback(self, interaction: discord.Interaction):
        path = audio_path(self.v, self.part, self.organ) if str(self.v) in psalms() else None
        if path is None:
            await interaction.response.send_message("⚠️ I don't have that recording right now.", ephemeral=True)
            return
        how = "played on the organ" if self.organ else "chanted in Latin by the schola"
        await interaction.response.send_message(
            f"{'▶️' if self.organ else '🎤'} **{heading(self.hebrew, self.v, self.part)}**, {how}.",
            file=discord.File(path, filename=f"Psalm_{self.hebrew}_{'organ' if self.organ else 'sung'}.ogg"))


bot.add_dynamic_items(PsalmChantButton)


def parse(query: str) -> "tuple | None":
    """'110' / '119 beth' / '119 2' / '110 organ' -> (hebrew, [(vulgate, part)], organ); None if no psalm."""
    q = query.lower()
    organ = bool(re.search(r"\b(organ|tune|midi)\b", q))
    m = re.search(r"\b(\d{1,3})\b", q)
    if not m or not 1 <= int(m.group(1)) <= 150:
        return None
    hebrew = int(m.group(1))
    targets = [(v, 0) for v in vulgate(hebrew)]
    if hebrew == 119:
        names = [p["name"].lower() for p in psalms()["118"]["parts"]]
        rest = q[m.end():]
        word = next((w for w in re.findall(r"[a-z]+", rest) if w in names), None)
        num = re.search(r"\b(\d{1,2})\b", rest)
        part = names.index(word) if word else (int(num.group(1)) - 1 if num and 1 <= int(num.group(1)) <= 22 else 0)
        targets = [(118, part)]
    return hebrew, targets, organ


async def send_psalm_chant(ctx, query: str) -> None:
    if not psalms():
        await ctx.send("⚠️ The chanted psalms aren't available right now.")
        return
    parsed = parse(query)
    if parsed is None:
        await ctx.send("Which psalm? `!psalm 110 chant` sings Psalm 110 in Latin; add `organ` for the organ "
                       "(`!psalm 23 chant organ`), and for Psalm 119 a section (`!psalm 119 chant beth`).")
        return
    hebrew, targets, organ = parsed
    for v, part in targets:
        await ctx.send(**chant_message(hebrew, v, part, organ))
