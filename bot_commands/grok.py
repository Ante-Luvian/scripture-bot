"""A secret joke (the owner's, 2026-11-02): "grok is this true?" gets a reply drawn as a post on X from @grok, saying
yes, no, maybe or something sillier. People in the owner's server ask it of each other the way they do on X. Not
in !help, the introduction or the changelog, by design."""
import datetime
import io
import math
import random
import re
import time

import discord
from PIL import Image, ImageDraw, ImageFont

from core import bot

FONTS = "C:/Windows/Fonts/"
S = 2                                                   # drawn at twice the size, for sharp text

# "grok is this true", "@grok is that real?", "grok confirm": grok, and something asking whether it's so
TRIGGER = re.compile(r"(?is)(?=.*\bgrok\b)(?=.*\b(?:true|real|accurate|legit|correct|right|fake|confirm|cap|lying|facts?)\b)")
COOLDOWN = 10                                           # seconds, a channel
_last: dict = {}

# (answer, weight): mostly the plain three, with the odd joke
ANSWERS = [
    ("yes.", 10), ("no.", 10), ("maybe.", 6),
    ("yes, and it's worse than you think.", 2), ("absolutely not.", 3), ("unfortunately, yes.", 3),
    ("no, but it should be.", 2), ("it's complicated.", 2), ("I'd rather not say.", 2),
    ("ask again later.", 1), ("50/50.", 2), ("depends who's asking.", 2), ("source: trust me.", 1),
    ("lmao no.", 2), ("100% true.", 2), ("this is the truest thing ever posted.", 1),
    ("I've looked into it. No.", 1), ("partially true. mostly not.", 1), ("no comment.", 2),
    ("yes. next question.", 1), ("not even close.", 1), ("signs point to yes.", 1),
    ("my sources say no.", 1), ("technically yes.", 1), ("bro what", 1),
]

WHITE, GREY, LINE, BLACK = (231, 233, 234), (113, 118, 123), (47, 51, 54), (0, 0, 0)
GOLD = (229, 187, 51)


def _font(name: str, size: int):
    try:
        return ImageFont.truetype(FONTS + name, size * S)
    except OSError:
        return ImageFont.load_default()


def _avatar(size: int) -> Image.Image:
    """A ring with a slash through it, white on black, in a circle."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size - 1, size - 1), fill=BLACK)
    c, r, w = size / 2, size * 0.27, max(2, size // 12)
    d.arc((c - r, c - r, c + r, c + r), start=60, end=360, fill=WHITE, width=w)
    d.line((size * 0.22, size * 0.80, size * 0.80, size * 0.20), fill=WHITE, width=w)
    return im


def _badge(d: ImageDraw.ImageDraw, x: float, y: float, size: float) -> None:
    """The gold check: a scalloped seal, a tick in black."""
    c = (x + size / 2, y + size / 2)
    points = []
    for i in range(24):
        a = i * 3.14159 * 2 / 24
        rad = size / 2 * (1.0 if i % 2 == 0 else 0.86)
        points.append((c[0] + rad * math.cos(a), c[1] + rad * math.sin(a)))
    d.polygon(points, fill=GOLD)
    d.line([(x + size * 0.28, y + size * 0.52), (x + size * 0.44, y + size * 0.68), (x + size * 0.74, y + size * 0.34)],
           fill=BLACK, width=max(2, int(size / 8)), joint="curve")


def _affiliate(d: ImageDraw.ImageDraw, x: float, y: float, size: float) -> None:
    """The little square beside the name, an X in it."""
    d.rounded_rectangle((x, y, x + size, y + size), radius=size * 0.15, fill=BLACK, outline=WHITE, width=max(1, S))
    m = size * 0.3
    d.line((x + m, y + m, x + size - m, y + size - m), fill=WHITE, width=max(1, S))
    d.line((x + m, y + size - m, x + size - m, y + m), fill=WHITE, width=max(1, S))


def _wrap(d, text: str, font, width: float) -> list:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def stamp(now: datetime.datetime) -> str:
    """ "11:57 PM · Nov 1, 2026" (no leading zero on the hour or day, as X shows it)."""
    hour = now.hour % 12 or 12
    return f"{hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'} · {now:%b} {now.day}, {now.year}"


def render(answer: str, now: datetime.datetime = None) -> bytes:
    now = now or datetime.datetime.now()
    W, pad = 900 * S, 24 * S
    name_f, handle_f = _font("segoeuib.ttf", 21), _font("segoeui.ttf", 19)
    body_f, time_f = _font("segoeui.ttf", 23), _font("segoeui.ttf", 18)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = _wrap(probe, answer, body_f, W - 2 * pad)
    line_h = 32 * S
    body_top = 92 * S
    time_top = body_top + line_h * len(lines) + 18 * S
    H = time_top + 46 * S
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im)
    av = 56 * S
    im.paste(_avatar(av), (pad - 8 * S, 12 * S), _avatar(av))
    x = pad + av + 4 * S
    d.text((x, 10 * S), "Grok", font=name_f, fill=WHITE)
    bx = x + d.textlength("Grok", font=name_f) + 6 * S
    _badge(d, bx, 15 * S, 20 * S)
    _affiliate(d, bx + 26 * S, 16 * S, 17 * S)
    d.text((x, 38 * S), "@grok", font=handle_f, fill=GREY)
    # the logo and the dots at the top right
    corner = 28 * S
    small = _avatar(corner)
    im.paste(small, (W - pad - 70 * S, 12 * S), small)
    for i in range(3):
        cx, cy = W - pad - 14 * S + i * 7 * S, 26 * S
        d.ellipse((cx - 2 * S, cy - 2 * S, cx + 2 * S, cy + 2 * S), fill=GREY)
    for i, line in enumerate(lines):
        d.text((pad, body_top + i * line_h), line, font=body_f, fill=WHITE)
    d.text((pad, time_top), stamp(now), font=time_f, fill=GREY)
    d.line((pad, H - 4 * S, W - pad, H - 4 * S), fill=LINE, width=S)
    im = im.resize((W // S, H // S), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def pick() -> str:
    answers, weights = zip(*ANSWERS)
    return random.choices(answers, weights=weights)[0]


def asks_grok(content: str) -> bool:
    return bool(content) and not content.startswith("!") and len(content) < 300 and bool(TRIGGER.match(content))


@bot.listen("on_message")
async def grok_is_this_true(message: discord.Message):
    if message.author.bot or not asks_grok(message.content):
        return
    key = getattr(message.channel, "id", None)
    if time.monotonic() - _last.get(key, -1e9) < COOLDOWN:
        return
    _last[key] = time.monotonic()
    try:
        await message.reply(file=discord.File(io.BytesIO(render(pick())), filename="grok.png"), mention_author=False)
    except discord.HTTPException:
        pass
