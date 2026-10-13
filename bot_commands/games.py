"""
Games.
  !whoami      Who Am I? -- a mystery person from the Bible, with clues that
               get easier one at a time (from the !who data). Anyone in the
               channel can guess; the first right answer wins.
"""
import random
import re

import discord

from core import bot, log, lookup
from bot_commands import people

BLANK = "❓"
GAME_SECONDS = 600
MIN_VERSES = 20                      # someone a Bible reader could know
COLOR = discord.Color.from_rgb(110, 70, 150)


# ── Who Am I? ───────────────────────────────────────────────────────────────

def _names_of(p: dict) -> set:
    names = {p["name"], p["short"], *p.get("also", [])}
    # (proper names only: Mary's record lists "mother" as another name for her)
    out = {re.sub(r"\s*\(.*\)$", "", n).strip() for n in names if n and n[0].isupper()}
    for n in list(out):                             # "Simon Peter": "Peter" on its own too
        words = n.split()
        if len(words) == 2:
            out.update(w for w in words if w[0].isupper())
    return out


def blank_out(text: str, p: dict) -> str:
    """The text with the person's names hidden."""
    for name in sorted(_names_of(p), key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(name)}\b", BLANK, text, flags=re.I)
    return text


def name_meaning(about: str) -> str:
    """Easton's opens most entries with what the name means: 'Beloved, the eighth son…' -> 'Beloved'."""
    first = re.split(r"[,.;(]", about or "", maxsplit=1)[0].strip()
    words = first.split()
    if not 1 <= len(words) <= 4 or words[0] in ("The", "One", "Beyond") or \
            (words[0] in ("A", "An") and len(words) > 2) or \
            re.search(r"\b(son|daughter|king|wife|father|mother|brother)\b", first, re.I):
        return ""
    if any(w[0].isupper() and w not in ("God", "Jehovah", "Lord") for w in words[1:]) or \
            not first[0].isalpha() or re.search(r"[=“\"']|\bAlso\b", first):
        return ""                                   # "Originally called Simon", "Also “Huram”"
    return first


def dictionary_line(about: str, p: dict) -> str:
    """The dictionary entry's first real sentence, with the name hidden."""
    meaning = name_meaning(about)
    text = about[len(meaning):].lstrip(" ,;") if meaning else (about or "")
    text = re.sub(r"\s*\([^)]*\)", "", text).lstrip(" ,;")                # "(Gen. 41:52)", "(=Simon)"
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].strip()
    if len(sentence) < 25:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    return blank_out(sentence[:300], p)


def _people_list(slugs: list, limit: int = 3) -> str:
    names = [people.data()["people"][s]["name"] for s in slugs if s in people.data()["people"]]
    names = [re.sub(r"\s*\(.*\)$", "", n) for n in names]
    if len(names) > limit:
        return ", ".join(names[:limit]) + f" and {len(names) - limit} more"
    return " and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else (names[0] if names else "")


def _a_verse(p: dict, rng: random.Random) -> str:
    refs = list(p["verses"])
    rng.shuffle(refs)
    for ref in refs[:12]:
        result = lookup.get_verse(ref)
        if not result.get("found"):
            continue
        text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", result["text"]).strip()
        hidden = blank_out(text, p)
        if BLANK in hidden and 60 <= len(hidden) <= 320:
            return f"*{hidden}* ({blank_out(result['reference'], p)})"
    return ""


def make_clues(slug: str, rng: random.Random = random) -> list:
    """Clues about a person, hardest first."""
    data = people.data()
    p = data["people"][slug]
    books = []
    for ref in p["verses"]:
        book = ref.rsplit(" ", 1)[0]
        if book not in books:
            books.append(book)
    he = "woman" if p.get("gender") == "Female" else "man"
    first = f"I am a {he} named in {len(p['verses'])} verses of the Bible"
    if BLANK in blank_out(" ".join(books), p):      # Ruth, Esther, Job: a book bears the name
        first += f", in {len(books)} book{'s' if len(books) != 1 else ''}."
    elif len(books) > 1:
        first += f", in {len(books)} books, from {books[0]} to {books[-1]}."
    else:
        first += f", all in {books[0]}."
    clues = [first]

    counts = []
    for key, one, many in (("children", "child", "children"), ("siblings", "brother or sister", "brothers and sisters"),
                           ("partners", "wife" if he == "man" else "husband", "wives" if he == "man" else "husbands")):
        n = len(p[key])
        if n:
            counts.append(f"{n} {one if n == 1 else many}")
    if counts:
        clues.append("In my family I had " + ", ".join(counts[:-1]) + (" and " if len(counts) > 1 else "")
                     + counts[-1] + ".")

    places = data["places"]
    where = []
    if p["groups"]:
        groups = [g for g in p["groups"] if g != "Genealogy of Jesus"]
        if groups and BLANK in blank_out(groups[0], p):
            where.append("One of the tribes of Israel is named after me" if groups[0].startswith("Tribe")
                         else "A group in the Bible is named after me")
        elif groups:
            where.append(f"I belonged to the {groups[0]}")
        if "Genealogy of Jesus" in p["groups"] and BLANK not in blank_out("Jesus", p):
            where.append("I'm in the family line of Jesus")
    if p["born"] and p["born"][0] in places:
        where.append(f"I was born in {places[p['born'][0]]['name']}")
    if p["died"] and p["died"][0] in places:
        place = places[p["died"][0]]["name"]
        where.append(f"I died {'on' if place.startswith('Mount') else 'in'} {place}")
    if where:
        clues.append(". ".join(where) + ".")

    meaning = name_meaning(p["about"])
    if meaning:
        clues.append(f"My name means “{meaning}”.")
    line = dictionary_line(p["about"], p)
    if line:
        clues.append(f"A Bible dictionary says of me: “{line}”")
    verse = _a_verse(p, rng)
    if verse:
        clues.append(f"A verse about me: {verse}")

    family = []
    if p["father"]:
        family.append(f"my father was {_people_list(p['father'])}")
    if p["mother"]:
        family.append(f"my mother was {_people_list(p['mother'])}")
    if p["partners"]:
        family.append(f"I married {_people_list(p['partners'])}")
    if p["children"]:
        family.append(f"my children included {_people_list(p['children'])}")
    if family:
        text = blank_out("; ".join(family), p)
        clues.append(text[0].upper() + text[1:] + ".")

    clues = [blank_out(c, p) for c in clues]        # whatever slipped through: a place, a group
    words = re.sub(r"\s*\(.*\)$", "", p["name"]).split()
    if len(words) == 1:
        clues.append(f"My name begins with **{words[0][0].upper()}** and has {len(words[0])} letters.")
    else:
        clues.append(f"My name is {len(words)} words, beginning **" + " ".join(w[0] + "…" for w in words)
                     + "** — either part will do as an answer.")
    return clues


def pick_person(rng: random.Random = random) -> "tuple[str, list]":
    """A well-known person with plenty of clues."""
    candidates = [s for s, p in people.data()["people"].items() if len(p["verses"]) >= MIN_VERSES]
    for _ in range(30):
        slug = rng.choice(candidates)
        clues = make_clues(slug, rng)
        if len(clues) >= 5:
            return slug, clues
    return slug, clues


def is_right(guess: str, slug: str) -> bool:
    """Any name that leads to this person: 'Jacob', 'Israel', 'King David'."""
    g = people._norm(guess)
    g = re.sub(r"^(king|queen|prophet|the|saint|st|apostle) ", "", g)
    if not g:
        return False
    index = people._index("people")
    return slug in index.get(g, []) or g in {people._norm(n) for n in _names_of(people.data()["people"][slug])}


class GuessModal(discord.ui.Modal, title="Who am I?"):
    guess = discord.ui.TextInput(label="Your guess", placeholder="A name from the Bible", max_length=60)

    def __init__(self, game: "WhoAmIView"):
        super().__init__()
        self.game = game

    async def on_submit(self, interaction: discord.Interaction):
        await self.game.check(interaction, str(self.guess.value))


class WhoAmIView(discord.ui.View):
    """One round. Not persistent: a round is over long before a restart matters."""

    def __init__(self, slug: str, clues: list):
        super().__init__(timeout=GAME_SECONDS)
        self.slug, self.clues = slug, clues
        self.shown = 1
        self.guessed: dict[int, int] = {}        # user id -> the clue they last guessed on
        self.winner = None
        self.over = False
        self.message = None

    def embed(self) -> discord.Embed:
        lines = [f"**{i}.** {c}" for i, c in enumerate(self.clues[:self.shown], 1)]
        embed = discord.Embed(title="🕵️ Who am I?", description="\n\n".join(lines), color=COLOR)
        if self.over:
            p = people.data()["people"][self.slug]
            who = f"🎉 **{self.winner}** got it on clue {self.shown}!" if self.winner else "Nobody got it this time."
            embed.add_field(name=f"I am {p['name']}", value=f"{who}\nMore: `!who {people._bare(p['name'])}` · "
                                                            f"`!tree {people._bare(p['name'])}`", inline=False)
            embed.set_footer(text="!whoami for another")
        else:
            left = len(self.clues) - self.shown
            embed.set_footer(text=f"Clue {self.shown} of {len(self.clues)} · Guess below — one guess per clue each"
                                  + (f" · {left} easier clue{'s' if left != 1 else ''} to come" if left else ""))
        return embed

    async def _finish(self, interaction: "discord.Interaction | None" = None) -> None:
        self.over = True
        self.stop()
        for item in self.children:
            item.disabled = True
        if interaction is not None and not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.embed(), view=self)
        elif self.message is not None:
            try:
                await self.message.edit(embed=self.embed(), view=self)
            except discord.HTTPException as e:
                log.warning(f"Couldn't end the Who am I? round: {e}")

    async def check(self, interaction: discord.Interaction, guess: str) -> None:
        if self.over:
            await interaction.response.send_message("This round is over — `!whoami` for another.", ephemeral=True)
            return
        if self.guessed.get(interaction.user.id) == self.shown:
            await interaction.response.send_message("You've had your guess for this clue — wait for the next one.",
                                                    ephemeral=True)
            return
        self.guessed[interaction.user.id] = self.shown
        if is_right(guess, self.slug):
            self.winner = interaction.user.display_name
            await self._finish(interaction)
        else:
            await interaction.response.send_message(f"❌ Not {guess.strip()[:60]}. Try again after the next clue.",
                                                    ephemeral=True)

    @discord.ui.button(label="Guess", emoji="✍️", style=discord.ButtonStyle.primary)
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GuessModal(self))

    @discord.ui.button(label="Next clue", emoji="💡", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.shown < len(self.clues):
            self.shown += 1
        if self.shown == len(self.clues):
            button.disabled = True
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Give up", emoji="🏳️", style=discord.ButtonStyle.secondary)
    async def give_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish(interaction)

    async def on_timeout(self):
        if not self.over:
            await self._finish()


async def start_whoami(ctx) -> None:
    slug, clues = pick_person()
    view = WhoAmIView(slug, clues)
    view.message = await ctx.send(embed=view.embed(), view=view)


@bot.command(name="whoami", aliases=["mystery", "whoisit"])
async def cmd_whoami(ctx):
    """Who Am I? Guess a person from the Bible from clues that get easier."""
    await start_whoami(ctx)


@bot.tree.command(name="whoami", description="Who Am I? Guess a person from the Bible from clues that get easier")
async def whoami_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await start_whoami(ctx)
