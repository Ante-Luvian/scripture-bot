# ScriptureBot changelog

What's new, newest first. When the bot starts after an update, she posts any
entries a server hasn't seen yet to that server's changelog channel
(`!changelogsetup #channel`); anyone can read recent ones with `!changelog`.

Format: one `## YYYY-MM-DD · Title` section per notable change (new commands,
new features, fixes users would notice), with `- ` bullets written for users.
Once an entry has been announced, don't change its heading — the heading is
how the bot remembers what it has already posted.

## 2026-10-12 · The big update: notes, study buttons, new oracle & more
- 📝 **New `!notes`** — the NET Bible's translator's, study, and text-critical notes for any verse (`!notes John 3:16`, up to 5 verses), straight from netbible.org. Numbered markers in the verse show exactly which word each note is about.
- 🔘 **Study buttons** — Bible verses from `!verse` now come with **Notes · Cross-refs · Interlinear · Card** buttons: one click to dig deeper.
- 📖 **New `!sortesbiblicae`** (or `!bibliomancy`) — the Bible opened at random, the old practice of bibliomancy, with the same study buttons.
- 🖼️ **Oracle cards** — every `!virgil`, `!homer`, `!delphi` and `!oracle` answer has a **Card** button that turns it into an image.
- 📜 **I announce my own updates now** — in the channel each server picks with `!changelogsetup #channel`; `!changelog` shows recent ones any time.
- 🔧 **Fixes** — Gilgamesh, the Baal Cycle, the Hymn to the Aten and the other Ancient Near East texts work again; side-by-side translations (`!verse John 3:16 kjv web`) work again; the Shepherd of Hermas takes traditional citations (`Herm Sim 9:1`); `Mishnah Berakhot 1:1` and `John 3:16 - 18` now work.
