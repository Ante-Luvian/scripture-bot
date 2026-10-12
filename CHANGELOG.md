# ScriptureBot changelog

What's new, newest first. When the bot starts after an update, she posts any
entries a server hasn't seen yet to that server's changelog channel
(`!changelogsetup #channel`); anyone can read recent ones with `!changelog`.

Format: one `## YYYY-MM-DD · Title` section per notable change (new commands,
new features, fixes users would notice), with `- ` bullets written for users.
Once an entry has been announced, don't change its heading — the heading is
how the bot remembers what it has already posted.

Write every bullet for someone who has never seen the code or this project's
history (see CLAUDE.md): one change per bullet; say in plain words what's new
or what was wrong; give an example command to try; explain any term a casual
reader wouldn't know.

## 2026-10-12 · The big update: notes, study buttons, new oracle & more
- 📝 **New command: `!notes`.** The NET Bible comes with thousands of notes from its translators explaining why a word was translated the way it was, what the original Greek or Hebrew says, and where ancient manuscripts disagree. Type `!notes John 3:16` to see them for any Bible verse (or up to 5 verses at once, like `!notes Genesis 1:1-3`). Small numbers in the verse show which word each note is about.
- 🔘 **Buttons under Bible verses.** When you look up a Bible verse with `!verse`, four buttons now appear underneath: **Notes** shows the translators' notes above, **Cross-refs** lists related verses elsewhere in the Bible, **Interlinear** shows the verse word by word in the original Greek or Hebrew, and **Card** turns the verse into an image you can share. Each button works once per message.
- 📖 **New oracle: `!sortesbiblicae`** (or the shorter `!bibliomancy`). An old tradition: open the Bible at a random page and read the verse your eye falls on as an answer. I'll pick a random verse from anywhere in the Bible for you, and it comes with the same four buttons.
- 🖼️ **Oracle answers as pictures.** Answers from `!virgil`, `!homer`, `!delphi` and `!oracle` now have a **Card** button that turns the answer into an image, like `!card` does for verses.
- 📜 **I'll announce my own updates** in a channel the server's admins choose with `!changelogsetup #channel` — that's what this message is! Anyone can type `!changelog` to see recent updates.
- 🔧 **Fixed: the ancient Near Eastern texts.** `!verse Gilgamesh 1`, `!verse Baal 1:1`, `!verse Aten` and the rest of that collection (the Epic of Gilgamesh, the Baal Cycle, the Hymn to the Aten, the Book of the Dead, the Mu'allaqat poems…) were showing errors or garbled text. They display properly again.
- 🔧 **Fixed: comparing translations.** Asking for one verse in several translations at once, like `!verse John 3:16 kjv web`, was failing with an error. It now shows them side by side again.
- 🔧 **Fixed: the Shepherd of Hermas.** This early Christian book is divided into Visions, Mandates and Similitudes, and you can now look it up the way scholars cite it: `!verse Herm Sim 9:1` means Similitude 9, chapter 1 (and `Herm Vis` and `Herm Man` work the same way). These used to open the wrong passages.
- 🔧 **Fixed: typing a Mishnah reference the way I display it.** (The Mishnah is the earliest written collection of Jewish oral law, from around AD 200.) Its passages are labelled like "Mishnah Berakhot 1:1", but typing that label back in, as in `!verse Mishnah Berakhot 1:1`, said "Unknown book". It works now, as does the short form `!verse Berakhot 1:1`.
- 🔧 **Fixed: verse ranges with spaces.** Typing a range with spaces around the dash, like `!verse John 3:16 - 18`, used to say "Unknown book". It now works just like `John 3:16-18`.
- 🔧 **Fixed: Psalms 151–155** (extra psalms found in some Bibles) were labelled oddly, like "Psalm 151 151:1". Now they read "Psalm 151:1".
