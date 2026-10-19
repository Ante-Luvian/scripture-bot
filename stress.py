"""
Stress testing: every command, fed what people actually type when they poke at a bot (typos,
nonsense, emoji, symbols, books that don't exist, absurd numbers, markdown and mentions, huge
input), and every reply checked for what shouldn't reach Discord: crashes, the "something went
wrong" apology, markup leaking through ([[ ]], {{ }}, HTML), unbalanced bold/italics/code,
"None"/"nan", unfilled {placeholders}, pings, and messages over Discord's limits.

The same sweep runs two ways:
  · python -m pytest -m stress   offline, against the commands that need no network
  · python stress.py [commands]  live: posts every input and reply to #bot-testing in the
                                 owner's server (only there), then a summary. Run it after
                                 deploying changes, naming the commands touched (or all).

Runtime state (bookmarks, plans, stats...) is redirected to a temporary folder in both, so a
sweep never writes into the live bot's files.
"""
import asyncio
import re
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEST_GUILD = "bot-testing"                  # the channel name; only the owner's server has it

# What people throw at any command that takes text.
HOSTILE = [
    "",                                      # nothing
    "   ",
    "asdfghjkl",                             # gibberish
    "xyzzy 3:16",                            # a book that doesn't exist
    "Jhon 3:16",                             # a typo
    "genisis 1",
    "🙏",                                    # emoji
    "🐍 3:16",
    "😀😀😀😀😀",
    "$", "%", "*", "_", "~", "{", ">", "|", "\\", "`", "[", "]", "(", ")", "#", "&",   # bare symbols
    "**bold** __under__ ~~strike~~ ||spoiler||",
    "`code` ```block```",
    "@everyone", "@here", "<@123456789012345678>", "<#123456789012345678>", "<@&123456789012345678>",
    "<script>alert(1)</script>",
    "'; DROP TABLE verses; --",
    "{book} {0} %s %d",
    "../../etc/passwd",
    "None", "null", "undefined", "NaN", "0", "-1", "1e309", "99999999999999999999999",
    "John 0:0", "John 999:999", "John 3:999", "John 3:16-1", "John 3:16-9999", "Genesis 1:1-50:26",
    "Psalm -5", "Revelation 22:22", "1 2 3", "3:16", ":", "::::", "John 3:16 xyzz", "John 3:16 kjv kjv kjv",
    "Ἐν ἀρχῇ ἦν ὁ λόγος", "בְּרֵאשִׁית", "في البدء", "太初有道",          # other scripts
    "Ｊｏｈｎ　３：１６",                                               # full-width
    "j" * 300,                                                          # long word
    "the " * 400,                                                       # very long input
    "​", "‮John 3:16",                                        # zero-width / right-to-left
    "John\n3:16",
]

# A representative dozen for the live run (each one is a message in #bot-testing; the offline
# run tries the whole list above)
LIVE_SAMPLE = ["", "asdfghjkl", "xyzzy 3:16", "Jhon 3:16", "🙏", "*", "`", "\\", "@everyone", "{book}",
               "John 999:999", "the " * 400]

# Commands that reach the internet (left to the live run), wait for an answer, or are owner-only.
NETWORK = {"salah", "notes", "compare", "parallel", "variants", "dafyomi", "parsha", "learning", "midi",
           "gematria", "today", "interlinear", "reverseinterlinear", "strong", "catena", "study"}
SKIP = {"weeklyreport", "scanstats", "guildactivity", "errors", "changelogintro", "checksources"}   # owner tools that DM/scan

# What a reply must not contain.
LEAKS = {
    "a wiki template": r"\{\{|\}\}",
    "wiki link brackets": r"\[\[|\]\]",
    "an HTML tag": r"</?(?:div|span|p|br|script|ref|sup|sub|table|tr|td|i|b|small|font)\b[^>]*>",
    "an HTML entity": r"&(?:lt|gt|amp|quot|nbsp|#\d+);",
    "an unfilled placeholder": r"(?<![\w{])\{[a-z_]+\}(?!\})",
    # (as a value -- "Source: None", a line of just "nan" -- not the English word "None")
    "a Python value": r"(?m)(?:^|[:=(]\s?)(?:None|nan|NaN|undefined)\s*(?:$|[),])|<built-in|object at 0x|Traceback",
    "a mass ping": r"(?<!`)@(?:everyone|here)",
}
APOLOGY = "something went wrong"


def problems_in(text: str, where: str, asked: str) -> list:
    out = []
    if not text:
        return out
    prose = re.sub(r"```.*?```|`[^`\n]*`", "", text, flags=re.S)          # (usage like `!verse <ref>` is fine)
    for name, pattern in LEAKS.items():
        m = re.search(pattern, prose)
        if m and not re.search(pattern, asked):                 # (unless it's echoing what was typed)
            out.append(f"{where}: {name} ({m.group(0)!r})")
    plain = re.sub(r"\\.", "", text)                                       # (escaped characters are plain)
    if plain.count("`") % 2 and "```" not in plain:
        out.append(f"{where}: unbalanced ` (code)")
    plain = re.sub(r"```.*?```|`[^`\n]*`", "", plain, flags=re.S)         # (code spans hold anything)
    if plain.count("**") % 2:
        out.append(f"{where}: unbalanced ** (bold)")
    if re.sub(r"\\.", "", text).count("```") % 2:
        out.append(f"{where}: unclosed code block")
    if APOLOGY in text.lower():
        out.append(f"{where}: the bot apologised for an error")
    return out


def check_reply(sent: dict, asked: str) -> list:
    """Problems in one send() call's arguments (content, embed(s), file(s))."""
    out = []
    content = sent.get("content")
    if content is not None:
        content = str(content)
        if len(content) > 2000:
            out.append(f"message is {len(content)} characters (Discord's limit is 2,000)")
        out += problems_in(content, "message", asked)
    embeds = list(sent.get("embeds") or []) + ([sent["embed"]] if sent.get("embed") else [])
    if len(embeds) > 10:
        out.append(f"{len(embeds)} embeds (limit 10)")
    total = 0
    for i, e in enumerate(embeds, 1):
        parts = [("title", e.title, 256), ("description", e.description, 4096),
                 ("footer", getattr(e.footer, "text", None), 2048), ("author", getattr(e.author, "name", None), 256)]
        parts += [(f"field {f.name!r} name", f.name, 256) for f in e.fields]
        parts += [(f"field {f.name!r}", f.value, 1024) for f in e.fields]
        if len(e.fields) > 25:
            out.append(f"embed {i}: {len(e.fields)} fields (limit 25)")
        for label, value, limit in parts:
            if value is None:
                continue
            value = str(value)
            total += len(value) if not label.endswith(" name") or True else 0
            if len(value) > limit:
                out.append(f"embed {i} {label}: {len(value)} characters (limit {limit})")
            if label.startswith("field") and not value.strip():
                out.append(f"embed {i} {label}: empty")
            out += problems_in(value, f"embed {i} {label}", asked)
    if total > 6000:
        out.append(f"embeds total {total} characters (limit 6,000)")
    return out


# ── driving a command without Discord ───────────────────────────────────────

class _Perms:
    def __getattr__(self, name):
        return False                                       # an ordinary member: no admin rights


def _fake_member(dm: "Recorder", uid=1):
    return types.SimpleNamespace(id=uid, bot=False, name="tester", display_name="tester", mention=f"<@{uid}>",
                                 guild_permissions=_Perms(), roles=[], avatar=None, display_avatar=None,
                                 send=dm.send, create_dm=dm._noop, global_name="tester")


class Recorder:
    """A channel stand-in: records what's sent; if `forward` is a real channel, posts it there too."""

    def __init__(self, forward=None):
        import discord
        self.sent, self.forward, self.id, self.name = [], forward, getattr(forward, "id", 1), TEST_GUILD
        self.guild = getattr(forward, "guild", None)
        self.type = discord.ChannelType.text
        self.mention = f"<#{self.id}>"

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})
        if self.forward is not None:
            kwargs.pop("view", None)                        # (buttons need the running bot to answer)
            kwargs["allowed_mentions"] = __import__("discord").AllowedMentions.none()
            try:
                return await self.forward.send(content, **kwargs)
            except Exception as e:
                self.sent[-1]["send_error"] = f"{type(e).__name__}: {e}"
        return types.SimpleNamespace(id=len(self.sent), edit=self._noop, add_reaction=self._noop,
                                     delete=self._noop, reply=self.send, jump_url="", channel=self)

    async def _noop(self, *a, **k):
        return None

    def typing(self):
        class _T:
            async def __aenter__(s): return s
            async def __aexit__(s, *e): return False
        return _T()

    def permissions_for(self, *_):
        return _Perms()


def isolate_runtime_files() -> None:
    """Point every runtime-state file at a temporary folder (as tests/conftest.py does)."""
    sys.path.insert(0, str(ROOT / "tests"))
    from conftest import RUNTIME_FILES
    tmp = Path(tempfile.mkdtemp(prefix="stress_"))
    for name, module in list(sys.modules.items()):
        if name in ("core", "bot") or name.startswith("bot_commands."):
            for attr in RUNTIME_FILES:
                if hasattr(module, attr):
                    setattr(module, attr, tmp / attr.lower().replace("_path", ".json"))
            if hasattr(module, "BACKUP_DIR"):
                module.BACKUP_DIR = tmp / "backups"


def _context_class():
    from core import ScriptureContext, apologetic, fit_for_discord

    class StressContext(ScriptureContext):
        """The bot's own context, its replies going to the Recorder instead of Discord."""

        async def send(self, content=None, **kwargs):
            content = fit_for_discord(content, kwargs)
            return await self.message.channel.send(apologetic(self.guild, content), **kwargs)

        async def reply(self, content=None, **kwargs):
            return await self.send(content, **kwargs)

        def typing(self, *a, **k):
            return self.message.channel.typing()

    return StressContext


async def run(command: str, arg: str, channel: Recorder, timeout: float = 30) -> list:
    """Run `!command arg` through the bot's own command machinery; the problems found (empty if fine)."""
    from discord.ext import commands
    from core import _recent_commands, bot, clean_input
    _recent_commands.clear()           # (the per-person speed limit would turn away all but the first ten inputs)
    text = clean_input(f"!{command} {arg}".rstrip() if arg.strip() else f"!{command}")
    member = _fake_member(channel)
    message = types.SimpleNamespace(content=text, author=member, channel=channel, guild=channel.guild, id=1,
                                    attachments=[], mentions=[], role_mentions=[], channel_mentions=[],
                                    reference=None, jump_url="", created_at=None, webhook_id=None,
                                    _state=bot._connection,
                                    add_reaction=channel._noop, reply=channel.send, delete=channel._noop)
    ctx = _context_class()(prefix="!", view=commands.view.StringView(text), bot=bot, message=message)
    ctx.view.skip_string("!")
    ctx.invoked_with = ctx.view.get_word()
    ctx.command = bot.all_commands.get(ctx.invoked_with)
    if ctx.command is None:
        return [f"no command !{command}"]
    before = len(channel.sent)
    found = []
    from core import RateLimited
    try:
        await asyncio.wait_for(ctx.command.invoke(ctx), timeout)
    except RateLimited:
        found.append("turned away by the speed limit, so never tried")   # (a pass that tested nothing)
    except (commands.UserInputError, commands.CheckFailure):
        pass                                                 # the bot answers these politely itself
    except asyncio.TimeoutError:
        found.append(f"no answer within {timeout:.0f}s")
    except Exception as e:
        err = getattr(e, "original", e)
        found.append(f"crashed: {type(err).__name__}: {str(err)[:200]}")
    for s in channel.sent[before:]:
        found += check_reply(s, arg)
        if s.get("send_error"):
            found.append(f"Discord refused the reply: {s['send_error'][:200]}")
    return found


def text_commands(names=None) -> list:
    from core import bot
    out = []
    for c in sorted(bot.commands, key=lambda c: c.name):
        if names and c.name not in names:
            continue
        if c.name in SKIP:
            continue
        out.append(c)
    return out


def sample(command, live: bool = False) -> list:
    """The inputs to try on a command: the hostile set for commands taking text, or just a few."""
    takes_text = any(p.kind.name == "KEYWORD_ONLY" for p in command.clean_params.values())
    takes_any = bool(command.clean_params)
    if not takes_any:
        return ["", "asdfghjkl", "🙏"]
    if takes_text:
        return LIVE_SAMPLE if live else HOSTILE
    return ["", "asdfghjkl", "🙏", "-1", "99999999999999999999999", "@everyone", "{book}", "John 3:16"]


# ── the live run ────────────────────────────────────────────────────────────

async def live(names=None) -> None:
    import os
    import discord
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    import bot as _bot                                       # registers every command module
    from core import bot
    isolate_runtime_files()
    bot.wait_for = _no_answer
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        target = next((c for g in client.guilds for c in g.text_channels if c.name == TEST_GUILD), None)
        if target is None:
            print(f"no #{TEST_GUILD} channel"); await client.close(); return
        cmds = text_commands(set(names) if names else None)
        total = sum(len(sample(c, live=True)) for c in cmds)
        await target.send(f"🧪 **Stress test:** {len(cmds)} command(s), {total} inputs.")
        report = []
        for c in cmds:
            for arg in sample(c, live=True):
                rec = Recorder(target)
                await rec.send(f"`!{c.name} {arg[:150]}`" if arg.strip() else f"`!{c.name}` (nothing)")
                found = await run(c.name, arg, rec)
                if found:
                    report.append((c.name, arg, found))
                    print(f"!{c.name} {arg[:40]!r}: {found}", flush=True)
                await asyncio.sleep(1.0)
        summary = (f"✅ **Stress test done:** no problems in {total} inputs." if not report else
                   f"⚠️ **Stress test done:** {len(report)} of {total} inputs had problems:\n" +
                   "\n".join(f"• `!{n} {a[:40]}` — {'; '.join(f)[:180]}" for n, a, f in report[:25]))
        await target.send(summary[:1990], allowed_mentions=discord.AllowedMentions.none())
        print(summary)
        await client.close()

    await client.start(os.environ["DISCORD_TOKEN"])


async def _no_answer(*args, timeout=None, **kwargs):
    raise asyncio.TimeoutError                              # (a game waiting for a reply gets none)


if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)
    asyncio.run(live(sys.argv[1:] or None))
