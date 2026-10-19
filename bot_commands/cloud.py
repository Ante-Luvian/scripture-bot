"""
!cloud -- a book's most distinctive words, drawn as a word cloud.

A word's size is how much more the book uses it than the rest of its library
does (tf-idf against the other books of the same corpus: the KJV's 66 for a
Bible book, the Quran's 114 surahs for a surah...), so Ecclesiastes is
"vanity", "labour" and "sun", not "the" and "and".
"""
import functools
import io
import math
import re
import zlib
from collections import Counter

import discord

from core import tradition_enabled, bot, log, lookup

FONT = "C:/Windows/Fonts/GARABD.TTF"           # Garamond bold: an old book's face
BACKGROUND = (246, 239, 222)                    # parchment
COLOURS = [(88, 24, 31), (120, 60, 20), (36, 57, 94), (52, 82, 52), (98, 52, 102), (60, 52, 44)]
MAX_WORDS = 90

# too common to say anything about a book (with the KJV's own: thee, thou, hath, unto...)
STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each even every few for from further had has have having he
her here hers herself him himself his how i if in into is it its itself just let like made make many may me might
more most much must my myself no nor not now of off on once one only or other our ours ourselves out over own same
say said says shall she should so some such than that the their theirs them themselves then there these they this
those through thus to too under until up upon us very was we were what when where which while who whom whose why
will with would yet you your yours yourself yourselves also even every hath hast doth dost art thee thou thy thine
ye unto saith shalt wilt wouldest wouldst canst couldest neither nay yea behold lo therefore wherefore whereas
thereof therein thereby thereon thereto whosoever whatsoever went come came go goeth cometh things thing two three
four five six seven eight nine ten put take took give gave set day days one ones man men also art upon among
o oh ah unto toward towards against shall will may might must would could should
""".split())


def _words(text: str) -> list:
    text = re.sub(r"\*\*\[[\d:]+\]\*\*|<[^>]+>|\[[^\]]*\]", " ", text.lower())
    return [w.strip("'") for w in re.findall(r"[a-z][a-z']+", text)]


def _book_text(chapters: dict) -> str:
    parts = []
    for verses in chapters.values():
        if isinstance(verses, dict):
            parts.extend(v if isinstance(v, str) else " ".join(map(str, v.values())) for v in verses.values())
        elif isinstance(verses, str):
            parts.append(verses)
    return " ".join(parts)


@functools.lru_cache(maxsize=64)
def _corpus_frequencies(corpus: str) -> tuple:
    """(number of books, {word: books it appears in}) for a corpus."""
    books = lookup._data.get(corpus, {})
    df = Counter()
    for chapters in books.values():
        df.update(set(_words(_book_text(chapters))))
    return len(books), df


def distinctive_words(corpus: str, book: str) -> dict:
    """{word: weight} -- the book's tf-idf against its own corpus."""
    words = [w for w in _words(_book_text(lookup._data[corpus][book])) if len(w) > 2 and w not in STOPWORDS]
    counts = Counter(words)
    n_books, df = _corpus_frequencies(corpus)
    if n_books < 3:                                  # nothing to compare with: plain frequency
        return dict(counts.most_common(MAX_WORDS))
    scores = {w: c * math.log((1 + n_books) / (1 + df[w])) for w, c in counts.items() if c >= 2}
    best = sorted(scores.items(), key=lambda kv: -kv[1])[:MAX_WORDS]
    return {w: s for w, s in best if s > 0}


def render(weights: dict, title: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    from wordcloud import WordCloud

    def colour(word, font_size, position, orientation, random_state=None, **kwargs):
        return COLOURS[zlib.crc32(word.encode()) % len(COLOURS)]    # (the same colour every time)

    cloud = WordCloud(width=1200, height=620, background_color=BACKGROUND, font_path=FONT, prefer_horizontal=0.9,
                      max_words=MAX_WORDS, relative_scaling=0.5, margin=4, random_state=7, color_func=colour)
    image = cloud.generate_from_frequencies(weights).to_image()
    canvas = Image.new("RGB", (1200, 700), BACKGROUND)
    canvas.paste(image, (0, 70))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, 40)
    w = draw.textlength(title, font=font)
    draw.text(((1200 - w) / 2, 18), title, fill=COLOURS[0], font=font)
    draw.line([(80, 72), (1120, 72)], fill=(190, 170, 130), width=2)
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


@bot.command(name="cloud", aliases=["wordcloud"])
async def cmd_cloud(ctx, *, book: str = ""):
    """A book's most distinctive words as a word cloud.
    Usage: !cloud Ecclesiastes  |  !cloud Revelation  |  !cloud Tao Te Ching"""
    import asyncio
    if not book.strip():
        await ctx.send("Which book? For example: `!cloud Ecclesiastes`, `!cloud Revelation`, `!cloud Proverbs`.")
        return
    corpus, name = lookup._resolve_book(book.strip())
    from scripture_lookup import CORPUS_TRADITION
    if name and not tradition_enabled(getattr(getattr(ctx, "guild", None), "id", None), CORPUS_TRADITION.get(corpus)):
        corpus, name = None, None                       # (a tradition this server turned off)
    if name is None or name not in lookup._data.get(corpus, {}):
        await ctx.send(f"I don't know a book called **{discord.utils.escape_markdown(book.strip())}**. "
                       f"Try `!cloud Ecclesiastes` or `!books` to browse.")
        return
    async with ctx.typing():
        try:
            weights = await asyncio.to_thread(distinctive_words, corpus, name)
            if len(weights) < 5:
                await ctx.send(f"**{name}** is too short for a word cloud.")
                return
            png = await asyncio.to_thread(render, weights, name)
        except Exception:
            log.exception(f"!cloud failed for {name}")
            await ctx.send("⚠️ Something went wrong drawing that cloud.")
            return
    top = ", ".join(list(weights)[:5])
    embed = discord.Embed(title=f"☁️ {name}", color=discord.Color.from_rgb(120, 60, 20),
                          description=f"The words that set **{name}** apart from the other books "
                                      f"of its collection. The most distinctive: *{top}*.")
    embed.set_image(url="attachment://cloud.png")
    await ctx.send(embed=embed, file=discord.File(io.BytesIO(png), filename="cloud.png"))
