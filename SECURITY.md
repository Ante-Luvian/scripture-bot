# Security policy

ScriptureBot runs on its owner's own computer, so a weakness in it is taken seriously.

## Reporting a problem
Please don't report a security problem in a public issue or in a Discord server. Report it to
the repository owner, privately: on GitHub, use **Report a vulnerability** on the repository's Security tab, which only the owner can read. Say what you found, how to reproduce it, and what it could let someone do.
You'll get an answer, and a fix if it's needed, as soon as possible.

## What counts
Anything that would let a Discord user, or someone sending input through any of the bot's
commands, buttons or menus:
- run code, or read or write files, on the machine the bot runs on;
- make the bot fetch something from a site of their choosing;
- use the bot to flood or overload the machine, or get it blocked by the sites it reads from;
- get around the admin-only commands, a server's settings, or the bot's mention rules
  (`@everyone`, roles).

## How the bot is protected
- It runs as a restricted Windows service account that can write only its own state files,
  backups and logs; the library itself is read-only to it.
- Nothing users type is run as code, used as a file path, or used to choose a website; text
  sent to outside sites is escaped.
- One person can send at most 10 commands in 20 seconds; bookmarks, exports and searches have
  their own limits.
- Every command is stress-tested with hostile input (see CONTRIBUTING.md).
