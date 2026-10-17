"""
Traditional prayers by name, for `!prayer st michael` (`!prayer` alone is still a random
Prayer Book prayer, in liturgy.py): the English, the Latin where the prayer has one, and
the chant sung where the bot has the prayer as a chant; the Orthodox prayers with their Greek. Wording as the prayers' Wikipedia
articles give it (tests/test_prayers.py checks a line of each against them).
"""
import re
import unicodedata

import discord

from bot_commands.angelus import AVE_MARIA, HAIL_MARY
from bot_commands.hymns import hymns, sung_path
from bot_commands.rosary import FATIMA, GLORY_BE, HAIL_HOLY_QUEEN, OUR_FATHER

COLOR = discord.Color.from_rgb(110, 70, 140)

# key: (title, [other names], English, Latin or "", a line about it, the chant sung with it or "")
PRAYERS = {
    "st michael": (
        "Prayer to Saint Michael", ["michael", "saint michael", "st. michael", "archangel"],
        "Saint Michael the Archangel, defend us in battle; be our protection against the wickedness and snares of "
        "the devil. May God rebuke him, we humbly pray: and do thou, O Prince of the heavenly host, by the power of "
        "God, thrust into Hell Satan and all of the other evil spirits who prowl about the world seeking the ruin "
        "of souls. Amen.",
        "Sancte Míchael Archángele, defénde nos in prœ́lio; contra nequítiam et insídias diáboli esto præsídium. "
        "Imperet illi Deus, súpplices deprecámur, tuque, Prínceps milítiæ cæléstis, Sátanam aliósque spíritus "
        "malígnos, qui ad perditiónem animárum pervagántur in mundo, divína virtúte, in inférnum detrúde. Amen.",
        "Written by Pope Leo XIII in 1886 and said after Low Mass for decades, as one of the Leonine Prayers.", ""),
    "memorare": (
        "The Memorare", ["remember o most gracious"],
        "Remember, O most gracious Virgin Mary, that never was it known that anyone who fled to your protection, "
        "implored your help, or sought your intercession, was left unaided. Inspired by this confidence, I fly "
        "unto you, O Virgin of virgins, my Mother. To you do I come, before you I stand, sinful and sorrowful. "
        "O Mother of the Word Incarnate, despise not my petitions, but in your mercy, hear and answer me. Amen.",
        "Memorare, piissima Virgo Maria, a saeculo non esse auditum, quemquam ad tua currentem praesidia, tua "
        "implorantem auxilia, tua petentem suffragia, esse derelictum. Ego tali animatus confidentia, ad te, Virgo "
        "Virginum, Mater, curro, ad te venio, coram te gemens peccator assisto. Noli, Mater Verbi, verba mea "
        "despicere; sed audi propitia et exaudi. Amen.",
        "From a longer 15th-century prayer; spread by the French priest Claude Bernard in the 1600s.", "Memorare"),
    "anima christi": (
        "Anima Christi (Soul of Christ)", ["soul of christ"],
        "Soul of Christ, sanctify me.\nBody of Christ, save me.\nBlood of Christ, inebriate me.\n"
        "Water from the side of Christ, wash me.\nPassion of Christ, strengthen me.\nO good Jesus, hear me.\n"
        "Within Thy wounds hide me.\nSuffer me not to be separated from Thee.\nFrom the malignant enemy defend me.\n"
        "In the hour of my death call me,\nAnd bid me come unto Thee,\nThat with Thy Saints I may praise Thee\n"
        "Forever and ever. Amen.",
        "Anima Christi, sanctifica me.\nCorpus Christi, salva me.\nSanguis Christi, inebria me.\n"
        "Aqua lateris Christi, lava me.\nPassio Christi, conforta me.\nO bone Jesu, exaudi me.\n"
        "Intra tua vulnera absconde me.\nNe permittas me separari a te.\nAb hoste maligno defende me.\n"
        "In hora mortis meae voca me.\nEt jube me venire ad te,\nUt cum Sanctis tuis laudem te,\n"
        "In saecula saeculorum. Amen.",
        "A medieval prayer, often said after Communion; St Ignatius put it at the start of his Spiritual Exercises.",
        "Anima Christi"),
    "act of contrition": (
        "Act of Contrition", ["contrition", "confession"],
        "O my God, I am heartily sorry for having offended Thee, and I detest all my sins, because I dread the "
        "loss of heaven and the pains of hell; but most of all because they offend Thee, my God, who art all good "
        "and deserving of all my love. I firmly resolve, with the help of Thy grace, to confess my sins, to do "
        "penance, and to amend my life. Amen.",
        "", "Said in confession, and at the end of the day, in sorrow for sin.", ""),
    "angel of god": (
        "Angel of God (to one's guardian angel)", ["guardian angel", "angele dei"],
        "Angel of God, my guardian dear,\nto whom God's love commits me here,\never this day (or night) be at my "
        "side,\nto light and guard, to rule and guide. Amen.",
        "Ángele Dei, qui custos es mei,\nme tibi commissum pietáte supérna,\nhódie (hac nocte) illúmina, custódi, "
        "rege et gubérna. Amen.",
        "Often the first prayer children learn.", ""),
    "morning offering": (
        "The Morning Offering", ["offering"],
        "O Jesus, through the Immaculate Heart of Mary, I offer you my prayers, works, joys, sufferings of this "
        "day, in union with the Holy Sacrifice of the Mass throughout the world. I offer them for all the "
        "intentions of your Sacred Heart; the salvation of souls, the reparation for sin, the reunion of all "
        "Christians; I offer them for the intentions of our bishops and of all members of the Apostleship of "
        "Prayer, and in particular for the intention recommended by the Holy Father this month.",
        "", "The first prayer of the day, offering it to God; from the Apostleship of Prayer (1844).", ""),
    "sub tuum": (
        "Sub tuum praesidium (We fly to thy protection)", ["we fly to thy protection", "sub tuum praesidium"],
        "We fly to thy protection, O Holy Mother of God; do not despise our petitions in our necessities, but "
        "deliver us always from all dangers, O glorious and blessed Virgin.",
        "Sub tuum præsidium confugimus, sancta Dei Génetrix; nostras deprecatiónes ne despícias in necessitátibus, "
        "sed a perículis cunctis líbera nos semper, Virgo gloriósa et benedícta.",
        "The oldest known prayer to Mary: parts are found on a papyrus of the 3rd or 4th century.",
        "Sub tuum praesidium"),
    "divine praises": (
        "The Divine Praises", ["blessed be god"],
        "Blessed be God.\nBlessed be His Holy Name.\nBlessed be Jesus Christ, true God and true Man.\n"
        "Blessed be the Name of Jesus.\nBlessed be His Most Sacred Heart.\nBlessed be His Most Precious Blood.\n"
        "Blessed be Jesus in the most holy Sacrament of the Altar.\nBlessed be the Holy Spirit, the Paraclete.\n"
        "Blessed be the great Mother of God, Mary most holy.\nBlessed be her holy and Immaculate Conception.\n"
        "Blessed be her glorious Assumption.\nBlessed be the name of Mary, Virgin and Mother.\n"
        "Blessed be St. Joseph, her most chaste spouse.\nBlessed be God in His Angels and in His Saints.",
        "", "Written in 1797 in reparation for blasphemy; said at Benediction of the Blessed Sacrament.", ""),
    "st joseph": (
        "Prayer to Saint Joseph", ["joseph", "saint joseph", "to thee o blessed joseph"],
        "To thee, O blessed Joseph, we have recourse in our affliction, and having implored the help of thy thrice "
        "holy Spouse, we now, with hearts filled with confidence, earnestly beg thee also to take us under thy "
        "protection. By that charity wherewith thou wert united to the Immaculate Virgin Mother of God, and by "
        "that fatherly love with which thou didst cherish the Child Jesus, we beseech thee and we humbly pray that "
        "thou wilt look down with gracious eye upon that inheritance which Jesus Christ purchased by His blood, "
        "and wilt succor us in our need by thy power and strength.\n\nDefend, O most watchful guardian of the Holy "
        "Family, the chosen off-spring of Jesus Christ. Keep from us, O most loving Father, all blight of error "
        "and corruption. Aid us from on high, most valiant defender, in this conflict with the powers of darkness. "
        "And even as of old thou didst rescue the Child Jesus from the peril of His life, so now defend God's Holy "
        "Church from the snares of the enemy and from all adversity. Shield us ever under thy patronage, that, "
        "following thine example and strengthened by thy help, we may live a holy life, die a happy death, and "
        "attain to everlasting bliss in Heaven. Amen.",
        "", "By Pope Leo XIII (1889), for October, the month of the Rosary, after the Rosary.", ""),
    "st francis": (
        "Prayer of Saint Francis (Make me an instrument of your peace)", ["francis", "instrument of your peace",
                                                                          "peace prayer"],
        "Lord, make me an instrument of your peace.\nWhere there is hatred, let me bring love.\nWhere there is "
        "offence, let me bring pardon.\nWhere there is discord, let me bring union.\nWhere there is error, let me "
        "bring truth.\nWhere there is doubt, let me bring faith.\nWhere there is despair, let me bring hope.\n"
        "Where there is darkness, let me bring your light.\nWhere there is sadness, let me bring joy.\nO Lord, "
        "grant that I may not so much seek\nto be consoled as to console,\nto be understood as to understand,\n"
        "to be loved as to love,\nfor it is in giving that one receives,\nit is in self-forgetting that one "
        "finds,\nit is in forgiving that one is forgiven,\nit is in dying that one awakens to eternal life.",
        "", "First printed in French in 1912; not by St Francis himself, but long given his name.", ""),
    "come holy spirit": (
        "Come, Holy Spirit", ["veni sancte spiritus", "holy spirit", "holy ghost"],
        "Come, Holy Spirit, fill the hearts of Thy faithful and kindle in them the fire of Thy love.\n"
        "℣. Send forth Thy Spirit, and they shall be created.\n℟. And Thou shalt renew the face of the earth.\n"
        "*Let us pray.* O God, who by the light of the Holy Spirit didst instruct the hearts of the faithful, grant "
        "that by the same Holy Spirit we may be truly wise and ever enjoy His consolations. Through Christ our "
        "Lord. Amen.",
        "Veni, Sancte Spíritus, reple tuórum corda fidélium, et tui amóris in eis ignem accénde.\n"
        "℣. Emítte Spíritum tuum, et creabúntur.\n℟. Et renovábis fáciem terræ.",
        "Said before study, work or any undertaking.", "Veni Sancte Spiritus reple"),
    "eternal rest": (
        "Eternal Rest (for the dead)", ["requiem", "requiem aeternam", "for the dead", "faithful departed"],
        "Eternal rest grant unto them, O Lord, and let perpetual light shine upon them. May they rest in peace. "
        "Amen.\nMay their souls, and the souls of all the faithful departed, through the mercy of God, rest in "
        "peace. Amen.",
        "Requiem ætérnam dona eis, Dómine, et lux perpétua lúceat eis. Requiéscant in pace. Amen.",
        "The Church's prayer for the dead; its first words open the Requiem Mass (whose Introit is sung here).",
        "Requiem aeternam (Introit of the Requiem Mass)"),
    "grace": (
        "Grace before and after meals", ["grace before meals", "bless us o lord", "meals"],
        "*Before:* Bless us, O Lord, and these Thy gifts, which we are about to receive from Thy bounty, through "
        "Christ our Lord. Amen.\n\n*After:* We give Thee thanks, Almighty God, for these and all Thy gifts, which "
        "we have received through Christ our Lord. Amen.",
        "", "Each is begun and ended with the sign of the cross.", ""),
    "our father": (
        "The Our Father (the Lord's Prayer)", ["lords prayer", "lord's prayer", "pater noster", "paternoster"],
        OUR_FATHER,
        "Pater noster, qui es in cælis, sanctificétur nomen tuum. Advéniat regnum tuum. Fiat volúntas tua, sicut in "
        "cælo et in terra. Panem nostrum quotidiánum da nobis hódie, et dimítte nobis débita nostra, sicut et nos "
        "dimíttimus debitóribus nostris. Et ne nos indúcas in tentatiónem: sed líbera nos a malo. Amen.",
        "The prayer Jesus taught (Matthew 6:9-13, Luke 11:2-4).", "Pater noster"),
    "hail mary": (
        "The Hail Mary", ["ave maria", "hail mary full of grace"], HAIL_MARY, AVE_MARIA,
        "The angel's greeting (Luke 1:28) and Elizabeth's (Luke 1:42), with the Church's petition.",
        "Ave Maria (Antiphona)"),
    "glory be": (
        "The Glory Be (Gloria Patri)", ["gloria patri", "doxology"], GLORY_BE,
        "Glória Patri, et Fílio, et Spirítui Sancto. Sicut erat in princípio, et nunc, et semper, et in sǽcula "
        "sæculórum. Amen.",
        "The short hymn of praise to the Trinity that ends every psalm in the Office.", ""),
    "hail holy queen": (
        "Hail, Holy Queen (Salve Regina)", ["salve regina", "holy queen"], HAIL_HOLY_QUEEN,
        "Salve, Regína, Mater misericórdiæ; vita, dulcédo, et spes nostra, salve. Ad te clamámus, éxsules fílii "
        "Hevæ. Ad te suspirámus, geméntes et flentes in hac lacrimárum valle. Eia ergo, advocáta nostra, illos tuos "
        "misericórdes óculos ad nos convérte. Et Jesum, benedíctum fructum ventris tui, nobis post hoc exsílium "
        "osténde. O clemens, O pia, O dulcis Virgo María.",
        "Sung at the end of Compline from Trinity Sunday to Advent, and said at the end of the Rosary.",
        "Salve Regina"),
    "fatima": (
        "The Fátima Prayer (O my Jesus)", ["o my jesus", "fatima prayer", "decade prayer"], FATIMA, "",
        "Many add it after each decade of the Rosary; from the apparitions at Fátima, 1917.", ""),
}
# the Orthodox Church's prayers, with their Greek
PRAYERS.update({
    "jesus prayer": (
        "The Jesus Prayer", ["prayer of the heart", "lord jesus christ son of god"],
        "Lord Jesus Christ, Son of God, have mercy on me, a sinner.",
        "Κύριε Ἰησοῦ Χριστέ, Υἱὲ τοῦ Θεοῦ, ἐλέησόν με τὸν ἁμαρτωλόν.",
        "The prayer of the heart of Orthodox monks, said over and over, often on a prayer rope, after the "
        "blind man's cry (Luke 18:38) and the tax collector's (Luke 18:13).", ""),
    "trisagion": (
        "The Trisagion (Holy God)", ["holy god", "thrice holy", "agios o theos"],
        "Holy God, Holy Mighty, Holy Immortal, have mercy on us. *(three times)*\nGlory to the Father, and to the "
        "Son, and to the Holy Spirit, both now and ever, and unto the ages of ages. Amen.\nO All-Holy Trinity, "
        "have mercy on us; O Lord, blot out our sins; O Master, pardon our iniquities; O Holy One, visit and heal "
        "our infirmities for Thy Name's sake.\nLord, have mercy. *(three times)*",
        "Ἅγιος ὁ Θεός, Ἅγιος ἰσχυρός, Ἅγιος ἀθάνατος, ἐλέησον ἡμᾶς.",
        "\"Thrice holy\": sung at every Divine Liturgy and said at the start of nearly every Orthodox service.", ""),
    "o heavenly king": (
        "O Heavenly King", ["heavenly king", "basileu ouranie"],
        "O Heavenly King, Comforter, Spirit of Truth, Who art everywhere present and fillest all things, Treasury "
        "of good things, and Giver of life: come and abide in us, and cleanse us from every sin, and save our "
        "souls, O Good One!",
        "Βασιλεῦ οὐράνιε, Παράκλητε, τὸ Πνεῦμα τῆς ἀληθείας, ὁ πανταχοῦ παρὼν καὶ τὰ πάντα πληρῶν, ὁ θησαυρὸς τῶν "
        "ἀγαθῶν καὶ ζωῆς χορηγός, ἐλθὲ καὶ σκήνωσον ἐν ἡμῖν, καὶ καθάρισον ἡμᾶς ἀπὸ πάσης κηλῖδος, καὶ σῶσον, "
        "Ἀγαθέ, τὰς ψυχὰς ἡμῶν.",
        "The prayer to the Holy Spirit that begins Orthodox prayers; left out from Pascha to Pentecost.", ""),
    "axion estin": (
        "It Is Truly Meet (Axion Estin)", ["it is truly meet", "it is truly right", "more honourable than the cherubim"],
        "It is truly meet to bless thee, O Theotokos, ever-blessed and most pure, and the Mother of our God. More "
        "honourable than the Cherubim, and more glorious beyond compare than the Seraphim, without defilement thou "
        "gavest birth to God the Word. True Theotokos, we magnify thee.",
        "Ἄξιόν ἐστιν ὡς ἀληθῶς μακαρίζειν σε τὴν Θεοτόκον, τὴν ἀειμακάριστον καὶ παναμώμητον καὶ μητέρα τοῦ Θεοῦ "
        "ἡμῶν. Τὴν τιμιωτέραν τῶν Χερουβεὶμ καὶ ἐνδοξοτέραν ἀσυγκρίτως τῶν Σεραφείμ, τὴν ἀδιαφθόρως Θεὸν Λόγον "
        "τεκοῦσαν, τὴν ὄντως Θεοτόκον, σὲ μεγαλύνομεν.",
        "The hymn to the Theotokos (the Mother of God) at the Divine Liturgy; by tradition an angel taught it to "
        "a monk of Mount Athos in the 10th century.", ""),
    "rejoice o virgin": (
        "Rejoice, O Virgin Theotokos", ["theotokos virgin rejoice", "rejoice o theotokos", "orthodox hail mary"],
        "God-bearing Virgin, rejoice, grace-filled Mary, the Lord with thee. Praised thou among women, and praised "
        "the fruit of thy womb, because it was the Saviour of our souls that thou borest.",
        "Θεοτόκε Παρθένε, χαῖρε, κεχαριτωμένη Μαρία, ὁ Κύριος μετὰ σοῦ. εὐλογημένη σὺ ἐν γυναιξί, καὶ "
        "εὐλογημένος ὁ καρπὸς τῆς κοιλίας σου, ὅτι Σωτῆρα ἔτεκες τῶν ψυχῶν ἡμῶν.",
        "The Orthodox form of the Hail Mary: the angel's greeting and Elizabeth's, sung at Vespers.", ""),
    "st ephrem": (
        "The Prayer of Saint Ephrem", ["ephrem", "ephraim", "lord and master of my life", "lenten prayer"],
        "O Lord and Master of my life, a spirit of idleness, curiosity, ambition, and idle talking; give me not.\n"
        "But a spirit of chastity, humility, patience, and love, bestow upon me, Thy servant.\nYea, O Lord King: "
        "grant me to see mine own failings, and not to condemn others; for blessed art Thou unto the ages of ages. "
        "Amen.",
        "Κύριε καὶ Δέσποτα τῆς ζωῆς μου, πνεῦμα ἀργίας, περιεργίας, φιλαρχίας, καὶ ἀργολογίας μή μοι δῷς.\n"
        "Πνεῦμα δὲ σωφροσύνης, ταπεινοφροσύνης, ὑπομονῆς, καὶ ἀγάπης χάρισαί μοι τῷ σῷ δούλῳ.\nΝαί, Κύριε "
        "Βασιλεῦ, δώρησαι μοι τοῦ ὁρᾶν τὰ ἐμὰ πταίσματα, καὶ μὴ κατακρίνειν τὸν ἀδελφόν μου, ὅτι εὐλογητὸς εἶ, εἰς "
        "τοὺς αἰῶνας τῶν αἰώνων. Ἀμήν.",
        "The prayer of Great Lent, said with prostrations; by St Ephrem the Syrian (4th century).", ""),
    "orthodox creed": (
        "The Nicene Creed (as the Orthodox say it)", ["symbol of faith", "orthodox nicene creed", "creed without filioque"],
        "I believe in one God, the Father Almighty, Maker of heaven and earth, and of all things visible and "
        "invisible;\nAnd in one Lord Jesus Christ, the Son of God, the Only-begotten, begotten of the Father before "
        "all ages; Light of Light, true God of true God, begotten, not made, of one essence with the Father, by whom "
        "all things were made; who for us men and for our salvation came down from heaven, and was incarnate of "
        "the Holy Spirit and the Virgin Mary, and became man; and was crucified also for us under Pontius Pilate, "
        "and suffered and was buried; and the third day He rose again, according to the Scriptures; and ascended "
        "into heaven, and sits at the right hand of the Father; and He shall come again with glory to judge the "
        "living and the dead, whose kingdom shall have no end.\nAnd in the Holy Spirit, the Lord, the Giver of "
        "Life, who proceeds from the Father; who with the Father and the Son together is worshipped and glorified; "
        "who spoke by the prophets;\nIn one Holy, Catholic, and Apostolic Church.\nI acknowledge one baptism for "
        "the remission of sins.\nI look for the resurrection of the dead, and the life of the age to come. Amen.",
        "Πιστεύω εἰς ἕνα Θεόν, Πατέρα, Παντοκράτορα, ποιητὴν οὐρανοῦ καὶ γῆς, ὁρατῶν τε πάντων καὶ ἀοράτων… "
        "Καὶ εἰς τὸ Πνεῦμα τὸ Ἅγιον, τὸ κύριον, τὸ ζῳοποιόν, τὸ ἐκ τοῦ Πατρὸς ἐκπορευόμενον… Ἀμήν.",
        "The Creed of Nicaea and Constantinople (381) as first written: the Spirit \"proceeds from the Father\", "
        "without the Western addition \"and the Son\" (the filioque). The full Greek: `!creed nicene greek`.", ""),
})
ORTHODOX = ["jesus prayer", "trisagion", "o heavenly king", "axion estin", "rejoice o virgin", "st ephrem",
            "orthodox creed"]

# prayers that have commands of their own
ELSEWHERE = {"angelus": "`!angelus`", "regina caeli": "`!angelus` (in Eastertide)", "rosary": "`!rosary`",
             "apostles creed": "`!creed apostles`", "creed": "`!creed`", "nicene creed": "`!creed nicene`"}


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    s = s.replace("æ", "ae").replace("saint ", "st ").replace("st. ", "st ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", s)).strip()


def find(query: str) -> "str | None":
    q = _norm(query)
    for key, (title, names, *_rest) in PRAYERS.items():
        if q in [_norm(key), _norm(title)] + [_norm(n) for n in names]:
            return key
    for key, (title, names, *_rest) in PRAYERS.items():                 # a word or two of the name
        if any(q and q in _norm(n) for n in [key, title] + names):
            return key
    return None


def prayer_message(key: str) -> dict:
    title, _, english, latin, note, chant = PRAYERS[key]
    embed = discord.Embed(title=f"🙏 {title}", description=english[:4096], color=COLOR)
    if latin:
        embed.add_field(name="In Greek" if key in ORTHODOX else "In Latin", value=latin[:1024], inline=False)
    embed.set_footer(text=note)
    message = {"embed": embed}
    hymn = next((h for h in hymns() if h["title"] == chant), None) if chant else None
    path = sung_path(hymn) if hymn else None
    if path:
        message["content"] = f"🎤 *{chant}*, sung in Latin."
        message["file"] = discord.File(path, filename=re.sub(r"[^A-Za-z0-9]+", "_", chant).strip("_") + "_sung.ogg")
    return message


def list_embed() -> discord.Embed:
    lines = [f"• **{title}** — `!prayer {key}`" for key, (title, *_rest) in PRAYERS.items() if key not in ORTHODOX]
    embed = discord.Embed(title="🙏 Traditional prayers", color=COLOR, description="\n".join(lines))
    embed.add_field(name="☦️ Orthodox", value="\n".join(f"• **{PRAYERS[k][0]}** — `!prayer {k}`" for k in ORTHODOX),
                    inline=False)
    embed.add_field(name="Elsewhere", value="The Angelus and Regina Caeli: `!angelus` · the Rosary: `!rosary` · "
                                            "the Creeds: `!creed` · a random Prayer Book prayer: `!prayer`",
                    inline=False)
    return embed


async def send_prayer(ctx, query: str) -> None:
    q = _norm(query)
    if q in ("list", "all", "prayers", "index"):
        await ctx.send(embed=list_embed())
        return
    if q in ELSEWHERE:
        await ctx.send(f"That one has its own command: {ELSEWHERE[q]}.")
        return
    key = find(query)
    if key is None:
        await ctx.send(f"I don't know a prayer called **{discord.utils.escape_markdown(query.strip())}**. "
                       f"`!prayer list` shows the ones I have.")
        return
    await ctx.send(**prayer_message(key))
