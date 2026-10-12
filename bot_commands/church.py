"""
!catena, !ccc / !canon, !creed, !summa.
"""
import discord
import re
from discord import app_commands
from summa_lookup import get_summa, get_summa_random, parse_summa_ref
from core import (
    _chunk,
    _scrape_votd,
    bot,
    lookup,
    record_special_stat,
)
from core import ROOT

# ── !catena — Patristic commentary from catenabible.com ──────────────────────

# Book name → catenabible.com URL abbreviation
_CATENA_BOOKS = {
    # OT
    "genesis": "gn", "gen": "gn",
    "exodus": "ex", "exod": "ex",
    "leviticus": "lv", "lev": "lv",
    "numbers": "nm", "num": "nm",
    "deuteronomy": "dt", "deut": "dt",
    "joshua": "jo", "josh": "jo",
    "judges": "jg", "judg": "jg",
    "ruth": "rt",
    "1 samuel": "1sm", "1sam": "1sm",
    "2 samuel": "2sm", "2sam": "2sm",
    "1 kings": "1kgs", "1kgs": "1kgs",
    "2 kings": "2kgs", "2kgs": "2kgs",
    "1 chronicles": "1chr", "1chr": "1chr",
    "2 chronicles": "2chr", "2chr": "2chr",
    "ezra": "ezr",
    "nehemiah": "ne", "neh": "ne",
    "tobit": "tb", "tob": "tb",
    "judith": "jdt",
    "esther": "est",
    "1 maccabees": "1mc", "1macc": "1mc",
    "2 maccabees": "2mc", "2macc": "2mc",
    "job": "jb",
    "psalms": "ps", "psalm": "ps",
    "proverbs": "prv", "prov": "prv",
    "ecclesiastes": "eccl", "qoheleth": "eccl",
    "song of songs": "sg", "song of solomon": "sg", "song": "sg",
    "wisdom": "wis", "wisdom of solomon": "wis",
    "sirach": "si", "ecclesiasticus": "si",
    "isaiah": "is", "isa": "is",
    "jeremiah": "jer",
    "lamentations": "lam",
    "baruch": "bar",
    "ezekiel": "ez", "ezek": "ez",
    "daniel": "dn", "dan": "dn",
    "hosea": "hos",
    "joel": "jl",
    "amos": "am",
    "obadiah": "ob",
    "jonah": "jon",
    "micah": "mi",
    "nahum": "na",
    "habakkuk": "hb", "hab": "hb",
    "zephaniah": "zep",
    "haggai": "hg",
    "zechariah": "zec",
    "malachi": "mal",
    # NT
    "matthew": "mt", "matt": "mt",
    "mark": "mk",
    "luke": "lk",
    "john": "jn",
    "acts": "ac", "acts of the apostles": "ac",
    "romans": "rom",
    "1 corinthians": "1cor", "1cor": "1cor",
    "2 corinthians": "2cor", "2cor": "2cor",
    "galatians": "gal",
    "ephesians": "eph",
    "philippians": "phil",
    "colossians": "col",
    "1 thessalonians": "1thes", "1thess": "1thes",
    "2 thessalonians": "2thes", "2thess": "2thes",
    "1 timothy": "1tm", "1tim": "1tm",
    "2 timothy": "2tm", "2tim": "2tm",
    "titus": "ti",
    "philemon": "phm",
    "hebrews": "heb",
    "james": "jas",
    "1 peter": "1pt", "1pet": "1pt",
    "2 peter": "2pt", "2pet": "2pt",
    "1 john": "1jn",
    "2 john": "2jn",
    "3 john": "3jn",
    "jude": "jude",
    "revelation": "rv", "rev": "rv", "apocalypse": "rv",
}

def _catena_book_abbr(book_raw: str) -> str | None:
    """Return the catenabible.com URL abbreviation for a book name."""
    key = book_raw.strip().lower()
    if key in _CATENA_BOOKS:
        return _CATENA_BOOKS[key]
    # Try stripping leading digit+space for numbered books
    for k, v in _CATENA_BOOKS.items():
        if key == k:
            return v
    return None


def _fetch_catena_sections(reference: str) -> dict:
    """
    Pure helper: fetch and parse catenabible.com commentary for a verse.

    Returns a dict with one of:
      {"error_send": "...user-friendly error message..."}   on failure
      {"sections": [(name, body), ...], "url": str,
       "book_raw": str, "chapter": str, "verse": str}       on success
    """
    import urllib.request
    import urllib.error
    import html as html_mod

    # Strip verse range if user passed one (e.g. "John 3:16-18" → "John 3:16")
    reference = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", reference.strip())

    # Parse "Book Chapter:Verse"
    m = re.match(
        r"^((?:\d\s*)?[A-Za-z][a-zA-Z\s]+?)\s+(\d+):(\d+)$",
        reference.strip()
    )
    if not m:
        return {"error_send": f"⚠️ Couldn't parse `{reference}`. Try: `!catena John 3:16`"}

    book_raw, chapter, verse = m.group(1).strip(), m.group(2), m.group(3)
    abbr = _catena_book_abbr(book_raw)
    if abbr is None:
        return {"error_send": f"⚠️ Book `{book_raw}` not found on catenabible.com."}

    url = f"https://catenabible.com/{abbr}/{chapter}/{verse}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return {"error_send": f"⚠️ catenabible.com returned HTTP {e.code} for `{reference}`.\nVisit: <{url}>"}
    except Exception as e:
        return {"error_send": f"⚠️ Could not reach catenabible.com: {e}"}

    # ── Parse commentary sections ─────────────────────────────────────────────
    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Trim the page footer (recurring nav links) BEFORE other cutoffs,
    # since these appear at the very end of the page and would otherwise leak
    # into the last commentary's body. Markers must be specific enough not to
    # match words that legitimately appear inside commentary text.
    for footer_cut in [
        "About Privacy Policy Donate",
        "About\nPrivacy Policy\nDonate",
    ]:
        idx = text.find(footer_cut)
        if idx != -1:
            text = text[:idx].strip()

    for cutoff in ["All Commentaries on", "Knowing this first", "Go To "]:
        idx = text.find(cutoff)
        if idx != -1:
            text = text[:idx].strip()

    # Start at first "Name AD YYYY" — skips the nav dump
    ad_match = re.search(r"\b[A-Z][a-zA-Z ]+AD \d{3,4}", text)
    if ad_match:
        text = text[ad_match.start():]

    text = re.sub(r"chevron-(?:left|right)", "", text)
    text = re.sub(r"Verse \d+\s+Read Chapter \d+\s+Verse \d+", "", text)
    text = re.sub(r"\d+ min\s+\d+ / \d+\s+Go to Commentary", "", text)
    text = re.sub(r"Read Chapter \d+", "", text)

    entries = re.split(r"\n*([A-Z][a-zA-Z ]+AD \d{3,4})\n*", text)
    sections = []
    i = 1
    while i < len(entries) - 1:
        name = entries[i].strip()
        body = re.sub(r"\s*\d+ min\s*\d* ?/? ?\d*\s*Go to Commentary\s*", "", entries[i + 1]).strip()
        if body and len(body) > 20:
            sections.append((name, body))
        i += 2

    return {
        "sections": sections,
        "url": url,
        "book_raw": book_raw,
        "chapter": chapter,
        "verse": verse,
    }


@bot.command(name="catena")
async def cmd_catena(ctx, *, reference: str = ""):
    """Fetch patristic commentary from catenabible.com. Usage: !catena John 3:16"""
    # If no reference given, use today's Verse of the Day reference
    if not reference:
        ref_raw, _ = _scrape_votd()
        if ref_raw is None:
            await ctx.send("⚠️ Could not fetch today's verse reference. Try: `!catena John 3:16`")
            return
        reference = re.sub(r"\s*[-–]\s*\d+$", "", ref_raw.strip())

    async with ctx.typing():
        result = _fetch_catena_sections(reference)

    if result.get("error_send"):
        await ctx.send(result["error_send"])
        return

    sections = result["sections"]
    url = result["url"]
    book_raw = result["book_raw"]
    chapter = result["chapter"]
    verse = result["verse"]

    if not sections:
        await ctx.send(f"⚠️ No commentary found for **{book_raw} {chapter}:{verse}**.\nVisit: <{url}>")
        return

    # ── Get KJV verse text ────────────────────────────────────────────────────
    ref_label = f"{book_raw.title()} {chapter}:{verse}"
    kjv_result = lookup.get_verse(f"{book_raw} {chapter}:{verse}")
    kjv_text = f"*{kjv_result['text']}*\n\n" if kjv_result.get("found") else ""

    # ── Build paginated view ──────────────────────────────────────────────────
    def make_embed(idx: int) -> discord.Embed:
        name, body = sections[idx]
        # Truncate body at sentence boundary if very long
        if len(body) > 3200 - len(kjv_text):
            limit = 3200 - len(kjv_text)
            trunc = body[:limit]
            last_period = trunc.rfind(". ")
            body = (trunc[:last_period + 1] if last_period > 200 else trunc) + " …"

        embed = discord.Embed(
            title=f"📜 {ref_label} — {name}",
            description=kjv_text + body,
            color=discord.Color.dark_gold(),
            url=url
        )
        embed.set_footer(text=f"Commentary {idx + 1} of {len(sections)} — catenabible.com")
        return embed

    class CatenaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(sections)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(sections)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            # Remove buttons when the view expires
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = CatenaView()
    msg = await ctx.send(embed=make_embed(0), view=view)
    view.message = msg


# ── Startup ────────────────────────────────────────────────────────────────────

# ── !ccc / !canon — Catechism and Canon Law ───────────────────────────────────

_CCC_DATA   = None
_CANON_DATA = None

def _load_ccc():
    global _CCC_DATA
    if _CCC_DATA is None:
        import json
        path = ROOT / "data" / "catechism.json"
        if path.exists():
            entries = json.loads(path.read_text(encoding="utf-8"))
            _CCC_DATA = {e["id"]: e["text"].strip() for e in entries}
    return _CCC_DATA

def _load_canon():
    global _CANON_DATA
    if _CANON_DATA is None:
        import json
        path = ROOT / "data" / "canon.json"
        if path.exists():
            entries = json.loads(path.read_text(encoding="utf-8"))
            _CANON_DATA = {}
            for e in entries:
                if "text" in e:
                    _CANON_DATA[e["id"]] = e["text"].strip()
                elif "sections" in e:
                    # Join numbered sub-sections
                    parts = []
                    for s in e["sections"]:
                        parts.append(f"§{s['id']}. {s['text'].strip()}")
                    _CANON_DATA[e["id"]] = "\n\n".join(parts)
    return _CANON_DATA

@bot.command(name="ccc")
async def cmd_ccc(ctx, *, args: str = ""):
    """Look up a paragraph of the Catechism of the Catholic Church. Usage: !ccc 1"""
    try:
        number = int(args.strip())
    except ValueError:
        await ctx.send("Usage: `!ccc <paragraph number>` (1–2865)")
        return
    if number <= 0:
        await ctx.send("Usage: `!ccc <paragraph number>` (1–2865)")
        return
    data = _load_ccc()
    if data is None:
        await ctx.send("⚠️ catechism.json not found in data folder.")
        return
    text = data.get(number)
    if text is None:
        await ctx.send(f"⚠️ Paragraph {number} not found. Valid range: 1–{max(data.keys())}.")
        return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000:
        text = text[:3997] + "…"
    embed = discord.Embed(
        title=f"CCC {number}",
        description=text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Catechism of the Catholic Church")
    record_special_stat(ctx.author.id, "ccc", f"CCC {number}")
    await ctx.send(embed=embed)


@bot.command(name="canon")
async def cmd_canon(ctx, *, args: str = ""):
    """Look up a canon of the Code of Canon Law. Usage: !canon 1"""
    try:
        number = int(args.strip())
    except ValueError:
        await ctx.send("Usage: `!canon <canon number>` (1–1751)")
        return
    if number <= 0:
        await ctx.send("Usage: `!canon <canon number>` (1–1751)")
        return
    data = _load_canon()
    if data is None:
        await ctx.send("⚠️ canon.json not found in data folder.")
        return
    text = data.get(number)
    if text is None:
        await ctx.send(f"⚠️ Canon {number} not found. Valid range: 1–{max(data.keys())}.")
        return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000:
        text = text[:3997] + "…"
    embed = discord.Embed(
        title=f"Canon {number}",
        description=text,
        color=discord.Color.dark_red()
    )
    embed.set_footer(text="Code of Canon Law (1983)")
    record_special_stat(ctx.author.id, "canon", f"Canon {number}")
    await ctx.send(embed=embed)


# ── !creed — The three ecumenical creeds, traditional (1662 BCP) English ────────

CREEDS = {
    "apostles": {
        "title": "The Apostles' Creed",
        "text": (
            "I believe in God the Father Almighty, Maker of heaven and earth:\n\n"
            "And in Jesus Christ his only Son our Lord, Who was conceived by the Holy Ghost, "
            "Born of the Virgin Mary, Suffered under Pontius Pilate, Was crucified, dead, and buried, "
            "He descended into hell; The third day he rose again from the dead, He ascended into heaven, "
            "And sitteth on the right hand of God the Father Almighty; From thence he shall come to judge "
            "the quick and the dead.\n\n"
            "I believe in the Holy Ghost; The holy Catholick Church; The Communion of Saints; "
            "The Forgiveness of sins; The Resurrection of the body, And the life everlasting. Amen."
        ),
        "latin_title": "Symbolum Apostolorum",
        "latin": (
            "Credo in Deum Patrem omnipotentem, Creatorem caeli et terrae.\n\n"
            "Et in Iesum Christum, Filium eius unicum, Dominum nostrum, qui conceptus est de Spiritu Sancto, "
            "natus ex Maria Virgine, passus sub Pontio Pilato, crucifixus, mortuus, et sepultus, "
            "descendit ad inferos, tertia die resurrexit a mortuis, ascendit ad caelos, "
            "sedet ad dexteram Dei Patris omnipotentis, inde venturus est iudicare vivos et mortuos.\n\n"
            "Credo in Spiritum Sanctum, sanctam Ecclesiam catholicam, sanctorum communionem, "
            "remissionem peccatorum, carnis resurrectionem, vitam aeternam. Amen."
        ),
    },
    "nicene": {
        "title": "The Nicene Creed",
        "text": (
            "I believe in one God the Father Almighty, Maker of heaven and earth, And of all things "
            "visible and invisible:\n\n"
            "And in one Lord Jesus Christ, the only-begotten Son of God, Begotten of his Father before "
            "all worlds, God of God, Light of Light, Very God of very God, Begotten, not made, "
            "Being of one substance with the Father, By whom all things were made; Who for us men, "
            "and for our salvation, came down from heaven, And was incarnate by the Holy Ghost of the "
            "Virgin Mary, And was made man, And was crucified also for us under Pontius Pilate; "
            "He suffered and was buried, And the third day he rose again according to the Scriptures, "
            "And ascended into heaven, And sitteth on the right hand of the Father; And he shall come "
            "again with glory to judge both the quick and the dead: Whose kingdom shall have no end.\n\n"
            "And I believe in the Holy Ghost, The Lord and Giver of Life, Who proceedeth from the Father "
            "and the Son, Who with the Father and the Son together is worshipped and glorified, "
            "Who spake by the Prophets. And I believe one Catholick and Apostolick Church. "
            "I acknowledge one Baptism for the remission of sins. And I look for the Resurrection of "
            "the dead, And the life of the world to come. Amen."
        ),
        "latin_title": "Symbolum Nicaenum-Constantinopolitanum",
        "latin": (
            "Credo in unum Deum, Patrem omnipotentem, factorem caeli et terrae, "
            "visibilium omnium et invisibilium.\n\n"
            "Et in unum Dominum Iesum Christum, Filium Dei unigenitum, et ex Patre natum ante omnia saecula. "
            "Deum de Deo, lumen de lumine, Deum verum de Deo vero, genitum, non factum, consubstantialem "
            "Patri: per quem omnia facta sunt. Qui propter nos homines et propter nostram salutem descendit "
            "de caelis. Et incarnatus est de Spiritu Sancto ex Maria Virgine, et homo factus est. "
            "Crucifixus etiam pro nobis sub Pontio Pilato, passus et sepultus est, et resurrexit tertia die, "
            "secundum Scripturas, et ascendit in caelum, sedet ad dexteram Patris. Et iterum venturus est "
            "cum gloria, iudicare vivos et mortuos, cuius regni non erit finis.\n\n"
            "Et in Spiritum Sanctum, Dominum et vivificantem, qui ex Patre Filioque procedit. Qui cum Patre "
            "et Filio simul adoratur et conglorificatur: qui locutus est per prophetas. Et unam, sanctam, "
            "catholicam et apostolicam Ecclesiam. Confiteor unum baptisma in remissionem peccatorum. "
            "Et exspecto resurrectionem mortuorum, et vitam venturi saeculi. Amen."
        ),
        "greek_title": "Σύμβολον τῆς Νικαίας-Κωνσταντινουπόλεως",
        "greek": (
            "Πιστεύω εἰς ἕνα Θεόν, Πατέρα, Παντοκράτορα, ποιητὴν οὐρανοῦ καὶ γῆς, "
            "ὁρατῶν τε πάντων καὶ ἀοράτων.\n\n"
            "Καὶ εἰς ἕνα Κύριον Ἰησοῦν Χριστόν, τὸν Υἱὸν τοῦ Θεοῦ τὸν μονογενῆ, τὸν ἐκ τοῦ Πατρὸς "
            "γεννηθέντα πρὸ πάντων τῶν αἰώνων· φῶς ἐκ φωτός, Θεὸν ἀληθινὸν ἐκ Θεοῦ ἀληθινοῦ, γεννηθέντα "
            "οὐ ποιηθέντα, ὁμοούσιον τῷ Πατρί, δι' οὗ τὰ πάντα ἐγένετο. Τὸν δι' ἡμᾶς τοὺς ἀνθρώπους καὶ "
            "διὰ τὴν ἡμετέραν σωτηρίαν κατελθόντα ἐκ τῶν οὐρανῶν καὶ σαρκωθέντα ἐκ Πνεύματος Ἁγίου καὶ "
            "Μαρίας τῆς Παρθένου καὶ ἐνανθρωπήσαντα. Σταυρωθέντα τε ὑπὲρ ἡμῶν ἐπὶ Ποντίου Πιλάτου, καὶ "
            "παθόντα καὶ ταφέντα. Καὶ ἀναστάντα τῇ τρίτῃ ἡμέρᾳ κατὰ τὰς Γραφάς. Καὶ ἀνελθόντα εἰς τοὺς "
            "οὐρανοὺς καὶ καθεζόμενον ἐκ δεξιῶν τοῦ Πατρός. Καὶ πάλιν ἐρχόμενον μετὰ δόξης κρῖναι ζῶντας "
            "καὶ νεκρούς, οὗ τῆς βασιλείας οὐκ ἔσται τέλος.\n\n"
            "Καὶ εἰς τὸ Πνεῦμα τὸ Ἅγιον, τὸ κύριον, τὸ ζῳοποιόν, τὸ ἐκ τοῦ Πατρὸς ἐκπορευόμενον, τὸ σὺν "
            "Πατρὶ καὶ Υἱῷ συμπροσκυνούμενον καὶ συνδοξαζόμενον, τὸ λαλῆσαν διὰ τῶν προφητῶν. Εἰς μίαν, "
            "Ἁγίαν, Καθολικὴν καὶ Ἀποστολικὴν Ἐκκλησίαν. Ὁμολογῶ ἓν βάπτισμα εἰς ἄφεσιν ἁμαρτιῶν. "
            "Προσδοκῶ ἀνάστασιν νεκρῶν. Καὶ ζωὴν τοῦ μέλλοντος αἰῶνος. Ἀμήν."
        ),
    },
    "athanasian": {
        "title": "The Athanasian Creed (Quicunque Vult)",
        "text": (
            "Whosoever will be saved: before all things it is necessary that he hold the Catholick Faith.\n"
            "Which Faith except every one do keep whole and undefiled: without doubt he shall perish everlastingly.\n\n"
            "And the Catholick Faith is this: That we worship one God in Trinity, and Trinity in Unity;\n"
            "Neither confounding the Persons: nor dividing the Substance.\n"
            "For there is one Person of the Father, another of the Son: and another of the Holy Ghost.\n"
            "But the Godhead of the Father, of the Son, and of the Holy Ghost, is all one: the Glory equal, "
            "the Majesty co-eternal.\n"
            "Such as the Father is, such is the Son: and such is the Holy Ghost.\n"
            "The Father uncreate, the Son uncreate: and the Holy Ghost uncreate.\n"
            "The Father incomprehensible, the Son incomprehensible: and the Holy Ghost incomprehensible.\n"
            "The Father eternal, the Son eternal: and the Holy Ghost eternal.\n"
            "And yet they are not three eternals: but one eternal.\n"
            "As also there are not three incomprehensibles, nor three uncreated: but one uncreated, "
            "and one incomprehensible.\n"
            "So likewise the Father is Almighty, the Son Almighty: and the Holy Ghost Almighty.\n"
            "And yet they are not three Almighties: but one Almighty.\n"
            "So the Father is God, the Son is God: and the Holy Ghost is God.\n"
            "And yet they are not three Gods: but one God.\n"
            "So likewise the Father is Lord, the Son Lord: and the Holy Ghost Lord.\n"
            "And yet not three Lords: but one Lord.\n"
            "For like as we are compelled by the Christian verity: to acknowledge every Person by himself "
            "to be God and Lord;\n"
            "So are we forbidden by the Catholick Religion: to say, There be three Gods, or three Lords.\n"
            "The Father is made of none: neither created, nor begotten.\n"
            "The Son is of the Father alone: not made, nor created, but begotten.\n"
            "The Holy Ghost is of the Father and of the Son: neither made, nor created, nor begotten, "
            "but proceeding.\n"
            "So there is one Father, not three Fathers; one Son, not three Sons: one Holy Ghost, "
            "not three Holy Ghosts.\n"
            "And in this Trinity none is afore, or after other: none is greater, or less than another;\n"
            "But the whole three Persons are co-eternal together: and co-equal.\n"
            "So that in all things, as is aforesaid: the Unity in Trinity, and the Trinity in Unity, "
            "is to be worshipped.\n"
            "He therefore that will be saved: must thus think of the Trinity.\n\n"
            "Furthermore, it is necessary to everlasting salvation: that he also believe rightly the "
            "Incarnation of our Lord Jesus Christ.\n"
            "For the right Faith is, that we believe and confess: that our Lord Jesus Christ, the Son "
            "of God, is God and Man;\n"
            "God, of the Substance of the Father, begotten before the worlds: and Man, of the Substance "
            "of his Mother, born in the world;\n"
            "Perfect God, and perfect Man: of a reasonable soul and human flesh subsisting;\n"
            "Equal to the Father, as touching his Godhead: and inferior to the Father, as touching his "
            "Manhood;\n"
            "Who although he be God and Man: yet he is not two, but one Christ;\n"
            "One; not by conversion of the Godhead into flesh: but by taking of the Manhood into God;\n"
            "One altogether; not by confusion of Substance: but by unity of Person.\n"
            "For as the reasonable soul and flesh is one man: so God and Man is one Christ;\n"
            "Who suffered for our salvation: descended into hell, rose again the third day from the dead;\n"
            "He ascended into heaven, he sitteth on the right hand of the Father, God Almighty: "
            "from whence he shall come to judge the quick and the dead.\n"
            "At whose coming all men shall rise again with their bodies: and shall give account for "
            "their own works.\n"
            "And they that have done good shall go into life everlasting: and they that have done evil "
            "into everlasting fire.\n\n"
            "This is the Catholick Faith: which except a man believe faithfully, he cannot be saved."
        ),
        "latin_title": "Quicunque Vult",
        "latin": (
            "Quicumque vult salvus esse, ante omnia opus est, ut teneat Catholicam fidem: Quam nisi quisque "
            "integram inviolatamque servaverit, absque dubio in aeternum peribit. Fides autem Catholica "
            "haec est: ut unum Deum in Trinitate, et Trinitatem in unitate veneremur. Neque confundentes "
            "personas, neque substantiam separantes. Alia est enim persona Patris alia Filii, alia Spiritus "
            "Sancti: Sed Patris, et Filii, et Spiritus Sancti una est divinitas, aequalis gloria, coeterna "
            "maiestas. Qualis Pater, talis Filius, talis [et] Spiritus Sanctus. Increatus Pater, increatus "
            "Filius, increatus [et] Spiritus Sanctus. Immensus Pater, immensus Filius, immensus [et] "
            "Spiritus Sanctus. Aeternus Pater, aeternus Filius, aeternus [et] Spiritus Sanctus. Et tamen "
            "non tres aeterni, sed unus aeternus. Sicut non tres increati, nec tres immensi, sed unus "
            "increatus, et unus immensus. Similiter omnipotens Pater, omnipotens Filius, omnipotens [et] "
            "Spiritus Sanctus. Et tamen non tres omnipotentes, sed unus omnipotens. Ita Deus Pater, Deus "
            "Filius, Deus [et] Spiritus Sanctus. Et tamen non tres dii, sed unus est Deus. Ita Dominus "
            "Pater, Dominus Filius, Dominus [et] Spiritus Sanctus. Et tamen non tres Domini, sed unus "
            "[est] Dominus. Quia, sicut singillatim unamquamque personam Deum ac Dominum confiteri "
            "christiana veritate compellimur: Ita tres Deos aut [tres] Dominos dicere Catholica religione "
            "prohibemur. Pater a nullo est factus: nec creatus, nec genitus. Filius a Patre solo est: non "
            "factus, nec creatus, sed genitus. Spiritus Sanctus a Patre et Filio: non factus, nec creatus, "
            "nec genitus, sed procedens. Unus ergo Pater, non tres Patres: unus Filius, non tres Filii: "
            "unus Spiritus Sanctus, non tres Spiritus Sancti. Et in hac Trinitate nihil prius aut "
            "posterius, nihil maius aut minus: Sed totae tres personae coaeternae sibi sunt et coaequales. "
            "Ita, ut per omnia, sicut iam supra dictum est, et unitas in Trinitate, et Trinitas in unitate "
            "veneranda sit. Qui vult ergo salvus esse, ita de Trinitate sentiat.\n\n"
            "Sed necessarium est ad aeternam salutem, ut incarnationem quoque Domini nostri Iesu Christi "
            "fideliter credat. Est ergo fides recta ut credamus et confiteamur, quia Dominus noster Iesus "
            "Christus, Dei Filius, Deus [pariter] et homo est. Deus [est] ex substantia Patris ante saecula "
            "genitus: et homo est ex substantia matris in saeculo natus. Perfectus Deus, perfectus homo: "
            "ex anima rationali et humana carne subsistens. Aequalis Patri secundum divinitatem: minor "
            "Patre secundum humanitatem. Qui licet Deus sit et homo, non duo tamen, sed unus est Christus. "
            "Unus autem non conversione divinitatis in carnem, sed assumptione humanitatis in Deum. Unus "
            "omnino, non confusione substantiae, sed unitate personae. Nam sicut anima rationalis et caro "
            "unus est homo: ita Deus et homo unus est Christus. Qui passus est pro salute nostra: "
            "descendit ad inferos: tertia die resurrexit a mortuis. Ascendit ad [in] caelos, sedet ad "
            "dexteram [Dei] Patris [omnipotentis]. Inde venturus [est] judicare vivos et mortuos. Ad cujus "
            "adventum omnes homines resurgere habent cum corporibus suis; Et reddituri sunt de factis "
            "propriis rationem. Et qui bona egerunt, ibunt in vitam aeternam: qui vero mala, in ignem "
            "aeternum. Haec est fides Catholica, quam nisi quisque fideliter firmiterque crediderit, "
            "salvus esse non poterit."
        ),
    },
}
CREED_ALIASES = {
    "apostle": "apostles", "apostles": "apostles", "apostles'": "apostles",
    "nicene": "nicene", "nicaea": "nicene", "nicea": "nicene",
    "athanasius": "athanasian", "athanasian": "athanasian", "quicunque": "athanasian", "quicunquevult": "athanasian",
}

CREED_LANGS = {
    "latin": "latin", "la": "latin", "lat": "latin",
    "greek": "greek", "gr": "greek", "el": "greek", "grc": "greek",
    "parallel": "parallel", "both": "parallel", "all": "parallel",
}

async def _send_creed(ctx, key: str, lang: str = "text"):
    creed = CREEDS[key]

    if lang == "parallel":
        for l in ("text", "greek", "latin"):
            if l == "text" or creed.get(l):
                await _send_creed(ctx, key, l)
        return

    if lang == "greek":
        if not creed.get("greek"):
            await ctx.send(f"No Greek text available for **{creed['title']}**.")
            return
        title = f"{creed['title']} — {creed.get('greek_title', 'Greek')}"
        body = creed["greek"]
        footer = "Greek (original conciliar language, liturgical wording)"
    elif lang == "latin":
        if not creed.get("latin"):
            await ctx.send(f"No Latin text available for **{creed['title']}**.")
            return
        title = f"{creed['title']} — {creed.get('latin_title', 'Latin')}"
        body = creed["latin"]
        footer = "Latin (traditional liturgical text)"
    else:
        title = creed["title"]
        body = creed["text"]
        footer = "Traditional English (Book of Common Prayer, 1662)"

    pages = _chunk(body, 3900)
    for i, page in enumerate(pages):
        embed = discord.Embed(
            title=title if len(pages) == 1 else f"{title} ({i + 1}/{len(pages)})",
            description=page,
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)
    record_special_stat(ctx.author.id, "creed", f"{creed['title']} [{lang}]")

@bot.command(name="creed", aliases=["creeds"])
async def cmd_creed(ctx, *, which: str = ""):
    """The three ecumenical creeds, in English, Latin, or (Nicene only) Greek.
    Usage: !creed              — list the creeds
           !creed apostle      — the Apostles' Creed (English)
           !creed nicene latin — the Nicene Creed in Latin
           !creed nicene greek — the Nicene Creed in its original Greek
           !creed athanasius parallel — Athanasian Creed, English then Latin
    """
    tokens = which.strip().split()
    key = CREED_ALIASES.get(tokens[0].lower()) if tokens else None
    if not key:
        embed = discord.Embed(title="📜 The Creeds", color=discord.Color.dark_gold())
        embed.description = (
            "`!creed apostle` — The Apostles' Creed\n"
            "`!creed nicene` — The Nicene Creed\n"
            "`!creed athanasius` — The Athanasian Creed (Quicunque Vult)\n\n"
            "Add `latin` for the traditional Latin text, `greek` for the Nicene Creed's original "
            "conciliar language, or `parallel` for all available: "
            "e.g. `!creed apostle latin`, `!creed nicene parallel`.\n\n"
            "English is traditional, as in the 1662 Book of Common Prayer."
        )
        await ctx.send(embed=embed)
        return
    lang = CREED_LANGS.get(tokens[1].lower(), "text") if len(tokens) > 1 else "text"
    await _send_creed(ctx, key, lang)

@bot.tree.command(name="creed", description="The Apostles', Nicene, or Athanasian Creed, in English, Latin, or Greek")
@app_commands.describe(which="apostle | nicene | athanasius, optionally + latin, greek, or parallel")
async def creed_slash(interaction: discord.Interaction, which: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_creed(ctx, which=which)


# ── !summa — Summa Theologica via newadvent.org ───────────────────────────────

@bot.command(name="summa", aliases=["st", "aquinas", "thomas"])
async def cmd_summa(ctx, *, reference: str = ""):
    """
    Look up an article from the Summa Theologica.
    Usage:
      !summa I.2.3        → Prima Pars, Q.2, Article 3
      !summa I-II.109.1   → Prima Secundae, Q.109, A.1
      !summa II-II.23     → Secunda Secundae, Q.23 (list articles)
      !summa random       → random article
    """
    ref = reference.strip()

    async with ctx.typing():
        if not ref or ref.lower() in ("random", "rand", "r"):
            result = get_summa_random()
        else:
            parsed = parse_summa_ref(ref)
            if parsed is None:
                await ctx.send(
                    f"⚠️ Could not parse **{ref}**.\n"
                    f"Format: `!summa I.2.3` · `!summa I-II.109.1` · `!summa II-II.23` · `!summa random`"
                )
                return
            part, question, article = parsed
            result = get_summa(part, question, article)

    if not result["found"]:
        embed = discord.Embed(
            title="Summa Theologica — Not found",
            description=result["error"],
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Question overview (no article specified)
    if result["type"] == "question":
        lines = [f"**{n}.** {title}" for n, title in result["articles"]]
        embed = discord.Embed(
            title=f"ST {result['part_display']}.{result['question']} — {result['title']}",
            description="\n".join(lines) or "No articles found.",
            color=discord.Color.dark_gold(),
            url=result["url"]
        )
        embed.set_footer(text=f"Summa Theologica · {result['part_long']} · newadvent.org")
        record_special_stat(ctx.author.id, "summa", f"ST {result['part_display']}.{result['question']}")
        await ctx.send(embed=embed)
        return

    await _send_summa_article(ctx, result)


async def _send_summa_article(ctx, result: dict):
    """Send a Summa article as a paginated embed: I answer that / Objections / Replies."""
    q_title   = result.get("question_title", "")
    art_title = result["title"]
    url       = result["url"]
    part_long = result["part_long"]

    def _trunc(text: str, limit: int = 3800) -> str:
        if len(text) <= limit:
            return text
        cut = text[:limit].rfind(". ")
        return (text[:cut + 1] if cut > 200 else text[:limit]) + " …"

    pages = []
    body0 = f"*{art_title}*\n\n**I answer that,** {_trunc(result['i_answer_that'])}"
    pages.append(("I answer that", body0))
    if result["objections"]:
        pages.append(("Objections", _trunc("\n\n".join(result["objections"]))))
    body2_parts = []
    if result["on_the_contrary"]:
        body2_parts.append(f"**On the contrary,** {result['on_the_contrary']}")
    body2_parts.extend(result["replies"])
    if body2_parts:
        pages.append(("On the contrary & Replies", _trunc("\n\n".join(body2_parts))))

    total = len(pages)
    footer_base = f"Summa Theologica · {part_long} · Q.{result['question']} A.{result['article']}"

    def make_embed(idx: int) -> discord.Embed:
        page_label, body = pages[idx]
        embed = discord.Embed(
            title=f"ST {result['part_display']}.{result['question']}.{result['article']} — {page_label}",
            description=body,
            color=discord.Color.dark_gold(),
            url=url
        )
        embed.set_footer(text=f"{footer_base} · {idx + 1}/{total} · newadvent.org")
        if idx == 0 and q_title:
            embed.set_author(name=q_title)
        return embed

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class SummaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(label="I answer that", style=discord.ButtonStyle.primary)
        async def jump_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = 0
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = SummaView()
    ref_label = (f"ST {result.get('part_display','')}"
                 f".{result.get('question','')}"
                 f".{result.get('article','')}")
    record_special_stat(ctx.author.id, "summa", ref_label)
    view.message = await ctx.send(embed=make_embed(0), view=view)
