"""
!rosary -- the Rosary, a page at a time: the opening prayers, the five decades of the
day's mysteries (each with its Bible passage), and the closing prayers, with ◀ ▶ to move
through them and the Ave Maria sung. The mysteries and the days they're prayed follow
Wikipedia's "Rosary" article (with the Luminous Mysteries on Thursdays, as most pray it
now); any set can be asked for by name.
"""
import datetime
import re

import discord

from core import bot, lookup
from bot_commands.angelus import HAIL_MARY
from bot_commands.hymns import hymns, sung_path

COLOR = discord.Color.from_rgb(60, 90, 160)

SIGN = "In the name of the Father, and of the Son, and of the Holy Ghost. Amen."
CREED = ("I believe in God, the Father Almighty, Creator of heaven and earth; and in Jesus Christ, His only Son, "
         "our Lord; who was conceived by the Holy Ghost, born of the Virgin Mary, suffered under Pontius Pilate, "
         "was crucified, died, and was buried. He descended into hell; the third day He arose again from the dead; "
         "He ascended into heaven, sitteth at the right hand of God the Father Almighty; from thence He shall come "
         "to judge the living and the dead. I believe in the Holy Ghost, the holy Catholic Church, the communion "
         "of Saints, the forgiveness of sins, the resurrection of the body, and life everlasting. Amen.")
OUR_FATHER = ("Our Father, who art in heaven, hallowed be Thy name; Thy kingdom come; Thy will be done on earth as it "
              "is in heaven. Give us this day our daily bread; and forgive us our trespasses as we forgive those who "
              "trespass against us; and lead us not into temptation, but deliver us from evil. Amen.")
GLORY_BE = ("Glory be to the Father, and to the Son, and to the Holy Ghost. As it was in the beginning, is now, and "
            "ever shall be, world without end. Amen.")
FATIMA = ("O my Jesus, forgive us our sins, save us from the fires of hell; lead all souls to heaven, especially "
          "those in most need of Thy mercy.")
HAIL_HOLY_QUEEN = ("Hail, holy Queen, Mother of mercy, our life, our sweetness, and our hope. To thee do we cry, poor "
                   "banished children of Eve; to thee do we send up our sighs, mourning and weeping in this valley of "
                   "tears. Turn, then, most gracious Advocate, thine eyes of mercy toward us; and after this our exile "
                   "show unto us the blessed fruit of thy womb, Jesus. O clement, O loving, O sweet Virgin Mary.\n"
                   "℣. Pray for us, O holy Mother of God.\n℟. That we may be made worthy of the promises of Christ.")
CLOSING = ("*Let us pray.* O God, whose only-begotten Son, by His life, death, and resurrection, has purchased for us "
           "the rewards of eternal life; grant, we beseech Thee, that meditating upon these mysteries of the most holy "
           "Rosary of the Blessed Virgin Mary, we may imitate what they contain and obtain what they promise, through "
           "the same Christ our Lord. Amen.")

# (mystery, its fruit, the Bible passage; None where the Bible doesn't tell it)
MYSTERIES = {
    "joyful": [("The Annunciation", "Humility", "Luke 1:26-38"),
               ("The Visitation", "Love of neighbour", "Luke 1:39-56"),
               ("The Birth of Jesus", "Poverty of spirit", "Luke 2:1-20"),
               ("The Presentation in the Temple", "Obedience", "Luke 2:22-38"),
               ("The Finding of Jesus in the Temple", "Joy in finding Jesus", "Luke 2:41-52")],
    "luminous": [("The Baptism of Jesus in the Jordan", "Openness to the Holy Spirit", "Matthew 3:13-17"),
                 ("The Wedding at Cana", "To Jesus through Mary", "John 2:1-11"),
                 ("The Proclamation of the Kingdom of God", "Trust in God", "Mark 1:14-15"),
                 ("The Transfiguration", "Desire for holiness", "Matthew 17:1-8"),
                 ("The Institution of the Eucharist", "Adoration", "Matthew 26:26-29")],
    "sorrowful": [("The Agony in the Garden", "Sorrow for sin", "Matthew 26:36-46"),
                  ("The Scourging at the Pillar", "Purity", "John 19:1"),
                  ("The Crowning with Thorns", "Moral courage", "Matthew 27:27-31"),
                  ("The Carrying of the Cross", "Patience", "Luke 23:26-32"),
                  ("The Crucifixion and Death of our Lord", "Perseverance", "Luke 23:33-46")],
    "glorious": [("The Resurrection", "Faith", "Matthew 28:1-10"),
                 ("The Ascension", "Hope", "Acts 1:6-11"),
                 ("The Descent of the Holy Spirit", "Love of God", "Acts 2:1-13"),
                 ("The Assumption of Mary", "Devotion to Mary", None),
                 ("The Coronation of Mary", "Trust in Mary's intercession", "Revelation 12:1")],
}
# Wikipedia's schedule, with the Luminous Mysteries (Monday = 0)
BY_WEEKDAY = ["joyful", "sorrowful", "glorious", "luminous", "sorrowful", "joyful", "glorious"]
ORDINAL = ["First", "Second", "Third", "Fourth", "Fifth"]
PAGES = 7                                            # the opening, five decades, the closing


def mysteries_for(day: datetime.date) -> str:
    return BY_WEEKDAY[day.weekday()]


def _passage(ref: str) -> str:
    result = lookup.get_verse(ref)
    if not result.get("found"):
        return ""
    text = re.sub(r"\*\*\[(\d+)\]\*\*", "", result["text"]).strip()
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= 900 else text[:900].rsplit(" ", 1)[0] + "…"


def page_embed(kind: str, page: int) -> discord.Embed:
    name = f"The {kind.capitalize()} Mysteries"
    if page == 0:
        embed = discord.Embed(title=f"📿 The Rosary · {name}", color=COLOR, description=(
            f"*Holding the crucifix:* {SIGN}\n\n**The Apostles' Creed.** {CREED}\n\n"
            f"*On the first large bead:* **Our Father.**\n\n"
            f"*On the three small beads, for faith, hope and charity:* **Hail Mary**, three times.\n> {HAIL_MARY}\n\n"
            f"**Glory Be.** {GLORY_BE}"))
        embed.add_field(name="Today", value="\n".join(f"{i + 1}. {m}" for i, (m, _, _) in
                                                     enumerate(MYSTERIES[kind])), inline=False)
    elif page <= 5:
        title, fruit, ref = MYSTERIES[kind][page - 1]
        embed = discord.Embed(title=f"📿 The {ORDINAL[page - 1]} {kind.capitalize()} Mystery: {title}", color=COLOR)
        if ref:
            embed.add_field(name=f"📖 {ref}", value=_passage(ref) or f"`!verse {ref}`", inline=False)
        else:
            embed.add_field(name="📖 Scripture", value="The Bible doesn't tell this mystery; it comes from the "
                                                       "Church's tradition.", inline=False)
        embed.add_field(name="Pray", value=(f"**Our Father.** {OUR_FATHER}\n\n**Hail Mary**, ten times.\n> {HAIL_MARY}"
                                            f"\n\n**Glory Be.** {GLORY_BE}")[:1024], inline=False)
        embed.add_field(name="Many add the Fátima prayer", value=FATIMA, inline=False)
        embed.set_footer(text=f"Fruit of the mystery: {fruit} · decade {page} of 5")
    else:
        embed = discord.Embed(title="📿 The Rosary · the closing prayers", color=COLOR,
                              description=f"**Hail, Holy Queen.** {HAIL_HOLY_QUEEN}\n\n{CLOSING}\n\n{SIGN}")
    if page != 0 and page <= 5:
        embed.set_author(name=name)
    return embed


class RosaryButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"rosary:(?P<action>back|next):(?P<kind>joyful|luminous|sorrowful|glorious):(?P<page>\d)"):
    """◀ ▶ through the Rosary; persistent, so they keep working after a restart."""

    def __init__(self, action: str, kind: str, page: int):
        super().__init__(discord.ui.Button(emoji="◀" if action == "back" else "▶",
                                           label="Back" if action == "back" else "Next",
                                           style=discord.ButtonStyle.secondary,
                                           custom_id=f"rosary:{action}:{kind}:{page}"))
        self.kind, self.page = kind, page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["kind"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=page_embed(self.kind, self.page),
                                                view=rosary_view(self.kind, self.page))


bot.add_dynamic_items(RosaryButton)


def rosary_view(kind: str, page: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)                 # persistent: must never time out
    if page > 0:
        view.add_item(RosaryButton("back", kind, page - 1))
    if page < PAGES - 1:
        view.add_item(RosaryButton("next", kind, page + 1))
    return view


def rosary_message(kind: str, why: str) -> dict:
    message = {"content": f"📿 **The Rosary** · {why}. ▶ Next to move through the decades.",
               "embed": page_embed(kind, 0), "view": rosary_view(kind, 0)}
    ave = next((h for h in hymns() if h["title"] == "Ave Maria (Antiphona)"), None)
    path = sung_path(ave) if ave else None
    if path:
        message["content"] += "\n🎤 The *Ave Maria*, sung in Latin."
        message["file"] = discord.File(path, filename="Ave_Maria_sung.ogg")
    return message


async def send_rosary(ctx, query: str = "") -> None:
    q = query.strip().lower()
    kind = next((k for k in MYSTERIES if q and k.startswith(q[:4])), None)
    if q and kind is None:
        await ctx.send("Which mysteries? `!rosary joyful`, `luminous`, `sorrowful` or `glorious`, "
                       "or `!rosary` for today's.")
        return
    if kind:
        why = f"the {kind.capitalize()} Mysteries"
    else:
        day = datetime.datetime.now(datetime.timezone.utc).date()
        kind = mysteries_for(day)
        why = f"{day.strftime('%A')}'s mysteries, the {kind.capitalize()}"
    await ctx.send(**rosary_message(kind, why))


@bot.command(name="rosary", aliases=["rosario"])
async def cmd_rosary(ctx, *, query: str = ""):
    """The Rosary, a decade at a time, with the day's mysteries and their Bible passages.
    Usage: !rosary             — today's mysteries
           !rosary sorrowful   — joyful, luminous, sorrowful or glorious"""
    await send_rosary(ctx, query)


@bot.tree.command(name="rosary", description="The Rosary, a decade at a time, with the day's mysteries")
@discord.app_commands.describe(mysteries="joyful, luminous, sorrowful or glorious; empty for today's")
async def rosary_slash(interaction: discord.Interaction, mysteries: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_rosary(ctx, mysteries)
