"""
!kings: the kings of Israel and Judah, from Saul to Zedekiah -- how long each
reigned and what the Book of Kings says of him -- as a chart, or one king at
a time.
  !kings              the chart (united kingdom, then Israel and Judah side by side)
  !kings Hezekiah     one king: his reign, the verdict on it, the verses

Every reign length and verdict is quoted from the KJV, with its verse, and
tests/test_kings.py checks each quotation against the local text (as the
curated tables in reference.py are). Lengths are the text's own; reigns
overlapped (co-regencies), so the chart stacks them in order -- it is not a
timeline.
"""
import asyncio
import io
import re

import discord
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

from core import bot, log, lookup

COLOR = discord.Color.from_rgb(150, 110, 40)

# (name, other names, kingdom, years, (length verse, its words), [(verdict verse, its words)], verdict, note)
#   verdict: "right" (did that which was right), "evil", "mixed" (both said), None (the text gives none)
KINGS = [
    ("Saul", [], "united", 40, ("Acts 13:21", "Saul the son of Cis, a man of the tribe of Benjamin, by the space of forty years"),
     [("1 Samuel 15:23", "he hath also rejected thee from being king")], "evil",
     "The Hebrew of 1 Samuel 13:1 is damaged (the KJV reads \u201cSaul reigned one year\u201d); Acts gives forty years."),
    ("David", [], "united", 40, ("1 Kings 2:11", "the days that David reigned over Israel were forty years"),
     [("1 Kings 15:5", "David did that which was right in the eyes of the Lord")], "right",
     "Seven years in Hebron, thirty-three in Jerusalem."),
    ("Solomon", [], "united", 40, ("1 Kings 11:42", "the time that Solomon reigned in Jerusalem over all Israel was forty years"),
     [("1 Kings 3:3", "Solomon loved the Lord"), ("1 Kings 11:6", "Solomon did evil in the sight of the Lord")], "mixed",
     "When he was old, \u201chis wives turned away his heart after other gods\u201d (1 Kings 11:4)."),

    # ── Israel, the northern kingdom ──
    ("Jeroboam", ["Jeroboam I"], "israel", 22, ("1 Kings 14:20", "the days which Jeroboam reigned were two and twenty years"),
     [("1 Kings 14:16", "Jeroboam, who did sin, and who made Israel to sin")], "evil",
     "He set up golden calves at Bethel and Dan."),
    ("Nadab", [], "israel", 2, ("1 Kings 15:25", "reigned over Israel two years"),
     [("1 Kings 15:26", "he did evil in the sight of the Lord")], "evil", ""),
    ("Baasha", [], "israel", 24, ("1 Kings 15:33", "twenty and four years"),
     [("1 Kings 15:34", "he did evil in the sight of the Lord")], "evil", ""),
    ("Elah", [], "israel", 2, ("1 Kings 16:8", "began Elah the son of Baasha to reign over Israel in Tirzah, two years"),
     [("1 Kings 16:13", "the sins of Elah his son")], "evil", ""),
    ("Zimri", [], "israel", 7 / 365, ("1 Kings 16:15", "did Zimri reign seven days in Tirzah"),
     [("1 Kings 16:19", "doing evil in the sight of the Lord")], "evil", "Seven days."),
    ("Omri", [], "israel", 12, ("1 Kings 16:23", "began Omri to reign over Israel, twelve years"),
     [("1 Kings 16:25", "Omri wrought evil in the eyes of the Lord")], "evil", "He built Samaria."),
    ("Ahab", [], "israel", 22, ("1 Kings 16:29", "reigned over Israel in Samaria twenty and two years"),
     [("1 Kings 16:30", "did evil in the sight of the Lord above all that were before him")], "evil",
     "Husband of Jezebel, in the days of Elijah."),
    ("Ahaziah of Israel", ["Ahaziah"], "israel", 2, ("1 Kings 22:51", "reigned two years over Israel"),
     [("1 Kings 22:52", "he did evil in the sight of the Lord")], "evil", ""),
    ("Jehoram of Israel", ["Joram", "Jehoram"], "israel", 12, ("2 Kings 3:1", "reigned twelve years"),
     [("2 Kings 3:2", "he wrought evil in the sight of the Lord; but not like his father")], "evil", ""),
    ("Jehu", [], "israel", 28, ("2 Kings 10:36", "the time that Jehu reigned over Israel in Samaria was twenty and eight years"),
     [("2 Kings 10:30", "thou hast done well in executing that which is right in mine eyes"),
      ("2 Kings 10:31", "he departed not from the sins of Jeroboam")], "mixed", "He wiped out the house of Ahab."),
    ("Jehoahaz of Israel", ["Jehoahaz"], "israel", 17, ("2 Kings 13:1", "reigned seventeen years"),
     [("2 Kings 13:2", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Jehoash of Israel", ["Joash", "Jehoash"], "israel", 16, ("2 Kings 13:10", "reigned sixteen years"),
     [("2 Kings 13:11", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Jeroboam II", [], "israel", 41, ("2 Kings 14:23", "reigned forty and one years"),
     [("2 Kings 14:24", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Zachariah", [], "israel", 0.5, ("2 Kings 15:8", "reign over Israel in Samaria six months"),
     [("2 Kings 15:9", "he did that which was evil in the sight of the Lord")], "evil", "Six months."),
    ("Shallum", [], "israel", 1 / 12, ("2 Kings 15:13", "he reigned a full month in Samaria"), [], None, "One month."),
    ("Menahem", [], "israel", 10, ("2 Kings 15:17", "reigned ten years in Samaria"),
     [("2 Kings 15:18", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Pekahiah", [], "israel", 2, ("2 Kings 15:23", "reigned two years"),
     [("2 Kings 15:24", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Pekah", [], "israel", 20, ("2 Kings 15:27", "reigned twenty years"),
     [("2 Kings 15:28", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Hoshea", [], "israel", 9, ("2 Kings 17:1", "to reign in Samaria over Israel nine years"),
     [("2 Kings 17:2", "he did that which was evil in the sight of the Lord, but not as the kings of Israel that were before him")],
     "evil", "The last king of Israel: Samaria fell to Assyria (2 Kings 17:6)."),

    # ── Judah, the southern kingdom ──
    ("Rehoboam", [], "judah", 17, ("1 Kings 14:21", "he reigned seventeen years in Jerusalem"),
     [("2 Chronicles 12:14", "he did evil, because he prepared not his heart to seek the Lord")], "evil",
     "Son of Solomon: the kingdom split under him."),
    ("Abijam", ["Abijah"], "judah", 3, ("1 Kings 15:2", "Three years reigned he in Jerusalem"),
     [("1 Kings 15:3", "he walked in all the sins of his father")], "evil", ""),
    ("Asa", [], "judah", 41, ("1 Kings 15:10", "forty and one years reigned he in Jerusalem"),
     [("1 Kings 15:11", "Asa did that which was right in the eyes of the Lord")], "right", ""),
    ("Jehoshaphat", [], "judah", 25, ("1 Kings 22:42", "he reigned twenty and five years in Jerusalem"),
     [("1 Kings 22:43", "doing that which was right in the eyes of the Lord")], "right", ""),
    ("Jehoram of Judah", [], "judah", 8, ("2 Kings 8:17", "he reigned eight years in Jerusalem"),
     [("2 Kings 8:18", "he did evil in the sight of the Lord")], "evil", "He married Ahab's daughter."),
    ("Ahaziah of Judah", [], "judah", 1, ("2 Kings 8:26", "he reigned one year in Jerusalem"),
     [("2 Kings 8:27", "did evil in the sight of the Lord")], "evil", ""),
    ("Athaliah", [], "judah", 6, ("2 Kings 11:3", "six years. And Athaliah did reign over the land"), [], None,
     "Queen, not king: Ahab's daughter, who seized the throne."),
    ("Jehoash of Judah", ["Joash of Judah"], "judah", 40, ("2 Kings 12:1", "forty years reigned he in Jerusalem"),
     [("2 Kings 12:2", "Jehoash did that which was right in the sight of the Lord all his days wherein Jehoiada the priest instructed him")],
     "right", "Crowned at seven."),
    ("Amaziah", [], "judah", 29, ("2 Kings 14:2", "reigned twenty and nine years in Jerusalem"),
     [("2 Kings 14:3", "he did that which was right in the sight of the Lord, yet not like David his father")], "right", ""),
    ("Azariah", ["Uzziah"], "judah", 52, ("2 Kings 15:2", "he reigned two and fifty years in Jerusalem"),
     [("2 Kings 15:3", "he did that which was right in the sight of the Lord")], "right",
     "Also called Uzziah; struck with leprosy (2 Kings 15:5)."),
    ("Jotham", [], "judah", 16, ("2 Kings 15:33", "he reigned sixteen years in Jerusalem"),
     [("2 Kings 15:34", "he did that which was right in the sight of the Lord")], "right", ""),
    ("Ahaz", [], "judah", 16, ("2 Kings 16:2", "reigned sixteen years in Jerusalem"),
     [("2 Kings 16:2", "did not that which was right in the sight of the Lord his God")], "evil", ""),
    ("Hezekiah", [], "judah", 29, ("2 Kings 18:2", "he reigned twenty and nine years in Jerusalem"),
     [("2 Kings 18:3", "he did that which was right in the sight of the Lord")], "right",
     "Jerusalem was spared from Sennacherib in his reign."),
    ("Manasseh", [], "judah", 55, ("2 Kings 21:1", "reigned fifty and five years in Jerusalem"),
     [("2 Kings 21:2", "he did that which was evil in the sight of the Lord")], "evil", "The longest reign."),
    ("Amon", [], "judah", 2, ("2 Kings 21:19", "he reigned two years in Jerusalem"),
     [("2 Kings 21:20", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Josiah", [], "judah", 31, ("2 Kings 22:1", "he reigned thirty and one years in Jerusalem"),
     [("2 Kings 22:2", "he did that which was right in the sight of the Lord")], "right",
     "Crowned at eight; the book of the law was found in his reign."),
    ("Jehoahaz of Judah", [], "judah", 0.25, ("2 Kings 23:31", "he reigned three months in Jerusalem"),
     [("2 Kings 23:32", "he did that which was evil in the sight of the Lord")], "evil", "Three months."),
    ("Jehoiakim", [], "judah", 11, ("2 Kings 23:36", "he reigned eleven years in Jerusalem"),
     [("2 Kings 23:37", "he did that which was evil in the sight of the Lord")], "evil", ""),
    ("Jehoiachin", ["Jeconiah", "Coniah"], "judah", 0.25, ("2 Kings 24:8", "he reigned in Jerusalem three months"),
     [("2 Kings 24:9", "he did that which was evil in the sight of the Lord")], "evil", "Three months; taken to Babylon."),
    ("Zedekiah", [], "judah", 11, ("2 Kings 24:18", "he reigned eleven years in Jerusalem"),
     [("2 Kings 24:19", "he did that which was evil in the sight of the Lord")], "evil",
     "The last king of Judah: Jerusalem fell to Babylon (2 Kings 25)."),
]

KINGDOMS = {"united": "The united kingdom", "israel": "Israel (the north)", "judah": "Judah (the south)"}
MARK = {"right": "✅", "evil": "❌", "mixed": "⚖️", None: "▫️"}
VERDICT_WORDS = {"right": "did that which was right", "evil": "did evil", "mixed": "both", None: "no verdict given"}


def length_text(years: float) -> str:
    if years >= 1:
        n = round(years)
        return f"{n} year{'s' if n != 1 else ''}"
    days = round(years * 365)
    if days < 28:
        return f"{days} days"
    months = round(years * 12)
    return f"{months} month{'s' if months != 1 else ''}"


def find_king(query: str) -> "list[tuple]":
    """Kings by name or other name; 'Jehoram' is two kings."""
    q = re.sub(r"\s+", " ", query.strip().lower()).removeprefix("king ")
    exact = [k for k in KINGS if q == k[0].lower()]
    if exact:
        return exact
    return [k for k in KINGS if q in [a.lower() for a in k[1]] or k[0].lower().split(" of ")[0] == q]


def king_embed(king: tuple) -> discord.Embed:
    name, also, kingdom, years, (len_ref, len_words), verdicts, verdict, note = king
    also = [a for a in also if a != name.split(" of ")[0]]
    embed = discord.Embed(title=f"👑 {name}", color=COLOR,
                          description=f"**{KINGDOMS[kingdom]}** · reigned **{length_text(years)}**"
                                      + (f"\n*Also called {', '.join(also)}*" if also else ""))
    embed.add_field(name="Reign", value=f"\u201c…{len_words}…\u201d ({len_ref})", inline=False)
    if verdicts:
        embed.add_field(name=f"{MARK[verdict]} The verdict",
                        value="\n".join(f"\u201c…{w}…\u201d ({r})" for r, w in verdicts), inline=False)
    else:
        embed.add_field(name=f"{MARK[None]} The verdict", value="The text gives no verdict on this reign.", inline=False)
    if note:
        embed.add_field(name="Note", value=note, inline=False)
    embed.set_footer(text="!kings for all of them · read on with !verse " + len_ref)
    return embed


def list_embed() -> discord.Embed:
    embed = discord.Embed(title="👑 The Kings of Israel and Judah", color=COLOR,
                          description="How long each reigned, and what the Book of Kings says of him: "
                                      "✅ did that which was right · ❌ did evil · ⚖️ both · ▫️ no verdict. "
                                      "`!kings Hezekiah` for one king and the verses.")
    for kingdom, label in KINGDOMS.items():
        rows = [f"{MARK[k[6]]} {k[0]} · {length_text(k[3])}" for k in KINGS if k[2] == kingdom]
        embed.add_field(name=label, value="\n".join(rows), inline=kingdom != "united")
    embed.set_image(url="attachment://kings.png")
    embed.set_footer(text="Reign lengths as the text gives them, in order — reigns overlapped, so this is not a timeline")
    return embed


# ── the chart ───────────────────────────────────────────────────────────────

S = 2
FONTS = "C:/Windows/Fonts/"
PAPER, INK, MUTED = (246, 240, 226), (60, 50, 40), (125, 112, 95)
FILL = {"right": (196, 222, 186), "evil": (236, 196, 186), "mixed": (240, 222, 168), None: (222, 218, 210)}
EDGE = {"right": (90, 140, 80), "evil": (170, 80, 60), "mixed": (180, 140, 50), None: (150, 145, 135)}
PX_PER_YEAR, MIN_H, COL_W, GAP, MARGIN = 3.2, 26, 300, 60, 36


def _font(name: str, size: int):
    try:
        return ImageFont.truetype(FONTS + name, size * S)
    except OSError:
        return ImageFont.load_default()


def _block(d, x, y, w, h, king):
    d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=5 * S,
                        fill=FILL[king[6]], outline=EDGE[king[6]], width=S)
    label = f"{king[0]} · {length_text(king[3])}"
    d.text(((x + 10) * S, (y + min(h, 40) / 2) * S), label, font=_font("georgia.ttf", 13), fill=INK, anchor="lm")


def chart() -> io.BytesIO:
    """The united kingdom across the top, then Israel and Judah side by side,
    each reign a block as tall as it was long (with a least height to read)."""
    def h(k):
        return max(MIN_H, k[3] * PX_PER_YEAR)
    united = [k for k in KINGS if k[2] == "united"]
    north = [k for k in KINGS if k[2] == "israel"]
    south = [k for k in KINGS if k[2] == "judah"]
    width = 2 * COL_W + GAP + 2 * MARGIN
    top = 92
    united_h = max(h(k) for k in united)
    cols_top = top + united_h + 70
    height = int(cols_top + max(sum(h(k) + 4 for k in north), sum(h(k) + 4 for k in south)) + 80)
    img = Image.new("RGB", (width * S, height * S), PAPER)
    d = ImageDraw.Draw(img)
    d.text((width / 2 * S, 30 * S), "The Kings of Israel and Judah", font=_font("georgiab.ttf", 24), fill=INK, anchor="mm")
    d.text((width / 2 * S, 58 * S), "each block as long as the reign the Bible gives it", font=_font("georgiai.ttf", 14),
           fill=MUTED, anchor="mm")
    # united kingdom: three blocks side by side
    uw = (width - 2 * MARGIN - 2 * 12) / 3
    for i, k in enumerate(united):
        _block(d, MARGIN + i * (uw + 12), top, uw, h(k), k)
    d.text((width / 2 * S, (top + united_h + 30) * S), "the kingdom divides under Rehoboam (1 Kings 12)",
           font=_font("georgiai.ttf", 13), fill=MUTED, anchor="mm")
    for col, (label, kings) in enumerate((("Israel (the north)", north), ("Judah (the south)", south))):
        x = MARGIN + col * (COL_W + GAP)
        d.text(((x + COL_W / 2) * S, (cols_top - 16) * S), label, font=_font("georgiab.ttf", 16), fill=INK, anchor="mm")
        y = cols_top
        for k in kings:
            _block(d, x, y, COL_W, h(k), k)
            y += h(k) + 4
        end = "Samaria falls to Assyria" if col == 0 else "Jerusalem falls to Babylon"
        d.text(((x + COL_W / 2) * S, (y + 18) * S), end, font=_font("georgiai.ttf", 13), fill=MUTED, anchor="mm")
    legend = "green: did that which was right · red: did evil · gold: both · grey: no verdict"
    d.text((width / 2 * S, (height - 22) * S), legend, font=_font("georgiai.ttf", 12), fill=MUTED, anchor="mm")
    img = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf


async def send_kings(ctx, query: str = "") -> None:
    query = query.strip()
    if query:
        found = find_king(query)
        if not found:
            await ctx.send(f"I don't know a king called **{query}** — `!kings` lists them all.")
            return
        for king in found[:3]:                    # "Jehoram" is a king of Israel and one of Judah
            await ctx.send(embed=king_embed(king))
        return
    try:
        buf = await asyncio.to_thread(chart)
    except Exception:
        log.exception("Couldn't draw the kings chart")
        embed = list_embed()
        embed.set_image(url=None)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=list_embed(), file=discord.File(buf, filename="kings.png"))


@bot.command(name="kings", aliases=["king", "monarchs"])
async def cmd_kings(ctx, *, query: str = ""):
    """The kings of Israel and Judah: reigns and the Bible's verdict on each.
    Usage: !kings            — the chart
           !kings Hezekiah   — one king"""
    async with ctx.typing():
        await send_kings(ctx, query)


@bot.tree.command(name="kings", description="The kings of Israel and Judah: how long each reigned, and the Bible's verdict")
@app_commands.describe(king="One king (e.g. Hezekiah); empty for the chart of them all")
async def kings_slash(interaction: discord.Interaction, king: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_kings(ctx, king)
