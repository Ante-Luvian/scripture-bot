"""
Ask the library: mention the bot with a question in a channel a server admin has opened to it, and it finds the
passages of the Classical and Christian libraries that bear on it and answers from them, citing each (every
citation one `!verse` can open). Replying to its answer carries the conversation on.

  @ScriptureBot what does Plotinus say evil is?
  !asksetup #channel        (admin) let people ask the library in this channel; again to stop
  !askcap [n]               (owner) the answers allowed a day, across all servers

The finding is free: a full-text index (SQLite FTS5, in memory, ranked by BM25) of every passage, built in the
background when the bot starts, if any server has opened a channel to it (about 40 seconds). The answer is one request to Claude Haiku,
which is paid for, so it is capped: ASK_DEFAULT_CAP answers a day across all servers (the owner can change it),
and one question per person per ASK_COOLDOWN seconds. Without ANTHROPIC_API_KEY it says it can't answer.
"""
import asyncio
import collections
import datetime as dt
import json
import os
import re
import sqlite3
import time
import urllib.request

import discord
from discord.ext import commands

from core import ROOT, _load_guild_config, _update_guild_config, bot, bot_is_owner, log, lookup, tradition_enabled

ASK_USAGE_PATH = ROOT / "data" / "ask_usage.json"          # {"day": "YYYY-MM-DD", "count": n, "cap": n}
MODEL = "claude-haiku-5-5"
ASK_DEFAULT_CAP = 50              # (about a cent an answer, its thinking included: ~50 cents a day at most)
ASK_COOLDOWN = 30                 # seconds between one person's questions
PASSAGES = 8                      # passages sent with a question
# the most of one passage sent, by its rank (a long one is cut around the words asked about): the best three
# whole enough to follow an argument, the rest a glimpse (about 10,000 characters in all, as 8 x 1,200 was)
PASSAGE_CHARS = (2400, 2400, 2400, 700, 700, 700, 700, 700)
PER_BOOK = 2                      # passages from one book, unless the question names its author or the book
PER_NAMED_BOOK = 5
HISTORY = 3                       # earlier exchanges of a conversation sent with a follow-up

# the libraries it reads: the Classical shelf and the Christian ones
CORPORA = ("classical", "kjv", "nt_apocrypha", "apostolic_fathers", "patristics", "charles", "medieval", "reformation")
SCRIPTURE = {"kjv"}
PLANNED = 5                       # passages the plan names that are fetched first (the search fills the rest)

_STOP = set("""a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her
here hers herself him himself his how i if in into is it its itself just me more most my myself no nor not now of off
on once only or other our ours out over own same she should so some such than that the their theirs them then there
these they this those through to too under until up very was we were what when where which while who whom why will
with would you your yours say says said tell think thought believe believed according teach teaches taught view views
idea ideas mean means meaning explain describe""".split())

_last_ask: dict = {}                         # user id -> when they last asked
_conversations: dict = {}                    # the bot's answer message id -> [(question, answer), ...]
_building = None                             # (an asyncio.Lock, made on first use)


# ── the index ──────────────────────────────────────────────────────────────

def _shelves() -> dict:
    """{book: the shelves above it in !books (["Classical", "Platonic", "Plotinus"])}: so "Plotinus" finds the
    Enneads."""
    from bot_commands.books import BOOKS_TREE
    out = {}

    def walk(node, path):
        for item in node:
            if isinstance(item, tuple):
                walk(item[1], path + [re.sub(r"[^\w\s'-]", "", item[0]).strip()])
            else:
                out.setdefault(item, path)
    walk(BOOKS_TREE, [])
    return out


def _named(book: str, shelves: list, question: str) -> bool:
    """Whether the question names the book, or the author whose shelf it's on ("what does Plotinus say...")."""
    q = question.lower()
    names = [book] + shelves[-1:]                    # (the nearest shelf is the author's: "Plotinus", "Origen")
    return any(len(n) >= 4 and re.search(rf"\b{re.escape(n.lower())}\b", q) for n in names)


class Index:
    """A full-text index (SQLite FTS5, in memory, ranked by BM25) of every passage in `corpora`. It holds only the
    words, not a second copy of the texts: row n is self.where[n], read back from the lookup."""

    def __init__(self, corpora=CORPORA):
        self.shelves = shelves = _shelves()
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE passages USING fts5(text, book, shelf, content='', "
                        "tokenize='porter unicode61 remove_diacritics 2')")
        self.where = []                                     # rowid - 1 -> (corpus, book, chapter, verse)
        self.span = {}                                      # corpus -> (first rowid, last rowid): each is a run
        for corpus in corpora:
            first = len(self.where) + 1
            for book, chapters in lookup._data.get(corpus, {}).items():
                rows = []
                for chap, verses in chapters.items():
                    for verse, text in verses.items():
                        if isinstance(text, str) and len(text.strip()) > 8:     # ("I and my Father are one.")
                            self.where.append((corpus, book, chap, verse))
                            rows.append((len(self.where), text, book, " ".join(shelves.get(book, []))))
                self.db.executemany("INSERT INTO passages (rowid, text, book, shelf) VALUES (?, ?, ?, ?)", rows)
            self.span[corpus] = (first, len(self.where))
        self.db.commit()

    def search(self, query: str, n: int = 200, corpora=None) -> list:
        """[(corpus, book, chapter, verse)], best first, from `corpora` only (in the search itself: the best 200
        of the whole library can hold no Bible verse at all)."""
        spans = [self.span[c] for c in (corpora or self.span) if c in self.span]
        if not spans:
            return []
        where = " OR ".join("rowid BETWEEN ? AND ?" for _ in spans)
        rows = self.db.execute(f"SELECT rowid FROM passages WHERE passages MATCH ? AND ({where}) "
                               "ORDER BY bm25(passages, 1.0, 6.0, 4.0) LIMIT ?",
                               (query, *[x for s in spans for x in s], n)).fetchall()
        return [self.where[r - 1] for (r,) in rows]


_index = None                                               # (built in the background when the bot starts)


def _terms(question: str) -> list:
    words = re.findall(r"[A-Za-zÀ-ÿ]{3,}", question.lower())
    return list(dict.fromkeys(w for w in words if w not in _STOP))


def _excerpt(text: str, terms: list, room: int) -> str:
    """A long passage cut to `room` characters around the first of the words asked about."""
    if len(text) <= room:
        return text
    low = text.lower()
    at = min((i for i in (low.find(t[:6]) for t in terms) if i >= 0), default=0)
    start = max(0, min(at - room // 4, len(text) - room))
    piece = text[start:start + room]
    return ("…" if start else "") + piece + ("…" if start + room < len(text) else "")


def find_passages(question: str, guild_id=None, index=None, limit: int = PASSAGES, corpora=CORPORA,
                  phrase: bool = False) -> list:
    """[{"reference", "text"}] of the passages that best answer the question, best first: no more than PER_BOOK
    from one book (PER_NAMED_BOOK from a book the question names, or its author), and only from the traditions
    the server has."""
    from scripture_lookup import CORPUS_TRADITION
    index = index or _index
    terms = _terms(question)
    if index is None:
        return []
    rows = []
    if phrase:                                      # (a planned search, "I am": the words together, common or not)
        words = re.findall(r"[A-Za-zÀ-ÿ']+", question)
        if words:
            rows += index.search('"' + " ".join(w.replace("'", " ") for w in words) + '"', corpora=corpora)
    # passages with all the words first; then, if they're few, those with any (common words alone are noise)
    for joiner in ((" AND ", " OR ") if terms else ()):
        rows += [r for r in index.search(joiner.join(f'"{t}"' for t in terms), corpora=corpora) if r not in rows]
        if len(rows) >= limit * 3 or len(terms) == 1:
            break
    if not rows:
        return []
    out, per_book, seen = [], collections.Counter(), set()
    def worth(row) -> int:
        """0 a passage of substance, 1 a short one (a line of a letter's farewell), 2 a list of contents."""
        text = lookup._data[row[0]][row[1]][row[2]][row[3]]
        if len(re.findall(r"(?:^|\s)\d{1,3}\.\s", text)) >= 4:
            return 2
        return 0 if len(text) >= 200 or row[0] in SCRIPTURE else 1     # (a Bible verse is short by nature)
    rows = [r for r in sorted(rows, key=worth) if worth(r) < 2 and r[0] in corpora]   # (sorted keeps the ranking)
    named = {}
    for corpus, book, chap, verse in rows:
        if book not in named:
            named[book] = _named(book, index.shelves.get(book, []), question)
        if per_book[book] >= (PER_NAMED_BOOK if named[book] else PER_BOOK) \
                or not tradition_enabled(guild_id, CORPUS_TRADITION.get(corpus)):
            continue
        text = lookup._data[corpus][book][chap][verse]
        same = re.sub(r"\W", "", text.lower())[:200]           # (a text the library holds twice, under two titles)
        if same in seen:
            continue
        seen.add(same)
        per_book[book] += 1
        out.append({"reference": lookup._cite(book, chap, verse), "named": named[book],
                    "text": _excerpt(text, terms, PASSAGE_CHARS[min(len(out), len(PASSAGE_CHARS) - 1)])})
        if len(out) == limit:
            break
    # a question about an author or a book, with enough of them found, gets only them: told to ignore passages that
    # merely share a word, the model still reports on them ("the Sozomen passage mentions Plotinus only...")
    if sum(p["named"] for p in out) >= 3:
        out = [p for p in out if p["named"]]
    return [{"reference": p["reference"], "text": p["text"]} for p in out]


# ── the plan: what a scholar would look up ─────────────────────────────────
# A search for the question's own words misses the answer when the texts don't use them: "does Christ claim to be
# God?" found Hilary, not John 8:58 ("Before Abraham was, I am") or 10:30. So a first, small request asks for the
# passages to check and for searches in the texts' own wording. Those are only where to look: what the answer may
# use is still what the bot finds in its library, and a reference the library hasn't is dropped.

PLAN = """A Discord bot answers questions from its library: the King James Bible, the Church Fathers (Ante-Nicene, \
Nicene and Post-Nicene, in the standard 19th-century translations), Christian mystics, and Greek and Roman \
philosophy and religion (Plato, Aristotle, Plotinus, Porphyry, Iamblichus, Proclus, the Hermetica, the Stoics). \
Plan its search for the question below. Reply with only a JSON object:
{"shelves": [which of "bible", "apocrypha", "fathers", "later_christian", "classical" to search. A question about \
what someone said, claimed or taught is answered from their own words: what Christ or an apostle says -> ["bible"]; \
what Plotinus or Plato says -> ["classical"]; what Augustine says -> ["fathers"]. Add "fathers" only for what the \
Church or its teachers taught or how they read a text, "later_christian" for the medieval and Reformation writers \
and mystics],
 "references": [up to 6 passages that most directly answer it, as "Book chapter:verse" (Bible books by their KJV \
names, e.g. "John 10:30", "Philippians 2:5-8"), the most important first; for other works only when you are sure \
of the exact book, chapter and section, else leave them out],
 "searches": [up to 3 short searches, in the words the texts themselves would use (the KJV's English for the Bible: \
"I am", "equal with God")]}
Give both sides where the question is disputed."""


SHELVES = {"bible": ("kjv",), "apocrypha": ("nt_apocrypha", "charles"), "fathers": ("apostolic_fathers", "patristics"),
           "later_christian": ("medieval", "reformation"), "classical": ("classical",)}


def _plan(question: str, history: list) -> dict:
    """{"corpora": (...), "references": [...], "searches": [...]}: everywhere and nothing named if the plan can't
    be had."""
    earlier = "".join(f"(Earlier question: {q})\n" for q, _ in history[-HISTORY:])
    try:
        reply = _ask_claude(PLAN, [{"role": "user", "content": f"{earlier}Question: {question}"}], max_tokens=1200)
        data = json.loads(re.search(r"\{.*\}", reply, re.S).group(0))
    except Exception as e:
        log.warning(f"ASK  no plan: {type(e).__name__}: {e}")
        return {"corpora": CORPORA, "references": [], "searches": []}
    clean = lambda v, n: [s.strip() for s in v if isinstance(s, str) and 0 < len(s.strip()) <= 80][:n] \
        if isinstance(v, list) else []
    corpora = tuple(c for s in clean(data.get("shelves"), 5) for c in SHELVES.get(s.lower(), ()))
    plan = {"corpora": corpora or CORPORA, "references": clean(data.get("references"), 6),
            "searches": clean(data.get("searches"), 3)}
    log.info(f"ASK  plan: {plan}")
    return plan


def gather(question: str, guild_id, plan: dict, index=None) -> list:
    """The passages to answer from, from the plan's shelves only: those it names that the library has (up to
    PLANNED), then the best the searches find."""
    from scripture_lookup import CORPUS_TRADITION
    corpora = plan.get("corpora") or CORPORA
    out, refs = [], set()
    for ref in plan.get("references", []):
        if len(out) == PLANNED:
            break
        try:
            r = lookup.get_verse(ref)
        except Exception:
            continue
        if not r.get("found") or not r.get("text"):
            continue
        corpus = lookup._resolve_book(r["reference"].rsplit(" ", 1)[0])[0]
        if corpus not in corpora or not tradition_enabled(guild_id, CORPUS_TRADITION.get(corpus)):
            continue
        text = re.sub(r"\*\*\[(\d+)\]\*\*\s*", r"(\1) ", r["text"]).strip()     # ("**[30]**" -> "(30)")
        out.append({"reference": r["reference"], "text": _excerpt(text, _terms(question), max(PASSAGE_CHARS))})
        refs.add(r["reference"])
    want = PASSAGES + min(len(out), 3)              # (room for the search's finds beside the planned ones)
    searches = [(s, True) for s in plan.get("searches", [])] + [(question, False)]
    for search, phrase in searches:                 # (the plan's searches first: the question's own words may
        for p in find_passages(search, guild_id, index=index, corpora=corpora, phrase=phrase,   # not be the texts')
                               limit=3 if phrase else PASSAGES):
            if len(out) >= want:
                return out
            if p["reference"] not in refs:
                out.append(p)
                refs.add(p["reference"])
    return out


# ── the answer ─────────────────────────────────────────────────────────────

SYSTEM = """You are the reading-room voice of ScriptureBot, a Discord bot that holds a large library of Classical \
(Greek and Roman: Plato, Aristotle, the Neoplatonists, the Hermetica...) and Christian texts (the Bible, the Church \
Fathers, the mystics). Someone has asked a question; the bot has searched its library and gives you the passages \
below. Answer from those passages only.

- Cite every claim with the passage's reference in square brackets, exactly as given: [Enneads 1.8:3].
- Quote only words that are in the passages. Never invent a quotation, a reference, or what an author "also said".
- The search finds some passages that only share a word with the question. Use the ones that bear on it and \
leave the others out entirely: don't mention them or say that they don't help.
- A passage that starts or ends with "…" is an excerpt from a longer one. Don't remark on that; answer from what \
is there.
- Write as someone who knows these texts, about the subject, not about your sources: never mention "the \
passages", "the library", "the excerpts" or what they don't say, and don't end with a caveat or disclaimer of any \
kind (what you can't say, how others might read it). The citations show where everything comes from.
- Only if none of the passages answer the question, say in one sentence that you found nothing on it.
- Where the authors disagree, say so; don't harmonise them. Explain the ideas plainly for someone who hasn't read \
them; give the author's view, not your own, and don't preach.
- At most 220 words. Discord markdown: *italics* for titles, no headings, no tables."""


def _ask_claude(system: str, messages: list, max_tokens: int = 2000) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no ANTHROPIC_API_KEY")
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system, "messages": messages}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        reply = json.loads(r.read().decode("utf-8"))
    text = "".join(part.get("text", "") for part in reply.get("content", []) if part.get("type") == "text")
    log.info(f"ASK  reply: stop {reply.get('stop_reason')}, usage {reply.get('usage')}, "
             f"blocks {[p.get('type') for p in reply.get('content', [])]}, {len(text)} chars")
    if not text.strip():
        raise RuntimeError(f"no text in the reply (stop: {reply.get('stop_reason')})")
    return text


def _messages(question: str, passages: list, history: list) -> list:
    msgs = []
    for q, a in history[-HISTORY:]:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    shown = "\n\n".join(f"[{p['reference']}]\n{p['text']}" for p in passages)
    msgs.append({"role": "user", "content": f"Passages from the library:\n\n{shown}\n\nQuestion: {question}\n\n"
                 "(Cite each claim in square brackets, like [Enneads 1.8:3]. Leave out any passage that doesn't "
                 "bear on the question: don't mention it at all. Don't mention the passages or the library "
                 "themselves, and end on the substance, with no caveat.)"})
    return msgs


def checked(answer: str, passages: list) -> tuple:
    """(the answer with any citation of a passage it wasn't given taken out, the references it cites)."""
    given = {p["reference"] for p in passages}
    cited = []

    def keep(m):
        ref = m.group(1).strip()
        if ref in given:
            if ref not in cited:
                cited.append(ref)
            return f"[{ref}]"
        return ""
    answer = re.sub(r"\[([^\[\]]{3,80})\]", keep, answer)
    plain = answer.replace("*", "")
    for ref in given:                                        # (a citation written without brackets: "In Enneads 1.8:1")
        if ref not in cited and re.search(rf"(?<![\w.:]){re.escape(ref)}(?![\w:]|\.\d)", plain):
            cited.append(ref)
    cited.sort(key=lambda r: plain.find(r) if r in plain else len(plain))
    return re.sub(r"[ \t]+([,.;:])", r"\1", answer).strip(), cited


# ── the day's allowance ────────────────────────────────────────────────────

def _usage() -> dict:
    try:
        data = json.loads(ASK_USAGE_PATH.read_text(encoding="utf-8")) if ASK_USAGE_PATH.exists() else {}
    except ValueError:
        data = {}
    today = dt.date.today().isoformat()
    if data.get("day") != today:
        data = {"day": today, "count": 0, "cap": data.get("cap", ASK_DEFAULT_CAP)}
    return data


def _save_usage(data: dict) -> None:
    ASK_USAGE_PATH.write_text(json.dumps(data), encoding="utf-8")


def ask_channels(guild_id) -> set:
    return set(_load_guild_config().get(str(guild_id), {}).get("ask_channels", []))


# ── Discord ────────────────────────────────────────────────────────────────

def _question_of(message: discord.Message) -> str:
    text = re.sub(rf"<@!?{bot.user.id}>", "", message.content)
    return re.sub(r"\s+", " ", text).strip()


async def _ensure_index() -> bool:
    global _building, _index
    if _index is not None:
        return True
    if _building is None:
        _building = asyncio.Lock()
    async with _building:
        if _index is None:
            started = time.monotonic()
            _index = await asyncio.to_thread(Index)
            log.info(f"ASK  library index built: {len(_index.where):,} passages in {time.monotonic() - started:.0f}s")
    return True


@bot.listen("on_ready")
async def _build_index_at_start():
    """Only where someone may ask: a bot with no channel opened to it never spends the memory."""
    if any(cfg.get("ask_channels") for cfg in _load_guild_config().values() if isinstance(cfg, dict)):
        await _ensure_index()


async def answer(question: str, guild_id, history: list) -> tuple:
    """(the reply's text, the references it cites); raises when it can't be had."""
    plan = await asyncio.to_thread(_plan, question, history)
    search_for = " ".join([q for q, _ in history[-HISTORY:]] + [question])
    passages = await asyncio.to_thread(gather, search_for, guild_id, plan)
    if not passages:
        return ("I couldn't find anything in the library on that. Try asking with the names or words the "
                "authors would use (*the soul*, *Plotinus*, *grace*…).", [])
    reply = await asyncio.to_thread(_ask_claude, SYSTEM, _messages(question, passages, history))
    return checked(reply, passages)


@bot.listen("on_message")
async def ask_the_library(message: discord.Message):
    if message.author.bot or not message.guild or bot.user is None:
        return
    replied = message.reference.message_id if message.reference else None
    following = replied in _conversations
    if not (bot.user in message.mentions or following) or message.content.startswith("!"):
        return
    if message.channel.id not in ask_channels(message.guild.id):
        return
    question = _question_of(message)
    if len(question) < 3:
        await message.reply("Ask me something after mentioning me, e.g. "
                            f"{bot.user.mention} *what does Plotinus say evil is?*", mention_author=False)
        return
    if len(question) > 500:
        await message.reply("That's a long question: could you put it in under 500 characters?", mention_author=False)
        return
    owner = await bot_is_owner(message.author)
    wait = ASK_COOLDOWN - (time.monotonic() - _last_ask.get(message.author.id, -1e9))
    if wait > 0 and not owner:
        await message.reply(f"One question at a time: ask again in {int(wait) + 1} seconds.", mention_author=False)
        return
    usage = _usage()
    if usage["count"] >= usage["cap"] and not owner:
        await message.reply("The library's reading room has closed for today (I can answer only so many "
                            "questions a day). Ask again tomorrow, or look things up yourself with `!search`.",
                            mention_author=False)
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        await message.reply("I can't answer questions just now (no AI key is set up).", mention_author=False)
        return
    _last_ask[message.author.id] = time.monotonic()
    history = _conversations.get(replied, []) if following else []
    async with message.channel.typing():
        try:
            if not await _ensure_index():
                raise RuntimeError("the index isn't ready")
            text, cited = await answer(question, message.guild.id, history)
            if not text.strip():
                raise RuntimeError("the answer was empty")
        except Exception as e:
            why = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else str(e)
            log.warning(f"ASK  failed: {type(e).__name__}: {why}")
            await message.reply("Sorry, I couldn't answer that just now. Try again in a little while.",
                                mention_author=False)
            return
    usage = _usage()
    usage["count"] += 1
    _save_usage(usage)
    embed = discord.Embed(description=text[:4000], color=discord.Color.dark_gold())
    if cited:
        embed.set_footer(text=("📚 " + " · ".join(cited))[:2000] + "\nOpen any with !verse <reference> · "
                              "reply to this to ask more")
    else:
        embed.set_footer(text="Reply to this to ask more")
    sent = await message.reply(embed=embed, mention_author=False,
                               allowed_mentions=discord.AllowedMentions.none())
    _conversations[sent.id] = (history + [(question, text)])[-HISTORY:]
    while len(_conversations) > 500:                         # (forget the oldest conversations)
        _conversations.pop(next(iter(_conversations)))


@bot.command(name="asksetup")
@commands.has_permissions(administrator=True)
async def ask_setup(ctx, *, arg: str = ""):
    """Let people ask the library questions in a channel (mention the bot with a question).

    Usage: !asksetup #channel   — turn it on there (again to turn it off)
           !asksetup            — where it's on"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    channels = ask_channels(ctx.guild.id)
    channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
    if channel is None:
        where = ", ".join(f"<#{c}>" for c in sorted(channels)) or "*nowhere yet*"
        await ctx.send(f"People can ask the library questions in: {where}.\n"
                       "Turn it on or off in a channel with `!asksetup #channel`.")
        return
    if channel.id in channels:
        channels.discard(channel.id)
        _update_guild_config(ctx.guild.id, ask_channels=sorted(channels))
        await ctx.send(f"I won't answer questions in {channel.mention} any more.")
        return
    channels.add(channel.id)
    _update_guild_config(ctx.guild.id, ask_channels=sorted(channels))
    asyncio.create_task(_ensure_index())                   # (so the first question needn't wait for it)
    await ctx.send(f"In {channel.mention}, mention me with a question and I'll answer from the library, citing "
                   f"the passages: {bot.user.mention} *what does Plotinus say evil is?* Reply to my answer to ask "
                   "more.")


@bot.command(name="askcap", hidden=True)
@commands.is_owner()
async def ask_cap(ctx, n: str = ""):
    """(owner) How many questions the library answers a day, across all servers: !askcap 100"""
    usage = _usage()
    if n.isdigit():
        usage["cap"] = int(n)
        _save_usage(usage)
    await ctx.send(f"Answers today: {usage['count']} of {usage['cap']} allowed. Change with `!askcap <number>`.")
