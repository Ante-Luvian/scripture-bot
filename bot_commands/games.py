"""
Games.
  !whoami      Who Am I? -- a mystery person from the Bible, with clues that
               get easier one at a time (from the !who data). Anyone in the
               channel can guess; the first right answer wins.
  !versle      Versle -- the same well-known verse for everyone each day
               (data/versle_pool.json); guess where it is in six tries, told
               after each guess how close the book, chapter and verse were.
               Progress and streaks: data/versle.json.
"""
import datetime
import json
import random
import re

import discord
from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log, lookup
from bot_commands import people
from scripture_lookup import BIBLE_NT, BIBLE_OT

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


# ── Versle ──────────────────────────────────────────────────────────────────

VERSLE_PATH = ROOT / "data" / "versle.json"
POOL_PATH = ROOT / "data" / "versle_pool.json"
FIRST_DAY = datetime.date(2026, 10, 13)            # Versle #1
TRIES = 6
NEAR = 3                                            # within this many books/chapters/verses: 🟨
CANON = BIBLE_OT + BIBLE_NT


def today_utc() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def puzzle_number(day: "datetime.date | None" = None) -> int:
    return ((day or today_utc()) - FIRST_DAY).days + 1


def answer_for(number: int) -> str:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))["verses"]
    return pool[(number - 1) % len(pool)]


def split_ref(ref: str) -> "tuple | None":
    """'1 Corinthians 13:4' -> ('1 Corinthians', 13, 4)"""
    m = re.match(r"^(.+?) (\d+):(\d+)$", ref)
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m and m.group(1) in CANON else None


def read_guess(text: str) -> "tuple[str | None, str]":
    """A player's guess -> (canonical reference, '') or (None, why not)."""
    result = lookup.get_verse(text.strip())
    if not result.get("found"):
        return None, "I couldn't find that verse — try something like `John 3:16`."
    ref = result["reference"]
    if not split_ref(ref):
        return None, "Guess a single verse from the 66 books of the Bible, like `Psalms 23:1`."
    return ref, ""


def judge(guess: str, answer: str) -> "tuple[str, str]":
    """(three squares for book, chapter and verse, a hint in words)"""
    (gb, gc, gv), (ab, ac, av) = split_ref(guess), split_ref(answer)
    gi, ai = CANON.index(gb), CANON.index(ab)

    def square(diff):
        return "🟩" if diff == 0 else "🟨" if abs(diff) <= NEAR else "⬛"

    def way(diff, unit, later, earlier):
        n = abs(diff)
        return f"{later if diff > 0 else earlier} (by {n} {unit}{'s' if n != 1 else ''})"
    squares = square(ai - gi)
    if gi != ai:
        testament = "" if (gi < len(BIBLE_OT)) == (ai < len(BIBLE_OT)) else \
            (" — in the New Testament" if ai >= len(BIBLE_OT) else " — in the Old Testament")
        hint = "Book: " + way(ai - gi, "book", "later in the Bible", "earlier in the Bible") + testament
        return squares + "⬛⬛", hint
    squares += square(ac - gc)
    if gc != ac:
        return squares + "⬛", "Right book! Chapter: " + way(ac - gc, "chapter", "later", "earlier")
    squares += square(av - gv)
    if gv != av:
        return squares, "Right chapter! Verse: " + way(av - gv, "verse", "later", "earlier")
    return squares, "That's it!"


def _load_versle() -> dict:
    try:
        data = json.loads(VERSLE_PATH.read_text(encoding="utf-8")) if VERSLE_PATH.exists() else {}
    except Exception:
        data = {}
    data.setdefault("days", {})
    data.setdefault("players", {})
    return data


def _blank_game() -> dict:
    return {"guesses": [], "done": False, "won": False}


def record_guess(user_id: int, number: int, ref: str) -> dict:
    """Add a guess to that day's game; returns the player's game {"guesses", "done", "won"}."""
    data = _load_versle()
    game = data["days"].setdefault(str(number), {}).setdefault(str(user_id), _blank_game())
    if game["done"]:
        return game
    game["guesses"].append(ref)
    game["won"] = ref == answer_for(number)
    game["done"] = game["won"] or len(game["guesses"]) >= TRIES
    if game["done"]:
        p = data["players"].setdefault(str(user_id), {"played": 0, "won": 0, "streak": 0, "best": 0, "last": 0})
        p["played"] += 1
        if game["won"]:
            p["won"] += 1
            p["streak"] = p["streak"] + 1 if p["last"] == number - 1 else 1
            p["best"] = max(p["best"], p["streak"])
        else:
            p["streak"] = 0
        p["last"] = number
    for day in [d for d in data["days"] if int(d) < number - 7]:      # a week of old games is plenty
        del data["days"][day]
    _atomic_write_json(VERSLE_PATH, data)
    return game


def player_game(user_id: int, number: int) -> dict:
    return _load_versle()["days"].get(str(number), {}).get(str(user_id), _blank_game())


def player_stats(user_id: int) -> dict:
    return _load_versle()["players"].get(str(user_id), {"played": 0, "won": 0, "streak": 0, "best": 0, "last": 0})


def grid(game: dict, answer: str) -> str:
    return "\n".join(judge(g, answer)[0] for g in game["guesses"])


def puzzle_embed(number: int) -> discord.Embed:
    answer = answer_for(number)
    text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", lookup.get_verse(answer)["text"]).strip()
    embed = discord.Embed(title=f"📜 Versle #{number}", color=COLOR,
                          description=f"*{text}*\n\nWhere in the Bible is this verse? You have {TRIES} guesses. "
                                      f"After each one I'll tell you privately how close you are:\n"
                                      f"🟩 right · 🟨 within {NEAR} · ⬛ further off — for the **book**, the "
                                      f"**chapter** and the **verse**.")
    embed.set_footer(text="A new verse every day at midnight UTC · everyone gets the same one · KJV")
    return embed


def progress_text(game: dict, number: int) -> str:
    answer = answer_for(number)
    lines = []
    for g in game["guesses"]:
        squares, hint = judge(g, answer)
        lines.append(f"{squares} **{g}** — {hint}")
    if game["won"]:
        lines.append(f"\n🎉 **Solved in {len(game['guesses'])}/{TRIES}!**")
    elif game["done"]:
        lines.append(f"\nThe verse was **{answer}**. Better luck tomorrow!")
    else:
        lines.append(f"\n{TRIES - len(game['guesses'])} guess(es) left — press **Guess** again.")
    return "\n".join(lines)


def share_text(name: str, game: dict, number: int) -> str:
    score = f"{len(game['guesses'])}/{TRIES}" if game["won"] else f"X/{TRIES}"
    return f"📜 **{name}** — Versle #{number} {score}\n{grid(game, answer_for(number))}"


class VersleModal(discord.ui.Modal, title="Versle: where is it?"):
    guess = discord.ui.TextInput(label="Your guess (a verse)", placeholder="e.g. John 3:16", max_length=40)

    def __init__(self, number: int):
        super().__init__()
        self.number = number

    async def on_submit(self, interaction: discord.Interaction):
        ref, why = read_guess(str(self.guess.value))
        if ref is None:
            await interaction.response.send_message(why, ephemeral=True)
            return
        game = record_guess(interaction.user.id, self.number, ref)
        text, extra = progress_text(game, self.number), {}
        if game["done"]:
            s = player_stats(interaction.user.id)
            text += f"\nStreak: {s['streak']} 🔥 · solved {s['won']} of {s['played']}"
            view = discord.ui.View(timeout=None)
            view.add_item(VersleButton("share", self.number))
            extra["view"] = view
        await interaction.response.send_message(text, ephemeral=True, **extra)


class VersleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"versle:(?P<action>guess|share):(?P<n>\d+)"):
    def __init__(self, action: str, number: int):
        label, emoji, style = {"guess": ("Guess", "✍️", discord.ButtonStyle.primary),
                               "share": ("Share my result", "📣", discord.ButtonStyle.secondary)}[action]
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style,
                                           custom_id=f"versle:{action}:{number}"))
        self.action, self.number = action, number

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], int(match["n"]))

    async def callback(self, interaction: discord.Interaction):
        today = puzzle_number()
        game = player_game(interaction.user.id, self.number)
        if self.action == "share":
            if not game["done"]:
                await interaction.response.send_message("Finish the puzzle first!", ephemeral=True)
                return
            await interaction.response.send_message(share_text(interaction.user.display_name, game, self.number))
        elif self.number != today:
            await interaction.response.send_message(f"That puzzle is over — today's is Versle #{today}: `!versle`.",
                                                    ephemeral=True)
        elif game["done"]:
            await interaction.response.send_message(progress_text(game, self.number), ephemeral=True)
        else:
            await interaction.response.send_modal(VersleModal(self.number))


bot.add_dynamic_items(VersleButton)


async def send_versle(ctx, arg: str = "") -> None:
    number = puzzle_number()
    if arg.strip().lower() in ("stats", "streak", "me"):
        s = player_stats(ctx.author.id)
        await ctx.send(f"📜 Versle: solved **{s['won']}** of **{s['played']}** · streak **{s['streak']}** "
                       f"(best {s['best']})")
        return
    view = discord.ui.View(timeout=None)            # persistent: the button works all day
    view.add_item(VersleButton("guess", number))
    await ctx.send(embed=puzzle_embed(number), view=view)


def yesterday_line(number: int) -> str:
    """'Yesterday's verse (Versle #4) was John 3:16 -- 5 of 7 players solved it.'"""
    if number <= 1:
        return ""
    games = _load_versle()["days"].get(str(number - 1), {})
    done = [g for g in games.values() if g["done"]]
    solved = sum(1 for g in done if g["won"])
    who = f" — {solved} of {len(done)} player{'s' if len(done) != 1 else ''} solved it" if done else ""
    return f"Yesterday's verse (Versle #{number - 1}) was **{answer_for(number - 1)}**{who}."


# ── the daily post (!verslesetup) ───────────────────────────────────────────
# Per-server settings in guild_config.json: versle_channel_id, versle_time ("HH:MM" UTC).
# versle.json "posted" {guild: puzzle number} stops a restart posting twice.

DEFAULT_VERSLE_TIME = "00:05"


async def post_daily_versle(guild_id, channel, number: int, force: bool = False) -> bool:
    data = _load_versle()
    posted = data.setdefault("posted", {})
    if posted.get(str(guild_id)) == number and not force:
        return False
    view = discord.ui.View(timeout=None)
    view.add_item(VersleButton("guess", number))
    await channel.send(content=yesterday_line(number) or None, embed=puzzle_embed(number), view=view)
    data = _load_versle()                         # (a guess may have been saved meanwhile)
    data.setdefault("posted", {})[str(guild_id)] = number
    _atomic_write_json(VERSLE_PATH, data)
    return True


async def run_daily_versles(client, number: int, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("versle_channel_id")
        if not channel_id or g.get("versle_time", DEFAULT_VERSLE_TIME) != current_hm:
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_daily_versle(guild_id, channel, number)
        except Exception:
            log.exception(f"Failed to post the daily Versle for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_versle_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_versles(bot, puzzle_number(now.date()), f"{now.hour:02d}:{now.minute:02d}")


@daily_versle_task.before_loop
async def _before_daily_versle():
    await bot.wait_until_ready()


@bot.command(name="verslesetup", aliases=["versleconfig"])
@commands.has_permissions(administrator=True)
async def cmd_verslesetup(ctx, action: str = "", *, arg: str = ""):
    """Post each day's Versle in a channel.
    Usage: !verslesetup                  — show this server's settings
           !verslesetup channel #chan    — post the day's puzzle there
           !verslesetup time 00:05       — daily post time (24h UTC; a new verse starts at midnight UTC)
           !verslesetup test             — post today's now
           !verslesetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("versle_channel_id"), g.get("versle_time", DEFAULT_VERSLE_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"📜 Daily Versle — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!verslesetup channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, versle_channel_id=None)
        await ctx.send("The daily Versle post is off for this server. (`!versle` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!verslesetup channel #games`")
            return
        _update_guild_config(ctx.guild.id, versle_channel_id=channel.id)
        await ctx.send(f"Each day's Versle will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!verslesetup time 07:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, versle_time=hm)
        await ctx.send(f"Daily Versle time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_daily_versle(ctx.guild.id, channel, puzzle_number(), force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")


@bot.command(name="versle", aliases=["dailyverse"])
async def cmd_versle(ctx, *, arg: str = ""):
    """Versle: today's verse -- where in the Bible is it? Six guesses.
    Usage: !versle         — today's puzzle
           !versle stats   — your record and streak"""
    await send_versle(ctx, arg)


@bot.tree.command(name="versle", description="Versle: today's verse — where in the Bible is it? Six guesses")
async def versle_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_versle(ctx)
