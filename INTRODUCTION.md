# ScriptureBot introduction

Posted by `!changelogintro` at the top of a server's updates channel: one
Discord message per `## ` section, then the most recent changelog entries.
Each section must stay under ~3,800 characters (Discord's embed limit is
4,096), and every user-facing command must be mentioned somewhere — a test
checks both. Written for people who have never used the bot.

## 👋 Hello! I'm ScriptureBot
I'm a library of sacred and ancient texts that lives in this server. I can look up a verse from the Bible in dozens of translations, show you the original Hebrew and Greek, tell you what the translators were thinking, pray the daily office with you, consult an ancient oracle — and a great deal more, across about **a thousand works** from more than a dozen traditions.

**Four ways to talk to me**
**1. Commands starting with `!`** — for example `!verse John 3:16`. This is the main way.
**2. Slash commands** — type `/` and pick from the list (for example `/verse`). They work the same, and Discord shows you what to fill in. `/verse` even suggests book names as you type.
**3. Just chat.** If you mention a Bible reference in an ordinary message — *"as it says in Romans 8:28…"* — I'll reply with the verse.
**4. Right-click any message** (on a phone: press and hold it), choose **Apps**, then **Look up verses** — I'll show you every reference in it (up to five), privately, just for you. Handy for long lists of verses, or older messages.

**Buttons**
Many of my answers come with buttons underneath. Under a Bible verse you'll see **Notes · Cross-refs · Interlinear · Card**, which dig deeper into that verse with one click (each is explained below). Long answers have **◀ ▶** buttons to turn the page.

**Getting help any time**
`!help` shows every command at a glance, and `!help <command>` explains one in detail — `!help verse`, `!help bcp`, `!help jewish`. The messages below are the full tour: first my library, then every command, grouped by what it's for.

## 📚 My library: the Bible and its neighbours
**The Bible** — all 66 books, King James Version by default, plus **more than 40 other translations** you can ask for by name: modern English (ESV, NIV, NASB, NKJV, NLT, NRSVCE, NABRE, CSB, the NET Bible and more), older ones (Geneva Bible, Young's Literal, Douay-Rheims, Knox), and the **original and ancient languages**: Hebrew (Westminster Leningrad Codex), Greek New Testament (Textus Receptus, Tischendorf), the Greek Old Testament (Septuagint), Latin (Vulgate), Syriac (Peshitta), Church Slavonic and even Old English. `!translations` lists them all.

**Apocrypha & Pseudepigrapha** — the 15 deuterocanonical books (Tobit, Judith, Wisdom, Sirach, Maccabees…) and 29 more ancient Jewish and early Christian writings: the **Book of Enoch**, **Jubilees**, the Testaments of the Twelve Patriarchs, the Psalms of Solomon, 3 & 4 Maccabees, Psalms 151–155 **2 Enoch** (the *Book of the Secrets of Enoch*), the First and Second Books of **Adam and Eve**, and the **Odes of Solomon**, early Christian hymns.

**New Testament Apocrypha** — 41 early Christian writings that didn't make it into the Bible: the **infancy gospels** (the *Protevangelium of James*, the story of Mary's own birth and childhood: `!verse Protevangelium 1:1`; the *Infancy Gospel of Thomas*, about Jesus as a boy), the **Acts of Pilate** or *Gospel of Nicodemus* with Christ's descent into hell, the **Acts of Paul and Thecla** and other acts of the apostles, and the **Passing of Mary**.

**The Dead Sea Scrolls** — the Community Rule, War Scroll, Damascus Document, Thanksgiving Hymns, the Habakkuk commentary and others, plus scroll copies of Isaiah, Exodus, Deuteronomy, Psalms and Daniel.

**Latter-day Saint scripture** — the Book of Mormon, Doctrine and Covenants, and Pearl of Great Price.

**Jewish writers of the Greek world** — the complete works of **Josephus** (Antiquities, Jewish War…) and **Philo of Alexandria**.

**The early Church** — the **Apostolic Fathers** (Clement, Ignatius, Polycarp, the Didache, the Shepherd of Hermas…), Dionysius the Areopagite, and about **400 works of the Church Fathers**, from Justin Martyr and Irenaeus through Augustine, Chrysostom and Jerome, plus early church histories. From the Middle Ages: **Bede**, **The Golden Legend**, the **Rule of St Benedict**, Thomas à Kempis's **Imitation of Christ** and Dante's **Divine Comedy** (Longfellow's translation, by canto and line: `!verse Inferno 1.1`).

## 📚 My library: other traditions
**Rabbinic & mystical Judaism** (from Sefaria) — the **Mishnah**, **Tosefta**, **Babylonian** and **Jerusalem Talmud**, the Targumim (Aramaic Bible translations), **Midrash Rabbah** and other midrashim, **Maimonides** (Mishneh Torah, Guide for the Perplexed), and Kabbalah: the **Zohar**, Sefer Yetzirah, the Bahir and the Tanya. `!help jewish` shows how to cite each.

**Islam** — the **Quran** (all 114 surahs, Pickthall's translation) and nine **hadith** collections, including Sahih al-Bukhari and Sahih Muslim. `!help islamic` has the details. From the Sufi poets: 43 poems from the **Divan of Hafiz** (`!verse Hafiz 1`).

**The Greek and Roman world** — Homer (*Iliad*, *Odyssey*), Virgil's *Aeneid*, Hesiod (*Theogony*, *Works and Days*, *Shield of Heracles*), Ovid, the Homeric and Orphic Hymns; philosophy from **Plato** and **Aristotle** to the Neoplatonists (Plotinus, Porphyry, Iamblichus, Proclus) and the emperor Julian; the Stoics **Marcus Aurelius** (*Meditations*) and **Epictetus** (*Enchiridion*); the **Hermetic** writings (Corpus Hermeticum, the Emerald Tablet); and oracles (Delphic maxims, the Chaldaean Oracles, the Golden Verses of Pythagoras).

**Gnostic & related** — the **Gospel of Thomas**, 114 sayings of Jesus (`!verse Gospel of Thomas 77`), the **Nag Hammadi library** (41 texts), the Mandaean *Ginza Rba* and *Book of John*, and Manichaean psalms.

**Buddhism and China** — the **Dhammapada** (the Buddha's sayings in verse: `!verse Dhammapada 183`), the **Sutta Nipāta** (some of the oldest Buddhist teachings: `!verse Sutta Nipata 143`) and the **Diamond Sutra**; the **Tao Te Ching**, Confucius's **Analects** (`!verse Analects 2.4`) and the **I Ching**, the ancient Chinese Book of Changes.

**Hinduism** — the four **Vedas**, the **Bhagavad Gita** (every verse, in Shri Purohit Swami's translation: `!verse Gita 2:47`) and three of the **Upanishads**, the philosophical heart of the Vedas (the Isa, Katha and Kena).

**Further afield** — the Zoroastrian **Gathas**; eight works of the **Bahá'í** faith, including the Kitáb-i-Aqdas; the Norse **Poetic Edda**; and the **ancient Near East**: the Epic of Gilgamesh, the Babylonian creation epic **Enuma Elish** (`!verse Enuma Elish 4`), the Canaanite Baal Cycle, the Egyptian Book of the Dead and Hymn to the Aten, the Wisdom of Ahikar, and the pre-Islamic Arabic Mu'allaqat poems. (I even have the Sermons of Vivec from *The Elder Scrolls*.)

Browse all of it with `!books`, or let me pick something at random with `!discover`.

## 📖 Reading scripture
**`!verse`** (or `!v`) is my main command.
• `!verse John 3:16` — one verse · `!verse Genesis 1:1-5` — a range · `!verse John 7:53-8:11` — across chapters · `!verse Psalm 23` — a whole chapter, in pages
• `!verse John 3:16 ESV` — in another translation · `!verse John 3:16 KJV ESV NIV` — several side by side
• `!verse` — a random verse · `!verse Proverbs` — random from one book · `!verse bible nt` — random from the New Testament
• Other traditions work the same way: `!verse Quran 2:255`, `!verse Enoch 1:9`, `!verse Berakhot 2a`, `!verse Gilgamesh 11`, `!verse Rig Veda 10.121:9`, `!verse Republic 514a` (Plato by the page-and-section numbers printed in every edition, or a stretch: `!verse Republic 514a-515c`), `!verse Iliad 6.440` (Homer by book and line)
Abbreviations are fine (`Jn`, `1 Cor`, `Ps`). Bible verses come with the four study buttons.

**`!prefer ESV`** makes a translation your personal default, so plain `!verse` uses it. `!prefer off` goes back to the KJV.
**`!translations`** lists every translation and the short name to use.

**`!search shepherd`** finds a word or phrase across my whole library (add a translation to search the Bible in it, e.g. `!search shepherd ESV`). Add `in:` and a tradition to search just that one: `!search nirvana in:buddhist`, `in:chinese`, `in:islamic`, `in:hindu`, `in:christian`… Up to 3 searches per 30 seconds.
**`!theme forgiveness`** — one passage on a theme from each tradition, side by side: the Bible next to the Quran, the Dhammapada, the Tao Te Ching, the Gita, the Stoics and more. Try `!theme love`, `!theme death`, `!theme the soul`.

**`!books`** opens an interactive browser of my whole library: pick a tradition, then a collection, then a book, and see its chapters. `!books Genesis` jumps straight to a book; `!books Augustine` lists an author's works.

**`!discover`** shows a random passage from anywhere in my library — a good way to stumble onto something new.

**`!export John`** sends a whole book as a text file you can download (`!export John 1-5` for chapters 1–5).

## 🔍 Comparing translations and languages
**`!compare John 3:16`** — one verse across many English translations, a page at a time.
• `!compare ancient John 3:16` — the same verse in the ancient witnesses: Hebrew or Greek, the Septuagint, Latin Vulgate, Syriac Peshitta, Church Slavonic and Old English.
• `!compare strong John 3:16` — the KJV with every word tagged by its number in Strong's dictionary of Hebrew and Greek.

**`!interlinear John 3:16`** — an image of the verse in the original Greek (or Hebrew, for the Old Testament), word by word, with how each word is pronounced and what it means written underneath. Press **Interlinear** under any Bible verse for the same thing.
**`!reverseinterlinear John 3:16`** — the other way round: the KJV in normal English word order, each word labelled with the Hebrew or Greek word it translates.

**`!variants Isaiah 53:5`** — puts the KJV beside the Septuagint and the Dead Sea Scroll text of the same verse, where a scroll survives (Isaiah, Exodus, Deuteronomy, Psalms, Daniel), with the scroll's story and a link to see it.

**`!parallel`** — classic works side by side in English and the original: `!parallel Il. 6.440-465` (Homer's *Iliad* in Greek with Pope's translation), `!parallel Aen. 4.1-30` (Virgil in Latin with Dryden), Ovid, the Old Saxon *Heliand*, Plato, Gilgamesh with the Akkadian, the Baal Cycle with the Ugaritic. `!parallel` alone lists everything available.

**`!card John 3:16`** — turns a verse into a parchment-style image to share (`!card John 3:16 ESV NIV` stacks translations). The **Card** button does the same.

## 🎓 Study tools
**`!notes John 3:16`** — the NET Bible's translators' notes: why a word was translated the way it was, background on the passage, and where ancient manuscripts disagree. Small numbers in the verse show which word each note is about. (Also the **Notes** button.)
**`!xref John 3:16`** — related verses elsewhere in the Bible, from the classic *Treasury of Scripture Knowledge*. (Also the **Cross-refs** button.)
**`!quoted Isaiah 53:5`** — where the New Testament quotes the Old (or the Book of Enoch and other ancient writings), shown side by side, each labelled as a direct quotation or a looser parallel.
**`!study John 3:16`** — the verse plus what the early Church Fathers said about it. **`!catena John 3:16`** gives just the Fathers' commentary.

**The original languages** (Strong's numbers are a standard numbering of every Hebrew and Greek word in the Bible — G for Greek, H for Hebrew):
• `!strong G26` — the dictionary entry for a word (here *agapē*, love) · `!strong John 3:16` — a verse with every word numbered
• `!root love` or `!root G26` — a word's root and the family of words built from it
• `!concordance G26` (or `!concordance agape`) — every verse where that word appears

**Reference books**
• `!topic forgiveness` — *Nave's Topical Bible*: every passage on a subject, organised into an outline
• `!dictionary Melchizedek` — people, places and terms, from *Easton's* and *Smith's Bible Dictionary*
• `!timeline Abraham` — where a person or event falls in James Ussher's famous chronology (*Annals of the World*, 1658), with what came just before and after
• `!gematria love` — the numerical values of a word in Hebrew and English gematria (numbers work too: `!gematria 666`)

## 🗺️ People, places and hymns
**`!who Ruth`** — who someone in the Bible was: a short description, their family (parents, husband or wife, children, brothers and sisters), their tribe, where they were born and died, and every verse that names them. When several people share a name — there are seven Marys and a dozen Johns — I'll list them so you can pick the one you mean (`!who Mary`). The menu under the card opens any of their relatives, so you can follow a family tree: Ruth → her son Obed → his son Jesse → his son David.

**`!tree David`** — a family tree, drawn as a picture: the person in the middle with their brothers and sisters, husband or wives, and children, their parents and grandparents above, and their line of fathers going back across the top. Big families are cut short to the best-known names (David had more than twenty children).
**`!tree Abraham to David`** — every generation from one person down to another, drawn as a chart: Abraham, Isaac, Jacob, Judah… down to David, fourteen generations. Try `!tree Adam to Jesus` for the whole of the Bible's genealogies, 65 generations. The names can go in either order.

**`!place Bethel`** — a place in the Bible on a map: the place marked in red with the towns, seas and regions around it named so you can get your bearings, a small map of the whole Bible world in the corner showing where you are, and a scale in kilometres and miles. Under it: what the place was, who was born or died there, and every verse that names it. Where nobody is quite sure where a place was, the map says so. Try `!place Sea of Galilee`, `!place Rome` or `!place Ur`.

**`!hymn amazing grace`** — a hymn's words, who wrote them and the tune, and the Bible passages it draws on. Search by title, first line, a line you remember from the words, a topic (`!hymn christmas`) or a passage (`!hymn Psalm 23` finds hymns based on it). `!hymn` alone picks one at random. Two buttons sit under each hymn:
• **▶️ Play the tune** — I play the hymn tune once through, in four-part harmony on an organ, as audio you can listen to right in Discord.
• **📖 Read the passages** — the Bible verses behind the hymn.
About 290 public-domain hymns and carols, from the Open Hymnal Project and Hymnary.org.

**`!metrical 23`** — a psalm from the **Scottish Metrical Psalter** of 1650: all 150 Psalms rewritten in rhyme and a steady beat so a whole congregation could sing them, still sung in Scottish churches today (it gave us *The Lord's my shepherd, I'll not want*). I show the psalm with its stanzas numbered by Bible verse, and the tune it's traditionally sung to:
• **▶️ Play the tune** — one verse of the tune in four parts on an organ; every stanza is sung to it.
• **The tune menu** — play the psalm to any other tune in the same rhythm, since any of them fits the words.
• **📖 Read in the KJV** — the same psalm in ordinary prose, to compare.
• **Second version** — some psalms (like Psalm 100) have two versions in the Psalter, and this switches between them. Ask for one directly with `!metrical 100b`.
Long psalms have buttons to turn the page, or ask for some verses: `!metrical 119:105-112`. Psalm 119 shows its 22 parts under their Hebrew letters (Aleph, Beth, Gimel…), with a menu to jump between them; ask for one by name with `!metrical 119 nun`. You can also search the words (`!metrical shepherd`), list every psalm sung to a tune (`!metrical crimond`), or get a random one with `!metrical`. `!psalm 23 sing` does the same as `!metrical 23`.

## ⛪ Prayer, liturgy & the Church
**`!today`** — what's happening today across traditions: the Catholic, Anglican and Orthodox calendars (feasts, saints, seasons, Orthodox fasting), the Hebrew date and Jewish holidays, and the Islamic date and holidays. Narrow it down with `!today catholic`, `!today orthodox`, `!today jewish`, `!today islam`; add a date with `!today 12-25`.

**The Daily Office** — Morning and Evening Prayer from the Book of Common Prayer (the Canadian 1962 Prayer Book, with Coverdale's Psalter):
• `!bcp` — today's psalms, two readings and collect, for morning or evening depending on the time · `!bcp morning`, `!bcp evening`, `!bcp 2026-12-25`
• `!mp` / `!ep` — just the readings for Morning or Evening Prayer
• `!psalm` — today's appointed psalms (`!psalm ep` for the evening ones)
• `!collect` — the Collect (short prayer) of the day
• `!prayer` — a random prayer from the 1662 Prayer Book

**`!creed`** — the Apostles', Nicene and Athanasian Creeds in traditional English: `!creed nicene`, with `latin` or `greek` for the original (`!creed nicene greek`) or `parallel` for all at once.

**Catholic teaching**
• `!ccc 1` — a paragraph of the *Catechism of the Catholic Church* (`!ccc 1700-1715` for a range, `!ccc random`)
• `!canon 1` — a canon of the Code of Canon Law
• `!summa I.2.3` — an article of St Thomas Aquinas's *Summa Theologica* (Part I, Question 2, Article 3), or `!summa random`

## 🔮 Oracles
For centuries people have sought guidance by opening a revered book at random or casting lots. I keep several of those traditions alive — for reflection and fun:
• `!virgil` — the *Sortes Vergilianae*: a random line from Virgil's *Aeneid*, as people did in the Middle Ages
• `!homer` — I roll three dice and give you the matching answer from the *Homeromanteion*, an oracle preserved on an ancient Egyptian papyrus
• `!delphi` — one of the maxims carved at the Temple of Apollo at Delphi
• `!oracle` — a saying from the Delphic oracles, the *Chaldaean Oracles* or the Golden Verses of Pythagoras
• `!sortesbiblicae` (or `!bibliomancy`) — the Bible opened at random
• `!iching` — I toss three coins six times to build a hexagram from the *I Ching*, the Chinese Book of Changes, and read you its Judgment and Image; any "changing" lines get their own readings and turn it into a second hexagram
• `!hafez` — *Fāl-e Hāfez*, a custom still alive in Iran: hold a wish or question in mind and open the poems of Hafiz, the great 14th-century Persian poet, at random; the poem you find is your answer

**Play a game:** `!quiz` shows a verse and four buttons — which book is it from? `!quiz hard` mixes traditions (Proverbs? the Quran? the Norse Edda?), and you can quiz yourself on one tradition: `!quiz buddhist`, `!quiz chinese`, `!quiz hindu`, `!quiz classical`, `!quiz norse` and more. `!quiz leaderboard` shows this server's top scorers — this week (it starts fresh every Monday) and of all time. Everyone gets one guess; the answer is revealed after a minute. Get three or more right in a row and you'll see your 🔥 streak.

**Ask a question** by typing it after the command — `!virgil will I find work?` — and I'll show it with the answer.
Every answer has a **🖼️ Card** button that turns it into an image to share.

## 🌅 Every day, and just for you
**`!votd`** — today's Verse of the Day. `!votd ESV` gives it in another translation; `!votd full` adds the ancient translations and a Church Father's commentary; `!votd extended` adds today's calendar too. Servers can have it posted automatically each day. Press **📅 Today's readings** under it to see that day's psalms and Bible readings for morning and evening prayer (from the Book of Common Prayer) — just for you.
**`!subscribe`** — get the Verse of the Day sent to your private messages every day · `!unsubscribe` to stop.

**Your own bookmarks**
• `!save John 3:16` — save a verse (add a note: `!save John 3:16 | got me through a hard week`)
• `!saved` — your saved verses · `!unsave 2` — remove number 2 from that list
• `!leaderboard` — who has saved the most verses

**`!plan start John`** — a reading plan: one chapter a day through a book. `!plan` shows today's chapter, `!plan status` your progress, `!plan stop` ends it. Add `!plan remind on` and I'll send you each day's chapter by private message (at 07:00 UTC, or pick a time: `!plan remind on 19:30`).

**`!memorize John 3:16`** — learn a verse by heart. I show it with some words blanked out; say it aloud, filling in the gaps, and press **Reveal** to check. **Harder** hides more words each time, until only the first letter of each word is left. Press **🔔 Remind me** and I'll send it to you by private message to practise again after 1, 3, 7, 14 and 30 days — spacing reviews out like that is what makes a verse stick. `!memorize list` shows your verses; `!memorize stop John 3:16` stops one.

**`!stats`** — how I've been used: the most-read verses and books, favourite commands and more.
**`!changelog`** — what's new with me lately.

## ⚙️ For server admins
These need the server's Administrator permission.
• `!votdsetup channel #channel` — post the Verse of the Day there every day; `!votdsetup time 04:00` sets the time (24-hour, UTC), `!votdsetup mode full` the style (`basic`, `full` or `extended`), `!votdsetup off` stops it
• `!oraclesetup channel #channel` — a daily oracle; `!oraclesetup time 12:00`, `!oraclesetup kind virgil` (or `homer`, `delphi`, `oracle`, `iching`, `hafez`, `any`), `!oraclesetup test` to try one now, `!oraclesetup off`
• `!quizsetup channel #channel` — a daily quiz question that everyone can answer all day; the answer is revealed when the next one is posted. `!quizsetup time 18:00`, `!quizsetup kind hard` (or `bible`, or a tradition like `buddhist`), `!quizsetup test` to post one now, `!quizsetup off`
• `!changelogsetup #channel` — where I announce my updates (like this channel); `!changelogsetup off` to stop
• `!changelogintro` — post this introduction, followed by the latest updates, in the updates channel (`!changelogintro fresh` first clears my earlier messages there)
• `!features` — optional extras, all off unless you turn them on: `!features react_save on` lets people bookmark a verse by reacting 📌, `!features streaks on` shows reading-plan streaks, `!features export on` lets people download their bookmarks with `!saved export`

Below are my most recent updates — new ones will appear here as they happen. Welcome! 📖
