# ScriptureBot introduction

Posted by `!changelogintro` at the top of a server's updates channel: one
Discord message per `## ` section, then the most recent changelog entries.
Each section must stay under ~3,800 characters (Discord's embed limit is
4,096), and every user-facing command must be mentioned somewhere — a test
checks both. Written for people who have never used the bot.

A server only sees the lines about what it has: a line naming only commands it has turned
off is left out, and so is one marked `<!-- texts: hindu -->` or `<!-- pack: orthodox -->`
(for lines that name no command) when that tradition or pack is off (core.for_guild).

## 👋 Hello! I'm ScriptureBot
I'm a library of sacred and ancient texts that lives in this server. I can look up a verse from the Bible in dozens of translations, show you the original Hebrew and Greek, tell you what the translators were thinking, pray the daily office with you, consult an ancient oracle — and a great deal more, across about **a thousand works** from more than a dozen traditions.

**Four ways to talk to me**
**1. Commands starting with `!`** — for example `!verse John 3:16`. This is the main way.
**2. Slash commands** — type `/` and pick from the list (for example `/verse`). They work the same, and Discord shows you what to fill in. `/verse` even suggests book names as you type.
**3. Just chat.** If you mention a Bible reference in an ordinary message — *"as it says in Romans 8:28…"* — I'll reply with the verse.
**4. Right-click any message** (on a phone: press and hold it), choose **Apps**, then **Look up verses** — I'll show you every reference in it (up to five), privately, just for you. Handy for long lists of verses, or older messages.

**Buttons**
Many of my answers come with buttons underneath. Under a Bible verse you'll see **Notes · Cross-refs · Interlinear · Card**, which dig deeper into that verse with one click (each is explained below), and **🖼️ Doré** when the passage has one of Doré's engravings. Long answers have **◀ ▶** buttons to turn the page.

**Getting help any time**
`!help` shows every command at a glance, and `!help <command>` explains one in detail — `!help verse`, `!help bcp`, `!help jewish`. The messages below are the full tour: first my library, then every command, grouped by what it's for.

## 📚 My library: the Bible and its neighbours
**The Bible** — all 66 books, King James Version by default, plus **more than 40 other translations** you can ask for by name: modern English (ESV, NASB, NKJV, NLT, NRSVCE, NABRE, CSB, the NET Bible and more), older ones (Geneva Bible, Young's Literal, Douay-Rheims, Knox), and the **original and ancient languages**: Hebrew (Westminster Leningrad Codex), Greek New Testament (Textus Receptus, Tischendorf), the Greek Old Testament (Septuagint), Latin (Vulgate), Syriac (Peshitta), Church Slavonic and even Old English. `!translations` lists them all.

<!-- texts: apocrypha -->**Apocrypha & Pseudepigrapha** — the 15 deuterocanonical books (Tobit, Judith, Wisdom, Sirach, Maccabees…) and 29 more ancient Jewish and early Christian writings: the **Book of Enoch**, **Jubilees**, the Testaments of the Twelve Patriarchs, the Psalms of Solomon, 3 & 4 Maccabees, Psalms 151–155 **2 Enoch** (the *Book of the Secrets of Enoch*), the First and Second Books of **Adam and Eve**, and the **Odes of Solomon**, early Christian hymns.

<!-- texts: apocrypha -->**New Testament Apocrypha** — 41 early Christian writings that didn't make it into the Bible: the **infancy gospels** (the *Protevangelium of James*, the story of Mary's own birth and childhood: `!verse Protevangelium 1:1`; the *Infancy Gospel of Thomas*, about Jesus as a boy), the **Acts of Pilate** or *Gospel of Nicodemus* with Christ's descent into hell, the **Acts of Paul and Thecla** and other acts of the apostles, and the **Passing of Mary**.

<!-- texts: jewish -->**The Dead Sea Scrolls** — the Community Rule, War Scroll, Damascus Document, Thanksgiving Hymns, the Habakkuk commentary and others, plus scroll copies of Isaiah, Exodus, Deuteronomy, Psalms and Daniel.

<!-- texts: lds -->**Latter-day Saint scripture** — the Book of Mormon, Doctrine and Covenants, and Pearl of Great Price.

<!-- texts: jewish -->**Jewish writers of the Greek world** — the complete works of **Josephus** (Antiquities, Jewish War…) and **Philo of Alexandria**.

<!-- texts: christian -->**The early Church** — the **Apostolic Fathers** (Clement, Ignatius, Polycarp, the Didache, the Shepherd of Hermas…), Dionysius the Areopagite, and about **400 works of the Church Fathers**, from Justin Martyr and Irenaeus through Augustine, Chrysostom and Jerome, plus early church histories. From the Middle Ages: **Bede**, **The Golden Legend**, the **Rule of St Benedict**, Thomas à Kempis's **Imitation of Christ** and Dante's **Divine Comedy** (Longfellow's translation, by canto and line: `!verse Inferno 1.1`). And three classics of Christian prayer: **The Cloud of Unknowing**, Julian of Norwich's **Revelations of Divine Love** (`!verse Julian of Norwich 5:1`) and Brother Lawrence's **Practice of the Presence of God**. From the 17th century, John Bunyan's **Pilgrim's Progress**, both parts, by section and paragraph (`!verse Pilgrim's Progress 1:1`, `!verse Pilgrim's Progress Part Two 1:1`), and **John Milton**: *Paradise Lost* by book and line (`!verse Paradise Lost 1:1-26` is its opening), *Paradise Regained* and *Samson Agonistes* (`!verse Samson Agonistes 1:80`), in the spelling of his own editions. From the 18th, the visionary **Emanuel Swedenborg**: all his theological works, among them *Heaven and Hell*, *Arcana Coelestia* and *True Christian Religion*, cited by his own section numbers (`!verse Heaven and Hell 51`, or `!verse HH 51`). And **William Blake**, who answered him: the *Songs of Innocence and of Experience* (`!verse Songs of Experience 12` is *The Tiger*), *The Marriage of Heaven and Hell* and *The Book of Thel*; **`!blake`** shows his illuminated books plate by plate, as he printed and hand-coloured them (`!blake songs`, `!blake list`), and his illustrations of other books by passage: the Book of Job (`!blake Job 38`), the Bible, Dante, *Paradise Lost* and *The Pilgrim's Progress*.

## 📚 My library: other traditions
<!-- texts: jewish -->**Rabbinic & mystical Judaism** (from Sefaria) — the **Mishnah**, **Tosefta**, **Babylonian** and **Jerusalem Talmud**, the Targumim (Aramaic Bible translations), **Midrash Rabbah** and other midrashim, **Maimonides** (Mishneh Torah, Guide for the Perplexed), and Kabbalah: the **Zohar**, Sefer Yetzirah, the Bahir and the Tanya; and anything else Sefaria has in English (`!verse Rashi on Genesis 1:1`). `!help jewish` shows how to cite each.

<!-- texts: islamic -->**Islam** — the **Quran** in 52 English translations (Abdel Haleem's by default; `!verse Quran 2:255 arberry` for another, or name several to compare) and ten **hadith** collections, including Sahih al-Bukhari and Sahih Muslim. `!help islamic` has the details. From the Persian poets: 43 poems from the **Divan of Hafiz** (`!verse Hafiz 1`), Rumi's **Masnavi** (its stories, by book and story: `!verse Masnavi 1.0` is the song of the reed flute) and Omar Khayyam's **Rubaiyat** (`!verse Rubaiyat 1:12`).

<!-- texts: classical -->**The Greek and Roman world** — Homer (*Iliad*, *Odyssey*), Virgil's *Aeneid*, Hesiod (*Theogony*, *Works and Days*, *Shield of Heracles*), Ovid, the Homeric and Orphic Hymns; philosophy from **Plato** and **Aristotle** to the later Platonists (Plutarch, Plotinus, Porphyry, Iamblichus, Proclus) and the emperor Julian; the Stoics **Marcus Aurelius** (*Meditations*) and **Epictetus** (*Enchiridion*); the **Hermetic** writings (Corpus Hermeticum, the Emerald Tablet); and oracles (Delphic maxims, the Chaldaean Oracles, the Golden Verses of Pythagoras). And about **600 more Greek and Latin works** in English from the Perseus Digital Library: the tragedies of Aeschylus, Sophocles and Euripides; Aristophanes and Plautus; the historians Herodotus, Thucydides (`!verse History of the Peloponnesian War 2.40`), Xenophon, Polybius, Livy, Tacitus and Suetonius; Plutarch's *Lives* and *Moralia*; Cicero, Caesar, Lucretius, Ovid, Horace, Lucian, Pausanias and the Greek orators. `!books` → Classical → The Perseus Library lists them by author.

<!-- texts: gnostic -->**Gnostic & related** — the **Gospel of Thomas**, 114 sayings of Jesus (`!verse Gospel of Thomas 77`), the **Nag Hammadi library** (41 texts), the Mandaean *Ginza Rba* and *Book of John*, and Manichaean psalms.

<!-- pack: comparative -->**Further afield** — eight works of the **Bahá'í** faith, including the Kitáb-i-Aqdas; the Norse **Poetic Edda**; and the **ancient Near East**: the Epic of Gilgamesh, the Babylonian creation epic **Enuma Elish** (`!verse Enuma Elish 4`), the Canaanite Baal Cycle, the Egyptian Book of the Dead and Hymn to the Aten, the Wisdom of Ahikar, and the pre-Islamic Arabic Mu'allaqat poems.

Browse all of it with `!books`, or let me pick something at random with `!discover`.

## 📜 My library: the Middle Ages
<!-- texts: arthurian -->**King Arthur and the Grail** — the medieval Arthurian legend in English: Sir Thomas **Malory**'s *Le Morte d'Arthur* by book and chapter (`!verse Malory 1.5` is the sword in the stone); the French romances of **Chrétien de Troyes** (*Erec*, *Cligès*, *Yvain*, *Lancelot*); the Grail stories (Wolfram's **Parzival**, the *High History of the Holy Graal*, the *Quest of the Holy Grail* from the great French Lancelot-Grail cycle); **Sir Gawain and the Green Knight** (`!verse Gawain 5`); *Tristan and Iseult*; the lays of **Marie de France**; shorter romances (*Morien*, *Sir Launfal*, *Libeaus Desconus*, *Tyolet*, the *Adventures at the Tarn Wadeling*); and the old chronicles that first told of Arthur: Nennius, **Geoffrey of Monmouth** (`!verse Geoffrey 9.1`), Wace and Layamon. Some are also here in their own Middle English, cited by line: *Sir Gawayn and the Grene Knyȝt* (`!verse Gawayn 1`), *Sir Tristrem*, *Of Arthour and of Merlin* and *Lancelot of the Laik*. `!books` → Arthurian legend lists them all.

<!-- texts: english -->**Medieval English poetry** — the poems of the Middle Ages in the English they were written in (Middle English: older spellings, and the old letters þ "th" and ȝ "y/gh"). **Chaucer** — the *Canterbury Tales*, *Troilus and Criseyde*, the *Parliament of Fowls* and the rest — and the poets who followed him (Henryson's *Testament of Cresseid*, Lydgate, Hoccleve); **Piers Plowman**; *Pearl*, *Cleanness* and *Patience* by the Gawain poet; Gower's *Confessio Amantis*; romances like *Sir Orfeo*, *Havelok* and *King Horn*; the forty-odd poems of the **Auchinleck manuscript** (about 1335), *Sir Beues of Hamtoun* and *Guy of Warwick* among them; Barbour's *Bruce* and Blind Hary's *Wallace* in Scots, and the later Scots poets Sir David Lyndsay and Alexander Montgomerie; mystery plays (the whole N-Town cycle, `!verse Ludus Coventriae 15:1`) and lyrics; the Tudor poets John Skelton and Stephen Hawes; and Spenser's *Faerie Queene*. Most of the poems are quoted by their line numbers: `!verse Sir Orfeo 233` shows the passage holding line 233 and `!verse Sir Orfeo 233-260` a stretch of lines; a poem in books takes book:line, as `!verse Troilus 3:1`. `!books` → Medieval English poetry lists them all.

<!-- texts: shakespeare -->**Shakespeare** — all 38 plays, the Sonnets and the long poems, in the Folger Shakespeare Library's edition (modern spelling). The plays are quoted the way everyone quotes them, by act, scene and line: `!verse Hamlet 3.1.64` is "To be or not to be", `!verse Macbeth 5.5` the whole of Act 5, Scene 5, and `!verse Romeo and Juliet prologue` the Prologue. A sonnet by its number: `!verse Sonnets 18`. His *Julius Caesar* is `Shakespeare: Julius Caesar` (or `JC`), as plain "Julius Caesar" is Suetonius's life of him. `!books` → Shakespeare lists them all. `!shakespeare` casts lots, as `!virgil` does with Virgil: dice for the play (numbered in the order of the 1623 First Folio), the act, the scene and the line, and the line they land on is your answer (`!shakespeare will it rain?`), with 📜 to read it in its scene; `!sonnet` gives a sonnet at random, `!sonnet 18` that one, and `!sonnet venus` (or `lucrece`, `phoenix`) stanzas of his other poems. Under a scene that John Boydell's Shakespeare Gallery (1789–1805) had painted, **🖌️ Boydell** shows the painting.


## 📚 My library: Asia and the wider world
<!-- texts: hindu -->**Hinduism** — the four **Vedas**; the **Bhagavad Gita** (every verse, in Shri Purohit Swami's translation: `!verse Gita 2:47`; or name one of five other translations, or the great commentaries of Shankara and Ramanuja: `!verse Gita 2:47 sivananda shankara`, `!help gita`); twelve **Upanishads**, the philosophical heart of the Vedas — the Isa, Katha and Kena, and in Max Müller's translation the Chandogya, Brihadaranyaka, Mundaka, Taittiriya and more (`!verse Chandogya Upanishad 6.8:7`: "thou, O Svetaketu, art it", the famous "Thou art that"); the **Yoga Sutras** of Patanjali (`!verse Yoga Sutras 1:2`); and the **Laws of Manu**.

<!-- texts: sikh -->**Sikhism** — the whole **Guru Granth Sahib**, the Sikh scripture, cited by page (*Ang*) and line as Sikhs cite it (`!verse Guru Granth Sahib 1:1`), and the **Japji**, Guru Nanak's morning prayer that opens it, by stanza (`!verse Japji 1`); Manmohan Singh's translation too (`!verse Guru Granth Sahib 1:1 manmohan`); the **Dasam Granth**, the writings of Guru Gobind Singh (`!verse Dasam Granth 1`); and the **Vaaran of Bhai Gurdas** (`!verse Bhai Gurdas 1:1`). `!help sikh` shows how to cite them.

<!-- texts: jain -->**Jainism** — the oldest Jain scriptures: the **Akaranga Sutra** (the conduct of monks, cited book.lecture.lesson: `!verse Akaranga Sutra 1.1.1`), the **Sutrakritanga**, the **Uttaradhyayana Sutra** (Mahavira's last teachings) and the **Kalpa Sutra** (the lives of the Jinas).

<!-- texts: buddhist -->**Buddhism** — the whole **Pali Canon** of the earliest Buddhist scriptures, in Bhikkhu Sujato's translation, cited as Buddhists cite it (`!verse MN 1`, `!verse SN 56.11`, the first sermon; `!help buddhist`); the **Dhammapada** (the Buddha's sayings in verse: `!verse Dhammapada 183`), the **Sutta Nipāta** (some of the oldest teachings), all 547 **Jataka** tales of the Buddha's former lives (`!verse Jataka 7`), the **Questions of King Milinda**, and two great Mahayana sutras, the **Diamond Sutra** and the **Lotus Sutra**.

<!-- texts: chinese -->**China and Japan** — the **Tao Te Ching** and the **Zhuangzi** (`!verse Zhuangzi 2`, the butterfly dream is at its end); Confucius's **Analects** (`!verse Analects 2.4`), **Mencius** (by book, part and chapter: `!verse Mencius 6.1.2`), the **Great Learning** and the **Doctrine of the Mean**; the **I Ching**; and Shinto's sacred histories, the **Kojiki** and the **Nihongi**.

<!-- pack: comparative -->**Persia, the Americas and old Europe** — the **Zoroastrian** scriptures: the **Gathas** (Zarathustra's own hymns), the **Yasna**, the **Yashts**, the **Vendidad** and the **Bundahishn**, the Zoroastrian account of creation; the Maya **Popol Vuh**; the Finnish **Kalevala**; and the Welsh **Mabinogion**.

<!-- pack: comparative -->`!search` and `!theme` know each of these as a tradition: `in:sikh`, `in:jain`, `in:shinto`, `in:zoroastrian`, `in:mesoamerican`, `in:finnish`, `in:celtic`.

## 📖 Reading scripture
**`!verse`** (or `!v`) is my main command.
• `!verse John 3:16` — one verse · `!verse Genesis 1:1-5` — a range · `!verse John 7:53-8:11` — across chapters · `!verse Psalm 23` — a whole chapter, in pages
• `!verse John 3:16 ESV` — in another translation · `!verse John 3:16 KJV ESV NKJV` — several side by side
• `!verse` — a random verse · `!verse Proverbs` — random from one book · `!verse bible nt` — random from the New Testament
<!-- pack: comparative -->• Other traditions work the same way: `!verse Quran 2:255`, `!verse Enoch 1:9`, `!verse Berakhot 2a`, `!verse Gilgamesh 11`, `!verse Rig Veda 10.121:9`, `!verse Republic 514a` (Plato by the page-and-section numbers printed in every edition, or a stretch: `!verse Republic 514a-515c`), `!verse Iliad 6.440` (Homer by book and line)
Abbreviations are fine (`Jn`, `1 Cor`, `Ps`). Bible verses come with the four study buttons, and any passage Gustave Doré engraved or William Blake painted gets a **🖼️ Doré** or **🎨 Blake** button too. Under a passage from any of my texts, **◀ Previous** and **Next ▶** read on and **📖 Whole chapter** opens its chapter.
A **🖌️** button shows the pictures of the old illustrated editions wherever a passage has one: Beardsley's *Morte d'Arthur*, Crane's *Faerie Queene*, the Boydell Gallery's paintings of Shakespeare, and the Aesop, La Fontaine and Grimm pictures under `!fable` and `!tale`.

**`!fable`** — fables from around the world: Aesop's (313 of them, in Townsend's translation), the Roman fable-writer Phaedrus, the French poet La Fontaine's in English verse, and *The Talking Beasts*, a book of the world's fables (Bidpai's from old India, the Russian Krylov's, African, Chinese and more). `!fable` gives one at random from any of them, `!fable fox` one with the fox in its title, `!fable lion and mouse` one by name, `!fable 12` Aesop's by number, `!fable la fontaine` (or `phaedrus`, `bidpai`, `krylov`…) one from that collection, `!fable list` Aesop's titles and `!fable collections` all of them. **🖼️ Card** makes a picture of a short fable you can save or share, and **🖌️** shows the fable's pictures from the old illustrated books: Gustave Doré's for La Fontaine; Arthur Rackham's, Walter Crane's and Milo Winter's for Aesop.

**`!dore`** — Gustave Doré's famous engravings for the Bible (the Apocrypha included), the *Divine Comedy* and *Paradise Lost*, each tied to the verse or line it shows: `!dore Genesis 11` lists that chapter's engravings with the verse of each, `!dore Inferno 3:82` shows Charon's boat, `!dore Paradise Lost 1` Satan's fall; `!dore` alone shows one at random, and `!dore list` what there is.

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

**`!card John 3:16`** — turns a verse into a parchment-style image to share (`!card John 3:16 ESV NKJV` stacks translations). The **Card** button does the same.

## 🎓 Study tools
**`!notes John 3:16`** — the NET Bible's translators' notes: why a word was translated the way it was, background on the passage, and where ancient manuscripts disagree. Small numbers in the verse show which word each note is about. (Also the **Notes** button.)
**`!xref John 3:16`** — related verses elsewhere in the Bible, from the classic *Treasury of Scripture Knowledge*. (Also the **Cross-refs** button.)
**`!quoted Isaiah 53:5`** — where the New Testament quotes the Old (or the Book of Enoch and other ancient writings), shown side by side, each labelled as a direct quotation or a looser parallel.
**`!story flood`**: the same story as different traditions tell it, side by side. The Flood in Genesis, the Epic of Gilgamesh, Ovid, the Quran and the Maya Popol Vuh; also `!story creation`, `humans` (the first people, made from earth), `tower`, `underworld`, `ages` (the golden age and after), `end` and `christ` (pagan texts early Christians read as foretelling Christ, each with the Church Father who read it so). Choose one from the menu to read it in full; `!story` alone lists them.
**`!cloud Ecclesiastes`** — a book's most distinctive words drawn as a picture, the bigger the word the more it sets that book apart from the rest of its collection: Ecclesiastes is *vanity*, *vexation* and *labour under the sun*, the Song of Solomon *beloved*, *myrrh* and *lilies*. Works for any book in the library (`!cloud Revelation`, `!cloud Tao Te Ching`).
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
• `!measure 300 cubits` — Bible weights, measures and money in today's terms: how long a cubit was, how heavy a talent, what a penny was worth (a day's wage). `!measure Genesis 6:15` converts every measurement in a verse — there, the size of Noah's ark. `!measure` alone lists them all
• `!kings` — every king of Israel and Judah from Saul to Zedekiah, drawn as a chart: each reign a block as long as the Bible says it lasted, coloured by the Bible's own verdict on it ("did that which was right" or "did evil"). `!kings Hezekiah` shows one king with the verses

**`!harmony feeding five thousand`** — one event in the life of Jesus as each Gospel tells it, side by side, so you can see at a glance what Matthew, Mark, Luke and John each include or leave out. It follows a classic *harmony of the Gospels* (A. T. Robertson's, 1922), which puts the whole story in order in 185 events, from the birth of John the Baptist to the Ascension. Find an event by words from it, by a verse (`!harmony Mark 6:41`) or by its number (`!harmony 72`). Buttons read each Gospel's account in full and step to the event before or after, so you can walk through the whole life of Christ. `!harmony` alone picks an event at random.

## 🗺️ People and places
**`!who Ruth`** — who someone in the Bible was: a short description, their family (parents, husband or wife, children, brothers and sisters), their tribe, where they were born and died, and every verse that names them. When several people share a name — there are seven Marys and a dozen Johns — I'll list them so you can pick the one you mean (`!who Mary`). The menu under the card opens any of their relatives, so you can follow a family tree: Ruth → her son Obed → his son Jesse → his son David.

**`!tree David`** — a family tree, drawn as a picture: the person in the middle with their brothers and sisters, husband or wives, and children, their parents and grandparents above, and their line of fathers climbing up from there (great-grandfather, 2× great-grandfather…) with a note of how far back it goes ("… 25 more generations, back to Adam"). Big families are cut short to the best-known names (David had more than twenty children).
**`!tree Abraham to David`** — every generation from one person down to another, drawn as a chart: Abraham, Isaac, Jacob, Judah… down to David, fourteen generations. Try `!tree Adam to Jesus` for the whole of the Bible's genealogies, 65 generations. The names can go in either order.

**`!place Bethel`** — a place in the Bible on a map: the place marked in red with the towns, seas and regions around it named so you can get your bearings, a small map of the whole Bible world in the corner showing where you are, and a scale in kilometres and miles. Under it: what the place was, who was born or died there, and every verse that names it. Where nobody is quite sure where a place was, the map says so. Try `!place Sea of Galilee`, `!place Rome` or `!place Ur`.

**`!journey paul 2`** — a great journey drawn on a map: every stop numbered and joined by arrows, with a list of what happened at each one and the verse that tells it. From the Bible: Abraham's journey from Ur, the Exodus from Egypt to Jericho, Paul's three missionary journeys (`!journey paul 1`, `paul 2`, `paul 3`), Paul's voyage and shipwreck on the way to Rome (`!journey rome`), the flight into Egypt, and Jonah's. `!journey` alone lists them.
<!-- texts: english -->• `!journey canterbury` — Chaucer's pilgrims on the road from Southwark to Canterbury, at the towns the *Canterbury Tales* name as they ride by.
<!-- texts: classical -->• `!journey odyssey` — Odysseus's ten years' wandering home from Troy; nobody knows where Homer's places were, so the map follows the ancient writers who placed them, and says who · `!journey aeneid` — Aeneas's voyage from Troy to the mouth of the Tiber.

## 🎵 Hymns and psalms to sing
**`!hymn amazing grace`** — a hymn's words, who wrote them and the tune, and the Bible passages it draws on. Search by title, first line, a line you remember from the words, a topic (`!hymn christmas`) or a passage (`!hymn Psalm 23` finds hymns based on it). `!hymn` alone picks one at random. Two buttons sit under each hymn:
<!-- pack: church -->• **▶️ Play the tune** — the tune once through, in four parts on an organ, to play right in Discord.
<!-- pack: church -->• **📖 Read the passages** — the Bible verses behind the hymn.
<!-- pack: church -->• **🇬🇧 English** — on many Latin chants: a published English translation (the Prayer Book's, Neale's, Caswall's…).
<!-- pack: church -->• **🎤 Sung** — on the Latin chants: sung in Latin by a synthesised choir.
<!-- pack: church -->• **🎼 Score** — the chant in square notes, as chant books print it.
**`!chant pater noster`** — a Latin chant sung, straight away; `!chant` alone sings a random one.
**`!midi amazing grace`** — just the tune, straight away: I skip the words and post the audio. It searches the same way as `!hymn`; `!midi` alone plays a random one.
**`!hymnday`** — the hymn of the day, chosen for the Church year and the same for everyone: on a great feast that feast's hymn (*Veni Creator* at Pentecost, *Vexilla Regis* on Good Friday), in Advent, Lent or Eastertide one of the season's hymns, and the rest of the year an English hymn, a Latin chant and a Sacred Harp song in turn. `!hymnday 2026-12-25` shows another day's. Server admins can have it posted every morning with **`!hymndaysetup channel #hymns`** (`time 08:00` in UTC, `test`, `off`).
**`!hymnlist`** — the whole hymnal by title: how many hymns are in each section, then `!hymnlist all` (every title, a page at a time), `!hymnlist chant` (just the Latin chant), `!hymnlist chant sequences`, or `!hymnlist veni` (titles with that word). Pick one from the list to open it.
<!-- pack: church -->About 290 public-domain hymns and carols, from the Open Hymnal Project and Hymnary.org — and **720 ancient Latin hymns and chants in Gregorian chant**, with their Latin words and the chant melody to play: the hymns of the Church's daily prayer (*Te lucis ante terminum*, *Veni Creator Spiritus*, *Vexilla Regis*, *Pange lingua*), the great sequences (*Dies irae*, *Stabat Mater*, *Victimae paschali laudes*), the *Te Deum*, and the antiphons *Salve Regina*, *Regina caeli* and *Ubi caritas*. And **the whole Sacred Harp**, the American shape-note songbook: 550 songs, each sung in four parts with its words, such as *Idumea*, *Northfield* and *Babylon Is Fallen* (`!hymn Idumea`, `!hymnlist harp`; `!hymn harp` for a random one).

**`!metrical 23`** — a psalm from the **Scottish Metrical Psalter** of 1650: all 150 Psalms rewritten in rhyme and a steady beat so a whole congregation could sing them, still sung in Scottish churches today (it gave us *The Lord's my shepherd, I'll not want*). I show the psalm with its stanzas numbered by Bible verse, and the tune it's traditionally sung to:
<!-- pack: church -->• **▶️ Play the tune** — one verse of the tune in four parts on an organ; every stanza is sung to it.
<!-- pack: church -->• **The tune menu** — play the psalm to any other tune in the same rhythm, since any of them fits the words.
<!-- pack: church -->• **📖 Read in the KJV** — the same psalm in ordinary prose, to compare.
<!-- pack: church -->• **Second version** — some psalms (like Psalm 100) have two versions in the Psalter, and this switches between them. Ask for one directly with `!metrical 100b`.
<!-- pack: church -->Long psalms have buttons to turn the page, or ask for some verses: `!metrical 119:105-112`. Psalm 119 shows its 22 parts under their Hebrew letters (Aleph, Beth, Gimel…), with a menu to jump between them; ask for one by name with `!metrical 119 nun`. You can also search the words (`!metrical shepherd`), list every psalm sung to a tune (`!metrical crimond`), or get a random one with `!metrical`. `!psalm 23 sing` does the same as `!metrical 23`.

## 🎻 Folk tales and ballads

<!-- texts: ballads -->**`!ballad`** — the old ballads of England and Scotland, all 305 that the scholar Francis James Child gathered in the 1800s (*The English and Scottish Popular Ballads*), often in several versions sung in different places: `!ballad` at random, `!ballad 84` by Child's number (*Barbara Allen*), `!ballad 12B` the second version of a ballad, `!ballad matty groves` by title or by a name it's sung under today, `!ballad list` all the titles. **🔀** moves to the next version, **▶️ Play the tune** plays a melody it was sung to (press **Next tune** for others), and **📺 Recording** opens someone singing it on YouTube.

<!-- texts: ballads -->**`!tale`** — one of the fairy tales the Brothers Grimm gathered in Germany in the 1800s, all 200 of them and ten short legends, in Margaret Hunt's well-known translation: `!tale` at random, `!tale wolf` one with the wolf in its title, `!tale rapunzel` by name (the names they're known by today work too: `!tale sleeping beauty` finds *Briar-Rose*), `!tale 12` by number, `!tale list` all the titles. Long tales turn their pages with ◀ ▶, and **🖌️** shows Walter Crane's and Arthur Rackham's pictures for the tale, where they drew it.

<!-- texts: ballads -->**`!reynard`** — *Reynard the Fox*, the great medieval story of the cunning fox who tricks the Wolf, the Bear and the Cat at the Lion's court and talks his way out of the gallows, in William Caxton's English of 1481 with modern spelling: `!reynard` starts at the beginning, `!reynard 12` opens a chapter, `!reynard tybert` finds the chapter about the Cat, and `!reynard list` shows them all (or `!tale reynard 12`, and `/tale`). **⏮** and **⏭** move between chapters, and each chapter ends with short notes explaining its old words.

<!-- texts: christian -->**`!physiologus`** — the *Physiologus*, the early Christian book of beasts behind every medieval bestiary, from the 2nd–4th century: what each animal does, and what it teaches about Christ and the soul (the pelican reviving its young with its own blood, the lion waking its cubs on the third day). `!physiologus` gives a beast at random, `!physiologus pelican` one by name, `!physiologus list` all 33 (or `!tale physiologus pelican`, and `/tale`).

## ⛪ Prayer, liturgy & the Church
**`!today`** — what's happening today across traditions: the Catholic, Anglican and Orthodox calendars (feasts, saints, seasons, Orthodox fasting), the Hebrew date and Jewish holidays, and the Islamic date and holidays. Narrow it down with `!today catholic`, `!today orthodox`, `!today jewish`, `!today islam`; add a date with `!today 12-25`.

**`!salah London`** — today's five Muslim prayer times for any city (Fajr at dawn, Dhuhr, Asr, Maghrib at sunset and Isha at night), worked out the way that country's Muslim authorities do. Add the country if a city name is ambiguous: `!salah Cairo, Egypt`.

<!-- pack: protestant -->**The Daily Office** — Morning and Evening Prayer from the Book of Common Prayer (the Canadian 1962 Prayer Book, with Coverdale's Psalter):
• `!bcp` — today's psalms, two readings and collect, for morning or evening depending on the time · `!bcp morning`, `!bcp evening`, `!bcp 2026-12-25`
• `!mp` / `!ep` — just the readings for Morning or Evening Prayer
• `!psalm` — today's appointed psalms (`!psalm ep` for the evening ones)
• `!psalm 110 chant` — any psalm chanted in Latin to a Gregorian psalm tone, the way monks sing the Office, by the bot's synthesised choir, with the Latin and the Douay-Rheims English to follow. Add `organ` to hear the melody on the organ instead. Psalm 119 is sung in its 22 sections: `!psalm 119 chant beth`.
• `!collect` — the Collect (short prayer) of the day
• `!prayer` — a random prayer from the 1662 Prayer Book; `!prayer st michael`, `!prayer memorare`, `!prayer anima christi`… — a traditional prayer by name, in English and Latin, sung where it's also a chant; Orthodox prayers too, with their Greek (`!prayer jesus prayer`, `!prayer trisagion`); `!prayer list` for them all
• `!vov` — a prayer of the English Puritans, from the collection *The Valley of Vision*: `!vov` at random, `!vov penitence` on a theme, `!vov topics` to browse them, `!vov 37` by number

**`!rosary`** — pray the Rosary, a page at a time: the opening prayers, then five decades (an Our Father, ten Hail Marys and a Glory Be), each on one of the day's *mysteries*, events from the lives of Jesus and Mary, with its Bible passage to think on, then the closing prayers. ◀ ▶ move through it, and the *Ave Maria* comes sung. It picks the day's set (the Joyful on Mondays, the Luminous on Thursdays…), or ask for one: `!rosary sorrowful`.

**`!angelus`** — the Angelus, the short prayer said morning, noon and evening in memory of the angel's message to Mary, in English and Latin, with the *Ave Maria* sung. In Eastertide the *Regina Cæli* ("O Queen of heaven, rejoice!") takes its place, as the Church directs. Admins: **`!angelussetup channel #prayer`** posts it every day at noon UTC, or at the traditional three hours with `time 06:00 12:00 18:00`.

**`!creed`** — the Apostles', Nicene and Athanasian Creeds in traditional English: `!creed nicene`, with `latin` or `greek` for the original (`!creed nicene greek`) or `parallel` for all at once.

<!-- pack: catholic_teaching -->**Catholic teaching**
• `!ccc 1` — a paragraph of the *Catechism of the Catholic Church* (`!ccc 1700-1715` for a range, `!ccc random`)
• `!canon 1` — a canon of the Code of Canon Law
• `!summa I.2.3` — an article of St Thomas Aquinas's *Summa Theologica* (Part I, Question 2, Article 3), or `!summa random`

## 😇 Saints and the Desert Fathers
<!-- pack: saints -->**`!saint`** — the saint of the day on the traditional calendar, from *Butler's Lives of the Saints*, with a **📖 Golden Legend** button when the medieval *Golden Legend* tells their story too. Look up any saint by name (`!saint George`, `!saint Christopher`; if there are several, like the two Augustines, I'll ask which) or by day (`!saint 25 July`). Admins: `!saintsetup channel #saints` posts the day's saint every morning.

<!-- pack: saints -->**`!desert`** — a saying of the Desert Fathers, the monks and nuns who went out into the Egyptian desert in the 4th and 5th centuries, from E. A. Wallis Budge's *Paradise of the Holy Fathers*. `!desert` gives one at random; `!desert Poemen` one by or about a particular father (`!desert fathers` lists them all, with how many sayings each has); `!desert topics` shows Budge's chapters, like *Of Humility* or *Of Patient Endurance*, and `!desert humility` picks from one; `!desert 1:303` finds a saying by its number, and `!desert anger` one with those words in it. The **🎲 Another** button draws again from the same father or topic. Also called `!apophthegm`, after the Greek name for these sayings.

## ☦️ The Orthodox Church
<!-- pack: orthodox -->The prayers, hymns and holy images of the Eastern Orthodox Church. (Its calendar and fasting days are in `!today orthodox`, and its daily prayers in `!prayer`, with their Greek: `!prayer jesus prayer`, `!prayer trisagion`, `!prayer list`.)

**`!troparion`** — the Orthodox hymns of the day: every day the Orthodox Church remembers its saints and feasts with a short hymn, the *troparion*, and a second, the *kontakion*. I give each, with the *tone* (one of eight melodies) it's sung to, from the Orthodox Church in America. Another day: `!troparion 12-25`. Admins: **`!troparionsetup channel #chan`** posts them every morning.

**`!icon`** — an Orthodox icon with what it shows: on one of the Great Feasts (Christmas, Theophany, Pascha, the Transfiguration…) that feast's icon, otherwise one of the famous icons, like Rublev's *Trinity* or the *Theotokos of Vladimir*. Ask for one: `!icon trinity`, or `!icon list` for them all.

**`!divineliturgy`** — the Divine Liturgy of St John Chrysostom, the service most Orthodox churches celebrate every Sunday, a page at a time in an 1866 English translation: the spoken parts, with what the priest and deacon do in italics. ◀ ▶ turn the pages, and a menu jumps to any part (the Creed, the Cherubic Hymn, Holy Communion…), or ask for one: `!divineliturgy creed`.

## ✡️ Jewish learning
<!-- pack: jewish_learning -->Jews around the world study the same texts each day, in cycles that run through whole books. These come from Sefaria's learning calendar, and every text opens in the bot.

**`!parsha`** — this week's Torah portion: the section of the Five Books of Moses read in synagogue on Shabbat, so that the whole Torah is read in a year. You get what it's about, its seven readings and the passage from the Prophets read with it (the *Haftarah*). Another week: `!parsha 12-25`.

**`!dafyomi`** — today's *Daf Yomi*, "page of the day": one double-sided page of the Talmud a day, finishing all 2,711 in about seven and a half years. I show the page's text.

**`!learning`** — all of the day's cycles at once: the Torah portion, Daf Yomi, a Mishnah, Maimonides, a chapter of the Bible, a passage of Jewish law and more, each with the command to read it. Admins: **`!learningsetup channel #chan`** posts it every morning.

## 🎲 Games
**Play a game:** `!quiz` shows a verse and four buttons — which book is it from? `!quiz hard` mixes traditions (Proverbs? the Quran? the Norse Edda?), and you can quiz yourself on one tradition: `!quiz buddhist`, `!quiz chinese`, `!quiz hindu`, `!quiz classical`, `!quiz norse` and more. `!quiz leaderboard` shows this server's top scorers — this week (it starts fresh every Monday) and of all time. Everyone gets one guess; the answer is revealed after a minute. Get three or more right in a row and you'll see your 🔥 streak.

**Versle**, the daily verse puzzle: `!versle` shows today's verse, the same one for everyone, and asks where in the Bible it is. Press **✍️ Guess** and type a verse; you get six tries. After each one I tell you privately how close you were: 🟩 right, 🟨 within three, ⬛ further off, for the book, the chapter and the verse, plus which way to go ("later in the Bible, by 5 books"). When you're done, **📣 Share my result** shows the channel your squares without giving the answer away. `!versle stats` shows your record and streak. A new verse comes at midnight UTC.

**Who Am I?** `!whoami` picks a mystery person from the Bible and gives you one clue to start: how many verses name them and where in the Bible. Press **💡 Next clue** for an easier one: their family, where they were born and died, what their name means, a verse about them with the name hidden, the names of their relatives, and at last the first letter. Anyone in the channel can press **✍️ Guess** (one guess per clue each), and the first right answer wins. Press **🏳️ Give up** to see who it was.

## 🔮 Oracles
<!-- pack: divination -->For centuries people have sought guidance by opening a revered book at random or casting lots. I keep several of those traditions alive — for reflection and fun:
• `!virgil` — the *Sortes Vergilianae*: a random line from Virgil's *Aeneid*, as people did in the Middle Ages
• `!homer` — I roll three dice and give you the matching answer from the *Homeromanteion*, an oracle preserved on an ancient Egyptian papyrus
• `!delphi` — one of the maxims carved at the Temple of Apollo at Delphi
• `!oracle` — a saying from the Delphic oracles, the *Chaldaean Oracles* or the Golden Verses of Pythagoras
• `!sortesbiblicae` (or `!bibliomancy`) — the Bible opened at random
• `!iching` — I toss three coins six times to build a hexagram from the *I Ching*, the Chinese Book of Changes, and read you its Judgment and Image; any "changing" lines get their own readings and turn it into a second hexagram
• `!hafez` — *Fāl-e Hāfez*, a custom still alive in Iran: hold a wish or question in mind and open the poems of Hafiz, the great 14th-century Persian poet, at random; the poem you find is your answer
• `!rumi` — the same with the *Masnavi* of Rumi, the 13th-century Sufi poet: I open it anywhere and read you a few couplets, with the story they come from
• `!tarot` — draw a card from the Rider tarot of 1909, in Pamela Colman Smith's pictures, with what it means in A. E. Waite's own words (upside down if it falls reversed). `!tarot three` lays past, present and future, `!tarot celtic` Waite's ten-card Celtic Cross, and `!tarot the tower` shows any card
<!-- pack: divination -->• `!planets` — where the Sun, the Moon and the planets are in the zodiac right now (the western, tropical zodiac), worked out from NASA's own planetary tables, with the day's events to the minute: planets in exact aspect, a planet entering a new sign or turning retrograde, the Moon's quarters. `!planets 2026-12-25` for any day from 1900 to 2049. For what the old astrologers made of it, my library has Ptolemy's *Tetrabiblos* and William Lilly (`!verse Lilly 7` is his chapter on Mars)
<!-- pack: divination -->• `!horoscope` — the day's significant events in the sky, and only those: a planet turning retrograde, the slow planets meeting or changing sign, a new or full moon, the main aspects. Each comes with a short note on what it means and which signs feel it most, in the old astrologer Sepharial's words where he wrote on it, otherwise written by AI from the real sky and labelled so. `!horoscope leo` gives the ones that touch your sign. Admins: `!astrosetup channel #astrology` posts `!planets` and `!horoscope` there every morning

**Ask a question** by typing it after the command — `!virgil will I find work?` — and I'll show it with the answer.
<!-- pack: divination -->Every answer has a **🖼️ Card** button that turns it into an image to share.

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
• `!oraclesetup channel #channel` — a daily oracle; `!oraclesetup time 12:00`, `!oraclesetup kind virgil` (or `homer`, `delphi`, `oracle`, `iching`, `hafez`, `rumi`, `any`), `!oraclesetup test` to try one now, `!oraclesetup off`
• `!quizsetup channel #channel` — a daily quiz question that everyone can answer all day; the answer is revealed when the next one is posted. `!quizsetup time 18:00`, `!quizsetup kind hard` (or `bible`, or a tradition like `buddhist`), `!quizsetup test` to post one now, `!quizsetup off`
• `!verslesetup channel #channel` — post each day's Versle puzzle in a channel, with yesterday's answer and how many people solved it. `!verslesetup time 07:00`, `!verslesetup test`, `!verslesetup off`
• `!changelogsetup #channel` — where I announce my updates (like this channel); `!changelogsetup off` to stop
• `!changelogintro` — post this introduction, followed by the latest updates, in the updates channel (`!changelogintro fresh` first clears my earlier messages there)
• `!serversetup` (or `/setup traditions`) — tell me what this server is for: which traditions (Christianity, Judaism, Islam, Buddhism…), which church (and for Anglicans, how high church), and whether you'd like oracles and divination. I put away the commands and texts you won't use, so they stop cluttering `!help`, the `/` menu and searches; nothing is deleted, and you can change your mind any time
• `!packs` — what this server has, and switch one thing on or off: `!packs divination off`, `!packs saints on`, or a tradition's texts, `!packs hindu on`
• `!features` — optional extras, all off unless you turn them on: `!features react_save on` lets people bookmark a verse by reacting 📌, `!features streaks on` shows reading-plan streaks, `!features export on` lets people download their bookmarks with `!saved export`

Below are my most recent updates — new ones will appear here as they happen. Welcome! 📖
