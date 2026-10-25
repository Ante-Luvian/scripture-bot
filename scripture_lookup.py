"""
scripture_lookup.py
-------------------
Handles all verse retrieval logic.

Data directory layout expected under  ./data/ :

  data/
    kjv/
      kjv_canon.json               # KJV Old + New Testament (66 books)
      kjv_apocrypha.json           # KJV Apocrypha (15 books)
    lds/
      book_of_mormon.json
      doctrine_and_covenants.json    # D&C uses sections, not chapters (treated the same)
      pearl_of_great_price.json      # Moses, Abraham, JS-Matthew, JS-History, Articles of Faith
    brenton/
      brenton_septuagint.json        # All LXX books including Psalms of Solomon, Prayer of Manasseh, etc.
    charles/
      book_of_enoch.json
      book_of_jubilees.json
    apostolic_fathers/               # J.B. Lightfoot translations
      1_clement.json
      2_clement.json
      ignatius_ephesians.json
      ignatius_magnesians.json
      ignatius_trallians.json
      ignatius_romans.json
      ignatius_philadelphians.json
      ignatius_smyrnaeans.json
      ignatius_polycarp.json
      polycarp_philippians.json
      martyrdom_of_polycarp.json
      epistle_of_barnabas.json
      didache.json
      shepherd_of_hermas.json        # Shepherd of Hermas (continuous chapter numbering)

Each JSON file must follow the schema:
  {
    "source": "King James Bible with Apocrypha",
    "books": {
      "BookName": {
        "1": {          // chapter (string key)
          "1": "text", // verse (string key)
          "2": "text"
        }
      }
    }
  }

For Doctrine & Covenants, treat each "section" as a "chapter".
For Articles of Faith (1 chapter, 13 articles), chapter = "1", verse = article number.
For Shepherd of Hermas, each part (Visions/Mandates/Similitudes) is its own book;
  chapter = the part's own chapter number, verse = sentence/paragraph number.
"""

from __future__ import annotations
import json
import os
import re
import unicodedata
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

from sefaria_lookup import (
    resolve_tractate,
    parse_mishnah_ref,
    fetch_mishnah,
    fetch_mishnah_chapter,
    MISHNAH_TRACTATES,
    # Babylonian Talmud
    get_talmud,
    parse_talmud_ref,
    resolve_talmud_tractate,
    TALMUD_TRACTATES,
    # Zohar
    get_zohar,
    parse_zohar_ref,
    # New Sefaria texts
    fetch_sefaria_generic,
)

# Jerusalem Talmud tractates available on Sefaria (Guggenheimer translation)
# Cite as: !verse Jerusalem Talmud Berakhot 1:1  (chapter:halakhah)
YERUSHALMI_TRACTATES: dict[str, str] = {
    # Seder Zeraim
    "berakhot": "Jerusalem_Talmud_Berakhot",
    "peah": "Jerusalem_Talmud_Peah",
    "demai": "Jerusalem_Talmud_Demai",
    "kilayim": "Jerusalem_Talmud_Kilayim",
    "sheviit": "Jerusalem_Talmud_Sheviit",
    "terumot": "Jerusalem_Talmud_Terumot",
    "maaserot": "Jerusalem_Talmud_Maasrot",
    "maaser sheni": "Jerusalem_Talmud_Maaser_Sheni",
    "challah": "Jerusalem_Talmud_Challah",
    "orlah": "Jerusalem_Talmud_Orlah",
    "bikkurim": "Jerusalem_Talmud_Bikkurim",
    # Seder Moed
    "shabbat": "Jerusalem_Talmud_Shabbat",
    "eruvin": "Jerusalem_Talmud_Eruvin",
    "pesachim": "Jerusalem_Talmud_Pesachim",
    "shekalim": "Jerusalem_Talmud_Shekalim",
    "yoma": "Jerusalem_Talmud_Yoma",
    "sukkah": "Jerusalem_Talmud_Sukkah",
    "beitzah": "Jerusalem_Talmud_Beitzah",
    "rosh hashanah": "Jerusalem_Talmud_Rosh_Hashanah",
    "taanit": "Jerusalem_Talmud_Taanit",
    "megillah": "Jerusalem_Talmud_Megillah",
    "moed katan": "Jerusalem_Talmud_Moed_Katan",
    "chagigah": "Jerusalem_Talmud_Chagigah",
    # Seder Nashim
    "yevamot": "Jerusalem_Talmud_Yevamot",
    "ketubot": "Jerusalem_Talmud_Ketubot",
    "nedarim": "Jerusalem_Talmud_Nedarim",
    "nazir": "Jerusalem_Talmud_Nazir",
    "sotah": "Jerusalem_Talmud_Sotah",
    "gittin": "Jerusalem_Talmud_Gittin",
    "kiddushin": "Jerusalem_Talmud_Kiddushin",
    # Seder Nezikin
    "bava kamma": "Jerusalem_Talmud_Bava_Kamma",
    "bava metzia": "Jerusalem_Talmud_Bava_Metzia",
    "bava batra": "Jerusalem_Talmud_Bava_Batra",
    "sanhedrin": "Jerusalem_Talmud_Sanhedrin",
    "makkot": "Jerusalem_Talmud_Makkot",
    "shevuot": "Jerusalem_Talmud_Shevuot",
    "avodah zarah": "Jerusalem_Talmud_Avodah_Zarah",
    "horayot": "Jerusalem_Talmud_Horayot",
    "niddah": "Jerusalem_Talmud_Niddah",
}

# Targumim available on Sefaria
# Cite as: !verse Targum Onkelos Genesis 1:1
TARGUM_NAMES: dict[str, str] = {
    "targum onkelos": "Onkelos",          # Torah only -- Sefaria's real title is "Onkelos Genesis" etc., not "Targum Onkelos, Genesis"
    "onkelos": "Onkelos",
    "targum jonathan": "Targum_Jonathan",         # Prophets only
    "targum yonatan": "Targum_Jonathan",
    "targum pseudo-jonathan": "Targum_Pseudo_Jonathan",  # Torah
    "pseudo-jonathan": "Targum_Pseudo_Jonathan",
    "targum neofiti": "Targum_Neofiti",           # Torah
    "neofiti": "Targum_Neofiti",
    "targum": "Onkelos",                   # default to Onkelos
}

# Midrash Rabbah and other Midrashim on Sefaria
# Cite as: !verse Bereshit Rabbah 1:1
MIDRASH_NAMES: dict[str, str] = {
    "bereshit rabbah": "Bereshit_Rabbah",
    "genesis rabbah": "Bereshit_Rabbah",
    "shemot rabbah": "Shemot_Rabbah",
    "exodus rabbah": "Shemot_Rabbah",
    "vayikra rabbah": "Vayikra_Rabbah",
    "leviticus rabbah": "Vayikra_Rabbah",
    "bamidbar rabbah": "Bamidbar_Rabbah",
    "numbers rabbah": "Bamidbar_Rabbah",
    "devarim rabbah": "Devarim_Rabbah",
    "deuteronomy rabbah": "Devarim_Rabbah",
    "ruth rabbah": "Ruth_Rabbah",
    "esther rabbah": "Esther_Rabbah",
    "eichah rabbah": "Eichah_Rabbah",
    "lamentations rabbah": "Eichah_Rabbah",
    "shir hashirim rabbah": "Shir_HaShirim_Rabbah",
    "song of songs rabbah": "Shir_HaShirim_Rabbah",
    "kohelet rabbah": "Kohelet_Rabbah",
    "ecclesiastes rabbah": "Kohelet_Rabbah",
    "mechilta": "Mekhilta_d\'Rabbi_Yishmael",
    "mekhilta": "Mekhilta_d\'Rabbi_Yishmael",
    "sifra": "Sifra",
    "sifre": "Sifre_Devarim",
    "sifrei": "Sifre_Devarim",
    "sifre bamidbar": "Sifre_Bamidbar",
    "sifre numbers": "Sifre_Bamidbar",
    "sifre devarim": "Sifre_Devarim",
    "sifre deuteronomy": "Sifre_Devarim",
    "pirkei derabbi eliezer": "Pirkei_DeRabbi_Eliezer",
    "tanchuma": "Midrash_Tanchuma",
}

# Kabbalah texts on Sefaria (beyond Zohar)
KABBALAH_NAMES: dict[str, str] = {
    "sefer yetzirah": "Sefer_Yetzirah",
    "book of formation": "Sefer_Yetzirah",
    "sefer habahir": "Bahir",
    "bahir": "Bahir",
    "tikkunei zohar": "Tikkunei_Zohar",
    "tikkunim": "Tikkunei_Zohar",
    "zohar chadash": "Zohar_Chadash",
    # Tanya has 5 parts — handled separately in _try_kabbalah
    "tanya": "Tanya",
}

# Tanya's 5 parts: user says "Tanya 2:1" meaning part 2, chapter 1
# or "Tanya 1:5" meaning Part I (Likkutei Amarim), chapter 5
TANYA_PARTS: dict[int, tuple[str, int]] = {
    # part_number: (sefaria_tref_suffix, chapter_count)
    1: ("Tanya,_Part_I;_Likkutei_Amarim",          53),
    2: ("Tanya,_Part_II;_Shaar_HaYichud_VehaEmunah", 12),
    3: ("Tanya,_Part_III;_Iggeret_HaTeshuvah",       12),
    4: ("Tanya,_Part_IV;_Iggeret_HaKodesh",          32),
    5: ("Tanya,_Part_V;_Kuntres_Acharon",             9),
}
from hadith_lookup import (
    get_hadith,
    parse_hadith_ref,
    resolve_collection,
    HADITH_COLLECTIONS,
    COLLECTION_DISPLAY,
)

DATA_DIR = Path(__file__).parent / "data"

# ── Book alias table ───────────────────────────────────────────────────────────
# Maps every reasonable abbreviation → canonical name used in JSON files.
# Add more as needed.

ALIASES: dict[str, str] = {
    # ── Old Testament ──────────────────────────────────────────────────────
    "gen": "Genesis", "ge": "Genesis", "gn": "Genesis",
    "ex": "Exodus", "exod": "Exodus",
    "lev": "Leviticus", "lv": "Leviticus",
    "num": "Numbers", "nu": "Numbers", "nm": "Numbers",
    "deut": "Deuteronomy", "dt": "Deuteronomy", "deu": "Deuteronomy",
    "josh": "Joshua", "jos": "Joshua",
    "judg": "Judges", "jdg": "Judges",
    "ruth": "Ruth", "rth": "Ruth",
    "1sam": "1 Samuel", "1 sam": "1 Samuel", "1sa": "1 Samuel", "i sam": "1 Samuel",
    "2sam": "2 Samuel", "2 sam": "2 Samuel", "2sa": "2 Samuel",
    "1kgs": "1 Kings", "1 kgs": "1 Kings", "1ki": "1 Kings",
    "2kgs": "2 Kings", "2 kgs": "2 Kings", "2ki": "2 Kings",
    "1chr": "1 Chronicles", "1 chr": "1 Chronicles", "1ch": "1 Chronicles",
    "2chr": "2 Chronicles", "2 chr": "2 Chronicles", "2ch": "2 Chronicles",
    "ezra": "Ezra",
    "neh": "Nehemiah",
    "esth": "Esther",
    "job": "Job",
    "ps": "Psalms", "psa": "Psalms", "psalm": "Psalms",
    "prov": "Proverbs", "pro": "Proverbs", "prv": "Proverbs",
    "eccl": "Ecclesiastes", "ecc": "Ecclesiastes", "qoh": "Ecclesiastes",
    "song": "Song of Solomon", "sos": "Song of Solomon", "ss": "Song of Solomon",
    "isa": "Isaiah",
    "jer": "Jeremiah",
    "lam": "Lamentations",
    "ezek": "Ezekiel", "eze": "Ezekiel",
    "dan": "Daniel",
    "hos": "Hosea",
    "joel": "Joel",
    "amos": "Amos",
    "obad": "Obadiah",
    "jonah": "Jonah", "jon": "Jonah",
    "mic": "Micah",
    "nah": "Nahum",
    "hab": "Habakkuk",
    "zeph": "Zephaniah", "zep": "Zephaniah",
    "hag": "Haggai",
    "zech": "Zechariah", "zec": "Zechariah",
    "mal": "Malachi",
    # ── New Testament ──────────────────────────────────────────────────────
    "matt": "Matthew", "mt": "Matthew",
    "mark": "Mark", "mrk": "Mark",
    "luke": "Luke", "lk": "Luke",
    "john": "John", "jn": "John",
    "acts": "Acts",
    "rom": "Romans",
    "1cor": "1 Corinthians", "1 cor": "1 Corinthians",
    "2cor": "2 Corinthians", "2 cor": "2 Corinthians",
    "gal": "Galatians",
    "eph": "Ephesians",
    "phil": "Philippians",
    "col": "Colossians",
    "1thess": "1 Thessalonians", "1 thess": "1 Thessalonians",
    "2thess": "2 Thessalonians", "2 thess": "2 Thessalonians",
    "1tim": "1 Timothy", "1 tim": "1 Timothy",
    "2tim": "2 Timothy", "2 tim": "2 Timothy",
    "titus": "Titus", "tit": "Titus",
    "phlm": "Philemon", "philem": "Philemon",
    "heb": "Hebrews",
    "jas": "James", "jam": "James",
    "1pet": "1 Peter", "1 pet": "1 Peter",
    "2pet": "2 Peter", "2 pet": "2 Peter",
    "1john": "1 John", "1 john": "1 John", "1jn": "1 John",
    "2john": "2 John", "2 john": "2 John",
    "3john": "3 John", "3 john": "3 John",
    "jude": "Jude",
    "rev": "Revelation", "apoc": "Revelation",
    # ── KJV Apocrypha ──────────────────────────────────────────────────────
    "1esd": "1 Esdras", "1 esd": "1 Esdras",
    "2esd": "2 Esdras", "2 esd": "2 Esdras",
    "tob": "Tobit",
    "jdt": "Judith",
    "addesth": "Additions to Esther", "add esth": "Additions to Esther",
    "wis": "Wisdom of Solomon", "wisd": "Wisdom of Solomon", "wisdom": "Wisdom of Solomon",
    "sir": "Sirach", "ecclus": "Sirach",
    "bar": "Baruch",
    "sg3": "Song of the Three Children",
    "sus": "Susanna",
    "bel": "Bel and the Dragon",
    "prmanas": "Prayer of Manasseh",
    "1macc": "1 Maccabees", "1 macc": "1 Maccabees",
    "2macc": "2 Maccabees", "2 macc": "2 Maccabees",
    # ── Brenton-only books ─────────────────────────────────────────────────
    "3macc": "3 Maccabees", "3 macc": "3 Maccabees",
    "4macc": "4 Maccabees", "4 macc": "4 Maccabees",
    "psssol": "Psalms of Solomon", "ps sol": "Psalms of Solomon", "pssol": "Psalms of Solomon",
    "odes": "Odes",
    "ps151": "Psalm 151", "psalm 151": "Psalm 151",
    "ps152": "Psalm 152", "psalm 152": "Psalm 152",
    "ps153": "Psalm 153", "psalm 153": "Psalm 153",
    "ps154": "Psalm 154", "psalm 154": "Psalm 154",
    "ps155": "Psalm 155", "psalm 155": "Psalm 155",
    # ── R.H. Charles ──────────────────────────────────────────────────────
    "enoch": "Book of Enoch", "1enoch": "Book of Enoch", "1 enoch": "Book of Enoch",
    "jub": "Book of Jubilees", "jubilees": "Book of Jubilees", "jub": "Book of Jubilees",
    # ── Apostolic Fathers (J.B. Lightfoot) ────────────────────────────────
    # 1 Clement — letter from the Roman church, ~96 AD
    "1clem": "1 Clement", "1 clem": "1 Clement", "1clement": "1 Clement",
    "i clem": "1 Clement", "i clement": "1 Clement",
    # 2 Clement — earliest surviving Christian homily, ~150 AD
    "2clem": "2 Clement", "2 clem": "2 Clement", "2clement": "2 Clement",
    "ii clem": "2 Clement", "ii clement": "2 Clement",
    # Ignatius of Antioch — seven letters, ~107 AD
    "ign eph": "Ignatius to the Ephesians",   "igneph": "Ignatius to the Ephesians",
    "ign mag": "Ignatius to the Magnesians",  "ignmag": "Ignatius to the Magnesians",
    "ign trall": "Ignatius to the Trallians", "igntrall": "Ignatius to the Trallians",
    "ign rom": "Ignatius to the Romans",      "ignrom": "Ignatius to the Romans",
    "ign phld": "Ignatius to the Philadelphians", "ignphld": "Ignatius to the Philadelphians",
    "ign smyrn": "Ignatius to the Smyrnaeans",    "ignsmyrn": "Ignatius to the Smyrnaeans",
    "ign pol": "Ignatius to Polycarp",        "ignpol": "Ignatius to Polycarp",
    # Polycarp
    "pol phil": "Polycarp to the Philippians", "polphil": "Polycarp to the Philippians",
    "pol": "Polycarp to the Philippians",      "polyp": "Polycarp to the Philippians",
    # Martyrdom of Polycarp
    "mart pol": "Martyrdom of Polycarp", "martpol": "Martyrdom of Polycarp",
    "mpol": "Martyrdom of Polycarp", "martyrdom": "Martyrdom of Polycarp",
    # Epistle of Barnabas
    "barn": "Epistle of Barnabas", "barnabas": "Epistle of Barnabas",
    "ep barn": "Epistle of Barnabas",
    # Didache (The Teaching of the Twelve Apostles)
    "did": "Didache", "didache": "Didache", "didach": "Didache",
    "teaching": "Didache",
    # Shepherd of Hermas
    "herm": "Shepherd of Hermas", "hermas": "Shepherd of Hermas",
    "shep herm": "Shepherd of Hermas", "shepherd": "Shepherd of Hermas",
    "herm vis": "Shepherd of Hermas", "hermvis": "Shepherd of Hermas",
    "herm man": "Shepherd of Hermas", "hermman": "Shepherd of Hermas",
    "herm sim": "Shepherd of Hermas", "hermsim": "Shepherd of Hermas",
    # ── Apocryphal Psalms ──────────────────────────────────────────────────
    "psalm 151": "Psalm 151", "ps 151": "Psalm 151",
    "psalm 152": "Psalm 152", "ps 152": "Psalm 152",
    "psalm 153": "Psalm 153", "ps 153": "Psalm 153",
    "psalm 154": "Psalm 154", "ps 154": "Psalm 154",
    "psalm 155": "Psalm 155", "ps 155": "Psalm 155",
    # ── Quran (Pickthall) ──────────────────────────────────────────────────
    "quran": "Quran", "qur": "Quran", "qran": "Quran",
    "sura": "Quran", "surah": "Quran",
    "koran": "Quran", "qur'an": "Quran",
    # ── Classical & Ancient Texts ───────────────────────────────────────────
    "golden verses": "Golden Verses of Pythagoras",
    "golden verses of pythagoras": "Golden Verses of Pythagoras",
    "gvp": "Golden Verses of Pythagoras",
    "pythagoras": "Golden Verses of Pythagoras",
    "orphic hymns": "Orphic Hymns",
    "orphic": "Orphic Hymns",
    "hymns of orpheus": "Orphic Hymns",
    "homeric hymns": "Homeric Hymns",
    "homeric": "Homeric Hymns",
    "corpus hermeticum": "Corpus Hermeticum",
    "hermeticum": "Corpus Hermeticum",
    "ch": "Corpus Hermeticum",
    "hermes": "Corpus Hermeticum",
    "asclepius": "Asclepius",
    "chaldaean oracles": "Chaldaean Oracles",
    "chaldean oracles": "Chaldaean Oracles",
    "oracles of zoroaster": "Chaldaean Oracles",
    "coz": "Chaldaean Oracles",
    "theogony": "Theogony",
    "hesiod": "Theogony",
    "hesiod theogony": "Theogony",
    "gathas": "Gathas",
    "gatha": "Gathas",
    "gathas of zarathushtra": "Gathas",
    "gathas of zarathustra": "Gathas",
    # Zoroastrian (Avesta, Bundahishn)
    "videvdad": "Vendidad", "vendidad": "Vendidad", "yasht": "Yashts", "yashts": "Yashts", "yasts": "Yashts",
    "bundahis": "Bundahishn", "bundahishn": "Bundahishn", "bundahism": "Bundahishn",
    # Sikh
    "granth": "Guru Granth Sahib", "guru granth": "Guru Granth Sahib", "adi granth": "Guru Granth Sahib",
    "sggs": "Guru Granth Sahib", "japji sahib": "Japji", "jap ji": "Japji", "jupji": "Japji", "jup": "Japji",
    # Jain
    "akaranga": "Akaranga Sutra", "acaranga": "Akaranga Sutra", "acaranga sutra": "Akaranga Sutra",
    "kalpa": "Kalpa Sutra", "uttaradhyayana": "Uttaradhyayana Sutra", "uttaradhyayana sutra": "Uttaradhyayana Sutra",
    "sutrakritanga sutra": "Sutrakritanga", "sutrakrtanga": "Sutrakritanga",
    # Shinto, Maya, Finnish, Welsh
    "nihon shoki": "Nihongi", "nihonshoki": "Nihongi", "popol wuj": "Popol Vuh",
    "mabinogi": "Mabinogion",
    # Chinese
    "chuang tzu": "Zhuangzi", "chuang-tzu": "Zhuangzi", "zhuang zi": "Zhuangzi", "kwang-dze": "Zhuangzi",
    "kwang dze": "Zhuangzi", "mengzi": "Mencius", "meng tzu": "Mencius", "da xue": "Great Learning",
    "ta hsueh": "Great Learning", "zhongyong": "Doctrine of the Mean", "zhong yong": "Doctrine of the Mean",
    "chung yung": "Doctrine of the Mean", "doctrine of mean": "Doctrine of the Mean",
    # Persian poetry
    "mathnawi": "Masnavi", "masnavi-i-ma'navi": "Masnavi", "rumi": "Masnavi", "khayyam": "Rubaiyat",
    "rubaiyat of omar khayyam": "Rubaiyat", "rubayyat": "Rubaiyat",
    # Buddhist
    "saddharma pundarika": "Lotus Sutra", "saddharma-pundarika": "Lotus Sutra", "lotus": "Lotus Sutra",
    "milinda": "Questions of King Milinda", "milindapanha": "Questions of King Milinda",
    "milinda panha": "Questions of King Milinda", "jatakas": "Jataka", "jataka tales": "Jataka",
    # Hindu
    "chandogya": "Chandogya Upanishad", "khandogya": "Chandogya Upanishad", "brihadaranyaka": "Brihadaranyaka Upanishad",
    "mundaka": "Mundaka Upanishad", "taittiriya": "Taittiriya Upanishad", "svetasvatara": "Svetasvatara Upanishad",
    "shvetashvatara": "Svetasvatara Upanishad", "prasna": "Prasna Upanishad", "prashna": "Prasna Upanishad",
    "maitri": "Maitrayana Upanishad", "maitrayani": "Maitrayana Upanishad", "kaushitaki": "Kaushitaki Upanishad",
    "manu": "Laws of Manu", "manusmriti": "Laws of Manu", "manava dharmashastra": "Laws of Manu",
    "yoga sutra": "Yoga Sutras", "yoga sutras of patanjali": "Yoga Sutras", "patanjali": "Yoga Sutras",
    # Christian mystics
    "cloud": "Cloud of Unknowing", "the cloud of unknowing": "Cloud of Unknowing",
    "julian of norwich": "Revelations of Divine Love", "showings": "Revelations of Divine Love",
    "brother lawrence": "Practice of the Presence of God", "practice of the presence": "Practice of the Presence of God",
    # Swedenborg, by the New Church's standard abbreviations
    "arcana": "Arcana Coelestia",                       # (not "ac": that's Acts) "arcana caelestia": "Arcana Coelestia", "secrets of heaven": "Arcana Coelestia",
    "hh": "Heaven and Hell", "dlw": "Divine Love and Wisdom", "dp": "Divine Providence",
    "tcr": "True Christian Religion", "true christianity": "True Christian Religion", "cl": "Conjugial Love",
    "marriage love": "Conjugial Love", "ar": "Apocalypse Revealed", "ae": "Apocalypse Explained",
    "eu": "Earths in the Universe", "other planets": "Earths in the Universe",
    "nj": "The New Jerusalem and its Heavenly Doctrine", "new jerusalem": "The New Jerusalem and its Heavenly Doctrine",
    "lj": "The Last Judgment", "last judgment": "The Last Judgment", "sd": "Spiritual Diary",
    "spiritual experiences": "Spiritual Diary", "wh": "The White Horse", "white horse": "The White Horse",
    "doctrine of the lord": "Doctrine of the Lord", "doctrine of sacred scripture": "Doctrine of the Sacred Scripture",
    "sacred scripture": "Doctrine of the Sacred Scripture", "doctrine of life": "Doctrine of Life",
    "doctrine of faith": "Doctrine of Faith", "brief exposition": "Brief Exposition of the Doctrine of the New Church",
    "soul and body": "Interaction of the Soul and Body", "charity": "Doctrine of Charity",
    # William Blake
    "thel": "The Book of Thel", "book of thel": "The Book of Thel", "mhh": "The Marriage of Heaven and Hell",
    "marriage of heaven and hell": "The Marriage of Heaven and Hell", "songs of innocence": "Songs of Innocence",
    "songs of experience": "Songs of Experience",
    # the Reformation ("Institutes" alone stays Cassian's, as it was before)
    "calvin's institutes": "Institutes of the Christian Religion", "calvins institutes": "Institutes of the Christian Religion",
    "calvin institutes": "Institutes of the Christian Religion", "inst": "Institutes of the Christian Religion",
    "95 theses": "Ninety-Five Theses", "ninety five theses": "Ninety-Five Theses", "theses": "Ninety-Five Theses",
    "heidelberg": "Heidelberg Catechism", "augsburg": "Augsburg Confession", "ac": "Augsburg Confession",
    "ap": "Apology of the Augsburg Confession", "apology of the augsburg confession": "Apology of the Augsburg Confession",
    "smalcald": "Smalcald Articles", "schmalkald articles": "Smalcald Articles",
    "luther's small catechism": "Small Catechism", "luther's large catechism": "Large Catechism",
    "epitome": "Formula of Concord, Epitome", "formula of concord": "Formula of Concord, Epitome",
    "solid declaration": "Formula of Concord, Solid Declaration",
    "power and primacy": "Treatise on the Power and Primacy of the Pope",
    "westminster confession": "Westminster Confession of Faith", "wcf": "Westminster Confession of Faith",
    "shorter catechism": "Westminster Shorter Catechism", "wsc": "Westminster Shorter Catechism",
    "larger catechism": "Westminster Larger Catechism", "wlc": "Westminster Larger Catechism",
    "39 articles": "Thirty-Nine Articles", "thirty nine articles": "Thirty-Nine Articles",
    "articles of religion": "Thirty-Nine Articles", "belgic": "Belgic Confession", "dort": "Canons of Dort",
    "canons of dordt": "Canons of Dort", "scots": "Scots Confession", "second helvetic": "Second Helvetic Confession",
    "1689": "Second London Baptist Confession", "london baptist confession": "Second London Baptist Confession",
    "1689 baptist confession": "Second London Baptist Confession",
    "bondage of the will": "The Bondage of the Will", "christian liberty": "A Treatise on Christian Liberty",
    "freedom of a christian": "A Treatise on Christian Liberty", "babylonian captivity": "The Babylonian Captivity of the Church",
    "to the christian nobility": "An Open Letter to the Christian Nobility", "christian nobility": "An Open Letter to the Christian Nobility",
    "good works": "Treatise on Good Works", "wittenberg sermons": "The Eight Wittenberg Sermons",
    "luther galatians": "Luther on Galatians", "luther's sermons": "Sermons of Martin Luther",
    "table talk": "Table Talk", "relics": "A Treatise on Relics",
    "first blast": "The First Blast of the Trumpet", "knox history": "The History of the Reformation in Scotland",
    "history of the reformation": "The History of the Reformation in Scotland",
    "latimer": "Sermons of Hugh Latimer", "herbert": "The Temple", "the temple herbert": "The Temple",
    "andrewes": "Private Devotions of Lancelot Andrewes", "serious call": "A Serious Call to a Devout and Holy Life",
    "wesley": "Sermons of John Wesley", "wesley's sermons": "Sermons of John Wesley", "wesley sermons": "Sermons of John Wesley",
    "wesley's journal": "The Journal of John Wesley", "wesley journal": "The Journal of John Wesley",
    "christian perfection": "A Plain Account of Christian Perfection",
    "hooker": "Laws of Ecclesiastical Polity", "ecclesiastical polity": "Laws of Ecclesiastical Polity",
    "of the laws of ecclesiastical polity": "Laws of Ecclesiastical Polity",
    "homilies": "The Book of Homilies, First Book", "book of homilies": "The Book of Homilies, First Book",
    "first book of homilies": "The Book of Homilies, First Book", "cranmer's homilies": "The Book of Homilies, First Book",
    "cranmers homilies": "The Book of Homilies, First Book", "second book of homilies": "The Book of Homilies, Second Book",
    "homilies 2": "The Book of Homilies, Second Book", "bonner": "Bonner's Homilies", "bonners homilies": "Bonner's Homilies",
    "donne": "Donne's LXXX Sermons", "lxxx sermons": "Donne's LXXX Sermons", "donne's sermons": "Donne's LXXX Sermons",
    "fifty sermons": "Donne's Fifty Sermons", "xxvi sermons": "Donne's XXVI Sermons", "holy sonnets": "Holy Sonnets",
    "donne holy sonnets": "Holy Sonnets",
    # John Bunyan
    "pilgrims progress": "Pilgrim's Progress", "pilgrim's progress part one": "Pilgrim's Progress",
    "pilgrim's progress part two": "Pilgrim's Progress, Part Two", "pilgrim's progress part 2": "Pilgrim's Progress, Part Two",
    "pilgrims progress part two": "Pilgrim's Progress, Part Two", "pilgrims progress part 2": "Pilgrim's Progress, Part Two",
    "pilgrim's progress 2": "Pilgrim's Progress, Part Two", "christiana": "Pilgrim's Progress, Part Two",
    # John Milton
    "pl": "Paradise Lost", "paradise regain'd": "Paradise Regained", "pr": "Paradise Regained",
    "samson": "Samson Agonistes", "sa": "Samson Agonistes",
    # Kitáb-i-Aqdas
    "kitab-i-aqdas": "Kitab-i-Aqdas",
    "kitab i aqdas": "Kitab-i-Aqdas",
    "aqdas": "Kitab-i-Aqdas",
    "kitab": "Kitab-i-Aqdas",
    "most holy book": "Kitab-i-Aqdas",
    # Hidden Words
    "hidden words arabic": "The Hidden Words (Arabic)",
    "the hidden words arabic": "The Hidden Words (Arabic)",
    "hidden words (arabic)": "The Hidden Words (Arabic)",
    "hidden words persian": "The Hidden Words (Persian)",
    "the hidden words persian": "The Hidden Words (Persian)",
    "hidden words (persian)": "The Hidden Words (Persian)",
    "hidden words": "The Hidden Words (Arabic)",
    # Gleanings
    "gleanings": "Gleanings from the Writings of Baha'u'llah",
    "gleanings from the writings of bahaullah": "Gleanings from the Writings of Baha'u'llah",
    "gwb": "Gleanings from the Writings of Baha'u'llah",
    # Prayers and Meditations
    "prayers and meditations": "Prayers and Meditations",
    "prayers and meditations by bahaullah": "Prayers and Meditations",
    "pm": "Prayers and Meditations",
    # Some Answered Questions
    "some answered questions": "Some Answered Questions",
    "answered questions": "Some Answered Questions",
    "saq": "Some Answered Questions",
    # Kitáb-i-Íqán
    "kitab-i-iqan": "Kitab-i-Iqan",
    "kitab i iqan": "Kitab-i-Iqan",
    "iqan": "Kitab-i-Iqan",
    "book of certitude": "Kitab-i-Iqan",
    # Epistle to the Son of the Wolf
    "epistle to the son of the wolf": "Epistle to the Son of the Wolf",
    "son of the wolf": "Epistle to the Son of the Wolf",
    "esw": "Epistle to the Son of the Wolf",
    # Dead Sea Scrolls sectarian texts (Open Dead Sea machine-draft translations)
    "hodayot": "Hodayot",
    "thanksgiving hymns": "Hodayot",
    "thanksgiving scroll": "Hodayot",
    "1qha": "Hodayot",
    "damascus document": "Damascus Document",
    "cd": "Damascus Document",
    "community rule": "Community Rule",
    "manual of discipline": "Community Rule",
    "1qs": "Community Rule",
    "war scroll": "War Scroll",
    "1qm": "War Scroll",
    "pesher habakkuk": "Pesher Habakkuk",
    "habakkuk commentary": "Pesher Habakkuk",
    "1qphab": "Pesher Habakkuk",
    "rule of the congregation": "Rule of the Congregation",
    "1qsa": "Rule of the Congregation",
    "rule of blessings": "Rule of Blessings",
    "1qsb": "Rule of Blessings",
    # Ginza Rba
    "ginza rba": "Ginza Rba",
    "ginza": "Ginza Rba",
    "ginza rba - the canonical prayerbook of the mandaeans": "Ginza Rba",
    "mandaean prayerbook": "Ginza Rba",
    "ginza rabba": "Ginza Rba",
    # Mandaean Book of John
    "mandaean book of john": "Book of John",
    "mjohn": "Book of John",
    "mandaean john": "Book of John",
    "drasha d-yahya": "Book of John",
    "drasha dyahya": "Book of John",
    # Hymns of Proclus
    "proclus": "Proclus",
    "hymns of proclus": "Proclus",
    "proclus hymns": "Proclus",
    # Aeneid
    "aeneid": "Aeneid",
    "the aeneid": "Aeneid",
    "virgil": "Aeneid",
    "vergil": "Aeneid",
    # Plato dialogues
    "euthyphro": "Euthyphro",
    "apology": "Apology",
    "apology of socrates": "Apology",
    "crito": "Crito",
    "phaedo": "Phaedo",
    "cratylus": "Cratylus",
    "theaetetus": "Theaetetus",
    "sophist": "Sophist",
    "statesman": "Statesman",
    "politicus": "Statesman",
    "parmenides": "Parmenides",
    "philebus": "Philebus",
    "symposium": "Symposium",
    "phaedrus": "Phaedrus",
    "alcibiades i": "Alcibiades I",
    "alcibiades 1": "Alcibiades I",
    "first alcibiades": "Alcibiades I",
    "alcibiades ii": "Alcibiades II",
    "alcibiades 2": "Alcibiades II",
    "second alcibiades": "Alcibiades II",
    "hipparchus": "Hipparchus",
    "rival lovers": "Rival Lovers",
    "theages": "Theages",
    "charmides": "Charmides",
    "laches": "Laches",
    "lysis": "Lysis",
    "euthydemus": "Euthydemus",
    "protagoras": "Protagoras",
    "gorgias": "Gorgias",
    "meno": "Meno",
    "greater hippias": "Greater Hippias",
    "hippias major": "Greater Hippias",
    "lesser hippias": "Lesser Hippias",
    "hippias minor": "Lesser Hippias",
    "ion": "Ion",
    "menexenus": "Menexenus",
    "cleitophon": "Cleitophon",
    "clitophon": "Cleitophon",
    "republic": "Republic",
    "the republic": "Republic",
    "timaeus": "Timaeus",
    "critias": "Critias",
    "minos": "Minos",
    "laws": "Laws",
    "the laws": "Laws",
    "epinomis": "Epinomis",
    "letters": "Letters",
    "platonic letters": "Letters",
    "axiochus": "Axiochus",
    "eryxias": "Eryxias",
    # ── Homer ──────────────────────────────────────────────────────────────────
    "iliad": "Iliad",
    "homer iliad": "Iliad",
    "odyssey": "Odyssey",
    "homer odyssey": "Odyssey",
    # ── Aristotle ──────────────────────────────────────────────────────────────
    "aristotle": "Nicomachean Ethics",  # default to most famous
    "nicomachean ethics": "Nicomachean Ethics",
    "nic eth": "Nicomachean Ethics",
    "en": "Nicomachean Ethics",
    "eudemian ethics": "Eudemian Ethics",
    "eud eth": "Eudemian Ethics",
    "ee": "Eudemian Ethics",
    "metaphysics": "Metaphysics",
    "met": "Metaphysics",
    "physics": "Physics",
    "phys": "Physics",
    "on the soul": "On the Soul",
    "de anima": "On the Soul",
    "politics": "Politics",
    "aristotle politics": "Politics",      # ("pol" is Polycarp, as in "Pol Phil 2:1")
    "rhetoric": "Rhetoric",
    "rhet": "Rhetoric",
    "poetics": "Poetics",
    "economics": "Economics",
    "categories": "Categories",
    "cat": "Categories",
    "on interpretation": "On Interpretation",
    "de int": "On Interpretation",
    "prior analytics": "Prior Analytics",
    "posterior analytics": "Posterior Analytics",
    "topics": "Topics",
    "on the heavens": "On the Heavens",
    "de caelo": "On the Heavens",
    "meteorology": "Meteorology",
    "on generation and corruption": "On Generation and Corruption",
    "history of animals": "History of Animals",
    "on the parts of animals": "On the Parts of Animals",
    "on the generation of animals": "On the Generation of Animals",
    "on memory": "On Memory and Reminiscence",
    "on memory and reminiscence": "On Memory and Reminiscence",
    "on dreams": "On Dreams",
    "on sleep": "On Sleep and Sleeplessness",
    "on prophesying by dreams": "On Prophesying by Dreams",
    "on sense": "On Sense and the Sensible",
    "on the motion of animals": "On the Motion of Animals",
    "on the gait of animals": "On the Gait of Animals",
    "athenian constitution": "Athenian Constitution",
    "ath const": "Athenian Constitution",
    "on longevity": "On Longevity and Shortness of Life",
    "on youth": "On Youth, Old Age, Life and Death",
    "on sophistical refutations": "On Sophistical Refutations",
    # ── Plotinus ───────────────────────────────────────────────────────────────
    "plotinus": "Enneads",
    "enneads": "Enneads",
    "rig veda": "Rig Veda", "rigveda": "Rig Veda", "rig": "Rig Veda",
    "yajur veda": "Yajur Veda", "yajurveda": "Yajur Veda", "yajur": "Yajur Veda",
    "sama veda": "Sama Veda", "samaveda": "Sama Veda", "sama": "Sama Veda",
    "2 enoch": "2 Enoch", "secrets of enoch": "2 Enoch", "book of the secrets of enoch": "2 Enoch",
    "slavonic enoch": "2 Enoch", "ii enoch": "2 Enoch",
    "protevangelium": "The Protevangelium of James", "protoevangelium": "The Protevangelium of James",
    "protevangelium of james": "The Protevangelium of James", "gospel of james": "The Protevangelium of James",
    "infancy gospel of james": "The Protevangelium of James",
    "pseudo-matthew": "The Gospel of Pseudo-Matthew", "gospel of pseudo-matthew": "The Gospel of Pseudo-Matthew",
    "nativity of mary": "The Gospel of the Nativity of Mary",
    "joseph the carpenter": "The History of Joseph the Carpenter",
    "history of joseph the carpenter": "The History of Joseph the Carpenter",
    "infancy gospel of thomas": "Gospel of Thomas: First Greek Form", "infancy thomas": "Gospel of Thomas: First Greek Form",
    "arabic infancy gospel": "The Arabic Gospel of the Infancy of the Saviour",
    "acts of pilate": "Acts of Pilate: First Greek Form", "gospel of nicodemus": "Acts of Pilate: First Greek Form",
    "nicodemus": "Acts of Pilate: First Greek Form",
    "descent into hell": "Descent of Christ into Hell: Greek Form",
    "acts of paul and thecla": "Acts of Paul and Thecla", "paul and thecla": "Acts of Paul and Thecla",
    "thecla": "Acts of Paul and Thecla",
    "acts of thomas": "Various Acts of Thomas", "acts of philip": "The Acts of Philip",
    "acts of barnabas": "The Acts of Barnabas",
    "apocalypse of paul": "Revelation of Paul", "revelation of paul": "Revelation of Paul",
    "revelation of moses": "Revelation of Moses",     # (Charles's "Apocalypse of Moses" is a separate book)
    "works and days": "Works and Days", "erga": "Works and Days", "op": "Works and Days",
    "shield of heracles": "Shield of Heracles", "shield": "Shield of Heracles",
    "meditations": "Meditations", "marcus aurelius": "Meditations", "med": "Meditations",
    "enchiridion of epictetus": "Enchiridion of Epictetus", "epictetus": "Enchiridion of Epictetus",   # ("enchiridion" is Augustine's)
    "imitation of christ": "Imitation of Christ", "imitation": "Imitation of Christ",
    "a kempis": "Imitation of Christ", "kempis": "Imitation of Christ",
    "rule of benedict": "Rule of Benedict", "rule of st benedict": "Rule of Benedict",
    "rule of saint benedict": "Rule of Benedict", "benedict": "Rule of Benedict", "rb": "Rule of Benedict",
    "inferno": "Inferno", "inf": "Inferno", "purgatorio": "Purgatorio", "purgatory": "Purgatorio",
    "purg": "Purgatorio", "paradiso": "Paradiso", "paradise": "Paradiso",
    "bhagavad gita": "Bhagavad Gita", "gita": "Bhagavad Gita", "bg": "Bhagavad Gita",
    "bhagavadgita": "Bhagavad Gita", "geeta": "Bhagavad Gita", "bhagavad geeta": "Bhagavad Gita",
    # ("Isa" alone is Isaiah)
    "isa upanishad": "Isa Upanishad", "isha upanishad": "Isa Upanishad", "isavasya": "Isa Upanishad",
    "isha": "Isa Upanishad",
    "katha upanishad": "Katha Upanishad", "katha": "Katha Upanishad", "kathopanishad": "Katha Upanishad",
    "kena upanishad": "Kena Upanishad", "kena": "Kena Upanishad",
    "dhammapada": "Dhammapada", "dhp": "Dhammapada",
    "diamond sutra": "Diamond Sutra", "vajracchedika": "Diamond Sutra",
    "gospel of thomas": "Gospel of Thomas", "gthom": "Gospel of Thomas", "coptic thomas": "Gospel of Thomas",
    "thomas": "Gospel of Thomas",
    "enuma elish": "Enuma Elish", "enuma": "Enuma Elish", "enuma elis": "Enuma Elish",
    "seven tablets of creation": "Enuma Elish",
    "sutta nipata": "Sutta Nipata", "suttanipata": "Sutta Nipata", "snp": "Sutta Nipata",
    "sutta-nipata": "Sutta Nipata",
    "first book of adam and eve": "First Book of Adam and Eve", "1 adam and eve": "First Book of Adam and Eve",
    "conflict of adam and eve": "First Book of Adam and Eve",
    "second book of adam and eve": "Second Book of Adam and Eve", "2 adam and eve": "Second Book of Adam and Eve",
    "odes of solomon": "Odes of Solomon",   # ("odes" is the Septuagint book) "ode of solomon": "Odes of Solomon",
    "tao te ching": "Tao Te Ching", "daodejing": "Tao Te Ching", "dao de jing": "Tao Te Ching",
    "tao teh king": "Tao Te Ching", "ttc": "Tao Te Ching", "laozi": "Tao Te Ching", "lao tzu": "Tao Te Ching",
    "analects": "Analects", "lunyu": "Analects", "confucius": "Analects",
    "divan of hafiz": "Divan of Hafiz", "hafiz": "Divan of Hafiz", "hafez": "Divan of Hafiz",
    "divan": "Divan of Hafiz", "diwan": "Divan of Hafiz",
    "i ching": "I Ching", "yijing": "I Ching", "yi jing": "I Ching", "iching": "I Ching", "yi king": "I Ching",
    "atharva veda": "Atharva Veda", "atharvaveda": "Atharva Veda", "atharva": "Atharva Veda",
    "divine names": "Divine Names", "the divine names": "Divine Names",
    "mystical theology": "Mystical Theology", "mystic theology": "Mystical Theology",
    "heavenly hierarchy": "On the Heavenly Hierarchy",
    "on the heavenly hierarchy": "On the Heavenly Hierarchy",
    "celestial hierarchy": "On the Heavenly Hierarchy",
    "ecclesiastical hierarchy": "On the Ecclesiastical Hierarchy",
    "on the ecclesiastical hierarchy": "On the Ecclesiastical Hierarchy",
    "letters of dionysius": "Letters of Dionysius",
    "liturgy of st dionysius": "Liturgy of St. Dionysius",
    "liturgy of dionysius": "Liturgy of St. Dionysius",
    "the enneads": "Enneads",
    "six enneads": "Enneads",
    "enn": "Enneads",
    # ── Porphyry ───────────────────────────────────────────────────────────────
    "porphyry": "On Abstinence",  # default to longest work
    "on abstinence": "On Abstinence",
    "de abstinentia": "On Abstinence",
    "porphyry life of pythagoras": "Life of Pythagoras",
    "porphyry pythagoras": "Life of Pythagoras",
    "cave of the nymphs": "On the Cave of the Nymphs",
    "cave of nymphs": "On the Cave of the Nymphs",
    "de antro": "On the Cave of the Nymphs",
    "auxiliaries": "Auxiliaries to the Intelligibles",
    "sententiae": "Auxiliaries to the Intelligibles",
    "letter to marcella": "Letter to Marcella",
    "marcella": "Letter to Marcella",
    # ── Iamblichus ─────────────────────────────────────────────────────────────
    "iamblichus": "On the Mysteries",  # default to most famous
    "on the mysteries": "On the Mysteries",
    "de mysteriis": "On the Mysteries",
    "iamblichus mysteries": "On the Mysteries",
    "iamblichus life of pythagoras": "Life of Pythagoras",
    "iamblichus pythagoras": "Life of Pythagoras",
    # ── Philo ──────────────────────────────────────────────────────────────────
    "philo": "On the Creation",  # default
    "philo judaeus": "On the Creation",
    "on the creation": "On the Creation",
    "de opificio": "On the Creation",
    "allegorical interpretation": "Allegorical Interpretation I",
    "allegorical interpretation i": "Allegorical Interpretation I",
    "allegorical interpretation ii": "Allegorical Interpretation II",
    "allegorical interpretation iii": "Allegorical Interpretation III",
    "on the cherubim": "On the Cherubim",
    "on abraham": "On Abraham",
    "on joseph": "On Joseph",
    "on the life of moses": "On the Life of Moses I",
    "life of moses": "On the Life of Moses I",
    "the decalogue": "The Decalogue",
    "decalogue": "The Decalogue",
    "on the embassy to gaius": "On the Embassy to Gaius",
    "embassy to gaius": "On the Embassy to Gaius",
    "flaccus": "Flaccus",
    "every good man is free": "Every Good Man is Free",
    "on the contemplative life": "On the Contemplative Life",
    "questions on genesis": "Questions on Genesis I",
    "questions on genesis i": "Questions on Genesis I",
    "questions on genesis ii": "Questions on Genesis II",
    "questions on genesis iii": "Questions on Genesis III",
    # ── Josephus ───────────────────────────────────────────────────────────────
    "josephus": "Jewish Antiquities",  # default
    "jewish antiquities": "Jewish Antiquities",
    "antiquities": "Jewish Antiquities",
    "ant": "Jewish Antiquities",
    "jewish war": "Jewish War",
    "war": "Jewish War",
    "bj": "Jewish War",
    "against apion": "Against Apion",
    "apion": "Against Apion",
    "life of josephus": "Life",
    "josephus life": "Life",
    # ── Julian ─────────────────────────────────────────────────────────────────
    "julian": "Hymn to King Helios",  # default
    "emperor julian": "Hymn to King Helios",
    "julian the apostate": "Hymn to King Helios",
    "hymn to king helios": "Hymn to King Helios",
    "hymn to helios": "Hymn to King Helios",
    "oration to the sun": "Hymn to King Helios",
    "hymn to the mother of gods": "Hymn to the Mother of Gods",
    "hymn to the mother of the gods": "Hymn to the Mother of Gods",
    "hymn to cybele": "Hymn to the Mother of Gods",
    "against the galilaeans": "Against the Galilaeans",
    "against the galileans": "Against the Galilaeans",
    "against the christians": "Against the Galilaeans",
    "the caesars": "The Caesars",
    "caesars": "The Caesars",
    "symposium of the caesars": "The Caesars",
    # ── Sallustius ─────────────────────────────────────────────────────────────
    "sallustius": "On the Gods and the World",
    "sallust": "On the Gods and the World",
    "on the gods and the world": "On the Gods and the World",
    "on the gods": "On the Gods and the World",
    "peri theon": "On the Gods and the World",
    # ── Proclus (theology) ─────────────────────────────────────────────────────
    "theology of plato": "Theology of Plato",
    "platonic theology": "Theology of Plato",
    "proclus theology": "Theology of Plato",
    "elements of theology": "Elements of Theology",
    "elements of theology proclus": "Elements of Theology",
    "proclus elements": "Elements of Theology",
    "stoicheiosis": "Elements of Theology",
    "stoicheiosis theologike": "Elements of Theology",
    "institutio theologica": "Elements of Theology",
    # ── Hierocles ──────────────────────────────────────────────────────────────
    "hierocles": "Commentary on the Golden Verses",
    "commentary on the golden verses": "Commentary on the Golden Verses",
    "hierocles commentary": "Commentary on the Golden Verses",
    # ── Marinus ────────────────────────────────────────────────────────────────
    "marinus": "Life of Proclus",
    "life of proclus": "Life of Proclus",
    "marinus life of proclus": "Life of Proclus",
    "on happiness": "Life of Proclus",
    # ── Pythagorean Sentences ──────────────────────────────────────────────────
    "pythagorean sentences": "Select Sentences of Sextus the Pythagorean",
    "sentences of sextus": "Select Sentences of Sextus the Pythagorean",
    "sextus pythagorean": "Select Sentences of Sextus the Pythagorean",
    "sextus": "Select Sentences of Sextus the Pythagorean",
    "demophilus": "Pythagorean Sentences of Demophilus",
    "sentences of demophilus": "Pythagorean Sentences of Demophilus",
    "democrates": "Golden Sentences of Democrates",
    "golden sentences": "Golden Sentences of Democrates",
    "sentences of democrates": "Golden Sentences of Democrates",
    "pythagorean sentences from stobaeus": "Pythagorean Sentences from Stobaeus",
    "stobaeus pythagorean": "Pythagorean Sentences from Stobaeus",
    "symbols of pythagoras": "Symbols of Pythagoras",
    "pythagorean symbols": "Symbols of Pythagoras",
    "similitudes of demophilus": "Similitudes of Demophilus",
    "pythagorean sentences from iamblichus": "Pythagorean Sentences from Iamblichus",
    # ── Porphyry additions ─────────────────────────────────────────────────────
    "life of plotinus": "Life of Plotinus",
    "porphyry life of plotinus": "Life of Plotinus",
    # Astrology: Ptolemy (by book.chapter) and Lilly
    "tetrabiblos": "Tetrabiblos", "quadripartite": "Tetrabiblos", "ptolemy tetrabiblos": "Tetrabiblos",
    "centiloquy": "Centiloquy", "centiloquium": "Centiloquy", "ptolemy centiloquy": "Centiloquy",
    "lilly": "Lilly's Introduction to Astrology", "william lilly": "Lilly's Introduction to Astrology",
    "christian astrology": "Lilly's Introduction to Astrology",
    "introduction to astrology": "Lilly's Introduction to Astrology",
    "lilly appendix": "Lilly's Introduction to Astrology, Appendix",
    "sepharial": "Sepharial's Astrology", "sepharial astrology": "Sepharial's Astrology",
    # Aesop (Townsend), one chapter a fable
    "aesop": "Aesop's Fables", "aesops fables": "Aesop's Fables", "aesop's fables": "Aesop's Fables",
    "fables": "Aesop's Fables", "fables of aesop": "Aesop's Fables", "aesop fables": "Aesop's Fables",
    # The Arthurian legend (scripts/build_arthurian.py)
    "malory": "Le Morte d'Arthur",
    "morte d'arthur": "Le Morte d'Arthur",
    "morte darthur": "Le Morte d'Arthur",
    "le morte darthur": "Le Morte d'Arthur",
    "the morte d'arthur": "Le Morte d'Arthur",
    "erec": "Erec and Enide",
    "erec et enide": "Erec and Enide",
    "cliges": "Cligès",
    "cligès": "Cligès",
    "yvain": "Yvain, the Knight with the Lion",
    "knight with the lion": "Yvain, the Knight with the Lion",
    "the knight with the lion": "Yvain, the Knight with the Lion",
    "lancelot": "Lancelot, the Knight of the Cart",
    "knight of the cart": "Lancelot, the Knight of the Cart",
    "the knight of the cart": "Lancelot, the Knight of the Cart",
    "parsifal": "Parzival",
    "wolfram": "Parzival",
    "high history": "The High History of the Holy Graal",
    "high history of the holy graal": "The High History of the Holy Graal",
    "perlesvaus": "The High History of the Holy Graal",
    "queste": "The Quest of the Holy Grail",
    "quest of the holy grail": "The Quest of the Holy Grail",
    "queste del saint graal": "The Quest of the Holy Grail",
    "the quest": "The Quest of the Holy Grail",
    "tristan": "Tristan and Iseult",
    "tristan and isolde": "Tristan and Iseult",
    "romance of tristan and iseult": "Tristan and Iseult",
    "bedier": "Tristan and Iseult",
    "gawain": "Sir Gawain and the Green Knight",
    "sggk": "Sir Gawain and the Green Knight",
    "gawain and the green knight": "Sir Gawain and the Green Knight",
    "green knight": "Sir Gawain and the Green Knight",
    "marie de france": "Lays of Marie de France",
    "lais of marie de france": "Lays of Marie de France",
    "lays": "Lays of Marie de France",
    "geoffrey of monmouth": "Geoffrey of Monmouth, History of the Kings of Britain",
    "geoffrey": "Geoffrey of Monmouth, History of the Kings of Britain",
    "history of the kings of britain": "Geoffrey of Monmouth, History of the Kings of Britain",
    "historia regum britanniae": "Geoffrey of Monmouth, History of the Kings of Britain",
    "wace": "Wace, Roman de Brut",
    "roman de brut": "Wace, Roman de Brut",
    "layamon": "Layamon's Brut",
    "lawman": "Layamon's Brut",
    "layamon's brut": "Layamon's Brut",
    "nennius": "Nennius, History of the Britons",
    "historia brittonum": "Nennius, History of the Britons",
    "history of the britons": "Nennius, History of the Britons",
    "libeaus": "Sir Libeaus Desconus",
    "libeaus desconus": "Sir Libeaus Desconus",
    "fair unknown": "Sir Libeaus Desconus",
    "launfal": "Sir Launfal",
    "tarn wadeling": "The Adventures of Arthur at the Tarn Wadeling",
    "awntyrs": "The Adventures of Arthur at the Tarn Wadeling",
    # Two books of beasts (scripts/build_beasts.py)
    "bestiary": "Physiologus", "the physiologus": "Physiologus",
    "reynard": "Reynard the Fox", "history of reynard the fox": "Reynard the Fox", "reynart": "Reynard the Fox",
    # More fables (scripts/build_fables.py), one chapter a fable
    "fables of phaedrus": "Fables of Phaedrus", "phaedrus fables": "Fables of Phaedrus",   # ("phaedrus": Plato's)
    "la fontaine": "Fables of La Fontaine", "lafontaine": "Fables of La Fontaine",
    "fables of la fontaine": "Fables of La Fontaine", "bidpai": "Fables of Bidpai", "pilpay": "Fables of Bidpai",
    "hitopadesa": "Fables from the Hitopadesa", "krylov": "Fables of Krylov", "krilof": "Fables of Krylov",
    "yriarte": "Fables of Yriarte", "iriarte": "Fables of Yriarte",
    # The Grimms' Household Tales (Hunt), one chapter a tale
    "grimm": "Grimm's Household Tales", "grimms": "Grimm's Household Tales", "grimm's": "Grimm's Household Tales",
    "grimms fairy tales": "Grimm's Household Tales", "grimm's fairy tales": "Grimm's Household Tales",
    "household tales": "Grimm's Household Tales", "grimm's household tales": "Grimm's Household Tales",
    "grimms household tales": "Grimm's Household Tales", "kinder und hausmarchen": "Grimm's Household Tales",
    # 36 Lessons of Vivec
    "vivec": "Vivec",
    "lessons of vivec": "Vivec",
    "36 lessons of vivec": "Vivec",
    "sermons of vivec": "Vivec",
    # Delphi
    "delphic maxims": "Delphic Maxims",
    "delphi maxims": "Delphic Maxims",
    "maxims": "Delphic Maxims",
    "delphic oracles": "Oracular Statements",
    "delphi oracles": "Oracular Statements",
    "oracular statements": "Oracular Statements",
    "pythia": "Oracular Statements",
    "pythian oracles": "Oracular Statements",
    # ── Church Fathers (patristics) ────────────────────────────────────────────
    # the councils (church_councils.json)
    "council of nicea": "Council of Nicaea", "first council of nicaea": "Council of Nicaea", "nicaea": "Council of Nicaea",
    "nicene canons": "Canons of Nicaea", "canons of nicea": "Canons of Nicaea",
    "constantinople i": "First Council of Constantinople", "first council of constantinople": "First Council of Constantinople",
    "constantinople ii": "Second Council of Constantinople", "constantinople iii": "Third Council of Constantinople",
    "chalcedon": "Council of Chalcedon", "ephesus": "Council of Ephesus",
    "council in trullo": "Canons of the Council in Trullo", "canons of trullo": "Canons of the Council in Trullo",
    "quinisext": "Canons of the Council in Trullo", "quinisext council": "Canons of the Council in Trullo",
    "african code": "Canons of Carthage", "code of canons of the african church": "Canons of Carthage",
    "second council of nicea": "Second Council of Nicaea", "nicaea ii": "Second Council of Nicaea",
    "seventh ecumenical council": "Second Council of Nicaea",
    "apostolical canons": "Apostolic Canons", "canons of the apostles": "Apostolic Canons",
    # ANF 7-9 additions
    "constitutions of the holy apostles": "Apostolic Constitutions",
    "liturgy of james": "Liturgy of St. James", "liturgy of st james": "Liturgy of St. James",
    "liturgy of mark": "Liturgy of St. Mark", "liturgy of st mark": "Liturgy of St. Mark",
    "addai and mari": "Liturgy of Addai and Mari", "anaphora of addai and mari": "Liturgy of Addai and Mari",
    "doctrine of addai": "The Teaching of Addaeus the Apostle", "teaching of addai": "The Teaching of Addaeus the Apostle",
    "mara bar serapion": "Letter of Mara, Son of Serapion", "letter of mara bar serapion": "Letter of Mara, Son of Serapion",
    "testament of abraham": "The Testament of Abraham: First Version",
    "nativity hymns": "Hymns on the Nativity", "epiphany hymns": "Hymns for the Feast of the Epiphany",
    # Budge's Paradise of the Holy Fathers, Vol. II (desert_fathers.json)
    "desert fathers": "Sayings of the Desert Fathers", "sayings of the fathers": "Sayings of the Desert Fathers",
    "sayings of the holy fathers": "Sayings of the Desert Fathers", "apophthegmata": "Sayings of the Desert Fathers",
    "apophthegmata patrum": "Sayings of the Desert Fathers", "paradise of the fathers": "Sayings of the Desert Fathers",
    "paradise of the holy fathers": "Sayings of the Desert Fathers",
    "paradise of palladius": "The Paradise of Palladius",
    "rule of pachomius": "The Rule of Pachomius", "pachomian rule": "The Rule of Pachomius",
    "history of the monks": "The History of the Monks of Egypt", "historia monachorum": "The History of the Monks of Egypt",
    "history of the monks of egypt": "The History of the Monks of Egypt",
    # the Philokalia (philokalia.json)
    "chapters on love": "Four Hundred Texts on Love", "four hundred chapters on love": "Four Hundred Texts on Love",
    "on prayer evagrios": "On Prayer: One Hundred and Fifty-Three Texts (Evagrios the Solitary)",
    "on the spiritual law": "On the Spiritual Law: Two Hundred Texts",
    "on watchfulness and holiness": "On Watchfulness and Holiness (Hesychios the Priest)",
    "gnomic anthology": "A Gnomic Anthology (Ilias the Presbyter)",
    "treasury of divine knowledge": "A Treasury of Divine Knowledge",
    "hagioretic tome": "The Declaration of the Holy Mountain in Defense of Those who Devoutly Practice A Life of Stillness",
    "exhortation to the heathen": "Exhortation to the Heathen",
    "protrepticus": "Exhortation to the Heathen",
    "the instructor": "The Instructor",
    "paedagogus": "The Instructor",
    "stromateis": "Stromateis", "stromata": "Stromateis", "miscellanies": "Stromateis",
    "apologeticum": "Apology",
    "on the prescription of heretics": "On the Prescription of Heretics",
    "de praescriptione": "On the Prescription of Heretics",
    "against marcion": "Against Marcion", "adversus marcionem": "Against Marcion",
    "de anima tert": "On the Soul",
    "on the resurrection of the flesh": "On the Resurrection of the Flesh",
    "on baptism": "On Baptism", "on repentance": "On Repentance",
    "scorpiace": "Scorpiace", "against hermogenes": "Against Hermogenes",
    "against praxeas": "Against Praxeas",
    "de principiis": "De Principiis", "on first principles": "De Principiis",
    "peri archon": "De Principiis",
    "against celsus": "Against Celsus", "contra celsum": "Against Celsus",
    "philocalia": "Philocalia",
    "on the incarnation": "On the Incarnation", "de incarnatione": "On the Incarnation",
    "discourses against the arians": "Discourses Against the Arians",
    "orations against the arians": "Discourses Against the Arians",
    "life of antony": "Life of Antony", "vita antonii": "Life of Antony",
    "on the decrees of nicaea": "On the Decrees of Nicaea",
    "de decretis": "On the Decrees of Nicaea",
    "letters of athanasius": "Letters of Athanasius",
    "hexaemeron": "Hexaemeron", "on the six days": "Hexaemeron",
    "de spiritu sancto": "On the Holy Spirit",
    "letters of basil": "Letters of Basil",
    "address to young men": "Address to Young Men",
    "on the soul and the resurrection": "On the Soul and the Resurrection",
    "the great catechism": "The Great Catechism",
    "oratio catechetica": "The Great Catechism",
    "on the making of man": "On the Making of Man",
    "de opificio hominis": "On the Making of Man",
    "life of macrina": "Life of Macrina",
    "against eunomius": "Against Eunomius",
    "letters of gregory of nyssa": "Letters of Gregory of Nyssa",
    "orations": "Orations", "theological orations": "Orations",
    "orations against julian": "Orations Against Julian",
    "letters of gregory nazianzen": "Letters of Gregory Nazianzen",
    "homilies on matthew": "Homilies on Matthew",
    "homilies on john": "Homilies on John",
    "homilies on acts": "Homilies on Acts",
    "homilies on romans": "Homilies on Romans",
    "homilies on 1 corinthians": "Homilies on 1 Corinthians",
    "homilies on 2 corinthians": "Homilies on 2 Corinthians",
    "homilies on ephesians": "Homilies on Ephesians",
    "homilies on philippians": "Homilies on Philippians",
    "homilies on colossians": "Homilies on Colossians",
    "homilies on hebrews": "Homilies on Hebrews",
    "homilies on the statues": "Homilies on the Statues",
    "on the priesthood": "On the Priesthood", "de sacerdotio": "On the Priesthood",
    "confessiones": "Confessions",
    "city of god": "City of God", "de civitate dei": "City of God",
    "on christian doctrine": "On Christian Doctrine",
    "de doctrina christiana": "On Christian Doctrine",
    "enchiridion": "Enchiridion",
    "letters of augustine": "Letters of Augustine",
    "on nature and grace": "On Nature and Grace",
    "on the spirit and the letter": "On the Spirit and the Letter",
    "de spiritu et littera": "On the Spirit and the Letter",
    "on the morals of the catholic church": "On the Morals of the Catholic Church",
    "letters of jerome": "Letters",
    "lives of illustrious men": "Lives of Illustrious Men",
    "de viris illustribus": "Lives of Illustrious Men",
    "against jovinianus": "Against Jovinianus",
    "adversus jovinianum": "Against Jovinianus",
    "commentary on daniel": "Commentary on Daniel",
    "against nestorius": "Against Nestorius",
    "adversus nestorii blasphemias": "Against Nestorius",
    "commentary on luke": "Commentary on Luke",
    "that christ is one": "That Christ is One",
    "quod unus sit christus": "That Christ is One",
    "scholia on the incarnation": "Scholia on the Incarnation",
    "sermons of leo": "Sermons",
    "letters of leo": "Letters of Leo",
    "tome to flavian": "Letters of Leo", "tome": "Letters of Leo",
    "exposition of the orthodox faith": "Exposition of the Orthodox Faith",
    "orthodox faith": "Exposition of the Orthodox Faith",
    "de fide orthodoxa": "Exposition of the Orthodox Faith",
    "discourses to hypatius": "Discourses to Hypatius",
    "against mani": "Against Mani",
    "nisibene hymns": "Nisibene Hymns",
    "dialogues": "Dialogues",
    "pastoral rule": "Pastoral Rule", "regula pastoralis": "Pastoral Rule",
    "letters of gregory the great": "Letters of Gregory the Great",

    # ── Extended Patristics (from epub extraction) ─────────────────────────────
    # Ambrose
    "ambrose": "On the Christian Faith (De fide)",
    "de fide": "On the Christian Faith (De fide)",
    "on the christian faith": "On the Christian Faith (De fide)",
    "on the mysteries ambrose": "On the Mysteries",
    "on repentance ambrose": "On Repentance",
    "on the duties of the clergy": "On the Duties of the Clergy",
    "de officiis": "On the Duties of the Clergy",
    "concerning virgins": "Concerning Virgins",
    "concerning widows": "Concerning Widows",
    "on the holy spirit ambrose": "On the Holy Spirit",
    # Aphrahat
    "aphrahat": "Demonstrations",
    "demonstrations": "Demonstrations",
    "persian sage": "Demonstrations",
    # Athenagoras
    "athenagoras": "A Plea for the Christians",
    "a plea for the christians": "A Plea for the Christians",
    "legatio": "A Plea for the Christians",
    "the resurrection of the dead": "The Resurrection of the Dead",
    # Clement of Rome
    "first epistle clement": "First Epistle",     # ("1clement" is 1 Clement, in the Apostolic Fathers)
    "clementine homilies": "Clementine Homilies",
    "recognitions of clement": "Recognitions",
    # Cyprian
    "cyprian": "The Treatises of Cyprian",
    "treatises of cyprian": "The Treatises of Cyprian",
    "the seventh council of carthage": "The Seventh Council of Carthage",
    # Cyril of Jerusalem
    "cyril of jerusalem": "Catechetical Lectures",
    "catechetical lectures": "Catechetical Lectures",
    "mystagogical catecheses": "Catechetical Lectures",
    # Eusebius
    "eusebius": "Church History",
    "ecclesiastical history eusebius": "Church History",
    "historia ecclesiastica": "Church History",
    "church history eusebius": "Church History",
    "life of constantine": "Life of Constantine",
    # Gregory Thaumaturgus
    "gregory thaumaturgus": "The Oration and Panegyric Addressed to Origen",
    "gregory the wonderworker": "The Oration and Panegyric Addressed to Origen",
    "panegyric to origen": "The Oration and Panegyric Addressed to Origen",
    # Hermas
    "the shepherd": "Shepherd of Hermas",
    "pastor of hermas": "Shepherd of Hermas",
    # Hilary of Poitiers
    "hilary": "On the Trinity",
    "hilary of poitiers": "On the Trinity",
    "on the trinity hilary": "On the Trinity",
    "on the councils": "On the Councils, or the Faith of the Easterns",
    "de synodis hilary": "On the Councils, or the Faith of the Easterns",
    # Hippolytus
    "hippolytus": "The Refutation of All Heresies",
    "refutation of all heresies": "The Refutation of All Heresies",
    "philosophumena": "The Refutation of All Heresies",
    "the antichrist hippolytus": "The Antichrist",
    "on the antichrist": "The Antichrist",
    # Ignatius of Antioch (epub versions)
    "epistle to the ephesians ignatius": "Epistle to the Ephesians",
    "epistle to the magnesians": "Epistle to the Magnesians",
    "epistle to the trallians": "Epistle to the Trallians",
    "epistle to the romans ignatius": "Epistle to the Romans",
    "epistle to the philadelphians": "Epistle to the Philadelphians",
    "epistle to the smyrnaeans": "Epistle to the Smyrnæans",
    "epistle to polycarp": "Epistle to Polycarp",
    # Irenaeus
    "irenaeus": "Against Heresies",
    "against heresies": "Against Heresies",
    "adversus haereses": "Against Heresies",
    "adv haer": "Against Heresies",
    "adv. haer.": "Against Heresies",
    "irenaeus against heresies": "Against Heresies",
    # John Cassian
    "john cassian": "Institutes",
    "cassian": "Institutes",
    "institutes cassian": "Institutes",
    "conferences cassian": "Conferences",
    "the conferences": "Conferences",
    "collationes": "Conferences",
    "de incarnatione cassian": "On the Incarnation of the Lord (Against Nestorius)",
    # Justin Martyr
    "justin": "First Apology",
    "justin martyr": "First Apology",
    "first apology justin": "First Apology",
    "second apology justin": "Second Apology",
    "dialogue with trypho": "Dialogue with Trypho",
    "trypho": "Dialogue with Trypho",
    # Lactantius
    "lactantius": "The Divine Institutes",
    "divine institutes": "The Divine Institutes",
    "institutiones divinae": "The Divine Institutes",
    "on the anger of god": "On the Anger of God",
    "de ira dei": "On the Anger of God",
    "on the workmanship of god": "On the Workmanship of God",
    "de opificio dei": "On the Workmanship of God",
    "manner of persecution": "Of the Manner In Which the Persecutors Died",
    "de mortibus persecutorum": "Of the Manner In Which the Persecutors Died",
    # Mathetes / Diognetus
    "mathetes": "Epistle to Diognetus",
    "epistle to diognetus": "Epistle to Diognetus",
    "diognetus": "Epistle to Diognetus",
    "to diognetus": "Epistle to Diognetus",
    # Methodius
    "methodius": "The Banquet of the Ten Virgins",
    "banquet of the ten virgins": "The Banquet of the Ten Virgins",
    "symposium methodius": "The Banquet of the Ten Virgins",
    # Minucius Felix
    "minucius felix": "Octavius",
    "octavius": "Octavius",
    # Novatian
    "novatian": "Treatise Concerning the Trinity",
    "novatian trinity": "Treatise Concerning the Trinity",
    "on the jewish meats": "On the Jewish Meats",
    # Polycarp (epub)
    "polycarp": "Epistle to the Philippians",
    "epistle to the philippians polycarp": "Epistle to the Philippians",
    "martyrdom of polycarp": "The Martyrdom of Polycarp",
    # Socrates Scholasticus
    "socrates scholasticus": "Ecclesiastical History",
    "ecclesiastical history socrates": "Ecclesiastical History",
    # Sozomen
    "sozomen": "Ecclesiastical History",
    "ecclesiastical history sozomen": "Ecclesiastical History",
    # Sulpitius Severus
    "sulpitius severus": "On the Life of St. Martin",
    "life of st martin": "On the Life of St. Martin",
    "life of martin": "On the Life of St. Martin",
    # Tatian
    "tatian": "Address to the Greeks",
    "address to the greeks": "Address to the Greeks",
    "oratio ad graecos": "Address to the Greeks",
    "diatessaron": "The Diatessaron",
    "the diatessaron": "The Diatessaron",
    # Theodoret
    "theodoret": "Ecclesiastical History",
    "ecclesiastical history theodoret": "Ecclesiastical History",
    "letters of theodoret": "Letters",
    "dialogues theodoret": 'Dialogues ("Eranistes" or "Polymorphus")',
    "eranistes": 'Dialogues ("Eranistes" or "Polymorphus")',
    # Theophilus
    "theophilus": "Theophilus to Autolycus",
    "theophilus to autolycus": "Theophilus to Autolycus",
    "ad autolycum": "Theophilus to Autolycus",
    # Victorinus
    "victorinus": "Commentary on the Apocalypse of the Blessed John",
    "commentary on the apocalypse": "Commentary on the Apocalypse of the Blessed John",
    "on the creation of the world victorinus": "On the Creation of the World",
    # Vincent of Lerins
    "vincent of lerins": "Commonitory for the Antiquity and Universality of the Catholic Faith",
    "commonitory": "Commonitory for the Antiquity and Universality of the Catholic Faith",
    "vincentian canon": "Commonitory for the Antiquity and Universality of the Catholic Faith",
    "commonitorium": "Commonitory for the Antiquity and Universality of the Catholic Faith",
    # Eusebius
    "life of constantine": "Life of Constantine",
    "vita constantini": "Life of Constantine",
    # Origen extensions
    "commentary on john origen": "Commentary on the Gospel of John",
    "commentary on matthew origen": "Commentary on the Gospel of Matthew",
    # Augustine extensions  
    "on the trinity augustine": "On the Holy Trinity",
    "on grace and free will": "On Grace and Free Will",
    "on baptism augustine": "On Baptism, Against the Donatists",
    "tractates on john": "Tractates on the Gospel of John",
    "expositions on the psalms": "The Enarrations, or Expositions, on the Psalms",
    "enarrations on the psalms": "The Enarrations, or Expositions, on the Psalms",
    "harmony of the gospels": "The Harmony of the Gospels",
    "on the sermon on the mount": "Our Lord's Sermon on the Mount",
    # Chrysostom extensions
    "commentary on galatians": "Commentary on Galatians",
    "on the priesthood": "On the Priesthood",
    # Jerome extensions
    "against jovinianus": "Against Jovinianus",
    "against vigilantius": "Against Vigilantius",
    "life of malchus": "The Life of Malchus, the Captive Monk",
    "life of hilarion": "The Life of S. Hilarion",
    "life of paul the hermit": "The Life of Paulus the First Hermit",
    "against the pelagians jerome": "Against the Pelagians",


    # ── Pearse corpus — new authors ───────────────────────────────────────────
    # Agapius of Hierapolis
    "agapius": "Universal History",
    "agapius of hierapolis": "Universal History",
    "universal history agapius": "Universal History",
    # Asterius of Amasea
    "asterius": "Sermons",
    "asterius of amasea": "Sermons",
    "sermons asterius": "Sermons",
    # Cosmas Indicopleustes
    "cosmas": "The Christian Topography",
    "cosmas indicopleustes": "The Christian Topography",
    "christian topography": "The Christian Topography",
    # Dioscorus of Alexandria
    "dioscorus": "Letter to Shenouda",
    "dioscorus of alexandria": "Letter to Shenouda",
    # Epiphanius of Salamis
    "epiphanius": "On Weights and Measures",
    "epiphanius of salamis": "On Weights and Measures",
    "weights and measures": "On Weights and Measures",
    # Eunomius of Cyzicus
    "eunomius": "The First Apology",
    "eunomius of cyzicus": "The First Apology",
    "first apology eunomius": "The First Apology",
    # Evagrius Scholasticus
    "evagrius": "Ecclesiastical History",
    "evagrius scholasticus": "Ecclesiastical History",
    "ecclesiastical history evagrius": "Ecclesiastical History",
    # Gildas
    "gildas": "The Ruin of Britain",
    "gildas the wise": "The Ruin of Britain",
    "ruin of britain": "The Ruin of Britain",
    "de excidio": "The Ruin of Britain",
    # Hermias
    "hermias": "Derision of Gentile Philosophers",
    "hermias the philosopher": "Derision of Gentile Philosophers",
    "derision of gentile philosophers": "Derision of Gentile Philosophers",
    "irrisio": "Derision of Gentile Philosophers",
    # Isidore of Seville
    "isidore": "Chronicon",
    "isidore of seville": "Chronicon",
    "chronicon isidore": "Chronicon",
    # John bar Penkaye
    "john bar penkaye": "Summary History of the World (Book 15: Rise of Islam)",
    "bar penkaye": "Summary History of the World (Book 15: Rise of Islam)",
    "resh melle": "Summary History of the World (Book 15: Rise of Islam)",
    # John of Ephesus
    "john of ephesus": "Ecclesiastical History (Third Part)",
    "ecclesiastical history john of ephesus": "Ecclesiastical History (Third Part)",
    # Leontius of Byzantium
    "leontius": "Against the Frauds of the Apollinarists",
    "leontius of byzantium": "Against the Frauds of the Apollinarists",
    "against the apollinarists": "Against the Frauds of the Apollinarists",
    # Macarius Magnes
    "macarius magnes": "Apocriticus",
    "macarius": "Apocriticus",
    "apocriticus": "Apocriticus",
    # Nestorius
    "nestorius": "The Bazaar of Heracleides",
    "bazaar of heracleides": "The Bazaar of Heracleides",
    "heracleides": "The Bazaar of Heracleides",
    # Optatus of Milevis
    "optatus": "Against the Donatists",
    "optatus of milevis": "Against the Donatists",
    "against the donatists": "Against the Donatists",
    # Pacian of Barcelona
    "pacian": "Letters to Sympronian",
    "pacian of barcelona": "Letters to Sympronian",
    "paraenesis pacian": "Paraenesis on Penance",
    "discourse on baptism pacian": "Discourse on Baptism",
    # Palladius
    "palladius": "The Lausiac History",
    "lausiac history": "The Lausiac History",
    "historia lausiaca": "The Lausiac History",
    "dialogue on chrysostom": "Dialogue on the Life of St. John Chrysostom",
    # Philostorgius
    "philostorgius": "Ecclesiastical History (Epitome)",
    "ecclesiastical history philostorgius": "Ecclesiastical History (Epitome)",
    # Philoxenus of Hierapolis
    "philoxenus": "13 Ascetic Discourses",
    "philoxenus of hierapolis": "13 Ascetic Discourses",
    "ascetic discourses philoxenus": "13 Ascetic Discourses",
    # Photius
    "photius": "Bibliotheca (Codices 1-165)",
    "photius of constantinople": "Bibliotheca (Codices 1-165)",
    "bibliotheca": "Bibliotheca (Codices 1-165)",
    "myriobiblion": "Bibliotheca (Codices 1-165)",
    # Possidius
    "possidius": "Life of St. Augustine",
    "life of st augustine": "Life of St. Augustine",
    "vita augustini": "Life of St. Augustine",
    # Pseudo-Hegesippus
    "pseudo hegesippus": "On the Ruin of Jerusalem",
    "hegesippus": "On the Ruin of Jerusalem",
    "on the ruin of jerusalem": "On the Ruin of Jerusalem",
    "de excidio hierosolymitano": "On the Ruin of Jerusalem",
    # Salvian
    "salvian": "On the Government of God",
    "on the government of god": "On the Government of God",
    "de gubernatione dei": "On the Government of God",
    # Severus of Antioch
    "severus of antioch": "Letters",
    "severus antioch": "Letters",
    # Sidonius Apollinaris
    "sidonius": "Letters",
    "sidonius apollinaris": "Letters",
    "letters sidonius": "Letters",
    # Theodore of Mopsuestia
    "theodore of mopsuestia": "Commentary on the Nicene Creed",
    "theodore mopsuestia": "Commentary on the Nicene Creed",
    "commentary nicene creed theodore": "Commentary on the Nicene Creed",
    "lords prayer sacraments": "Commentary on the Lord's Prayer and Sacraments",
    # Timothy I
    "timothy i": "Apology for Christianity to Caliph Al-Mahdi",
    # Definitions of Hermes
    "definitions of hermes": "Definitions of Hermes Trismegistus to Asclepius",
    "definitiones hermetis": "Definitions of Hermes Trismegistus to Asclepius",
    "emerald tablet": "The Emerald Tablet",
    "tabula smaragdina": "The Emerald Tablet",
    "hermetic definitions": "Definitions of Hermes Trismegistus to Asclepius",
    "definitions hermes asclepius": "Definitions of Hermes Trismegistus to Asclepius",

    # Bede
    "bede": "Ecclesiastical History of the English People",
    "venerable bede": "Ecclesiastical History of the English People",
    "bede ecclesiastical history": "Ecclesiastical History of the English People",
    "ecclesiastical history england": "Ecclesiastical History of the English People",
    "historia ecclesiastica bede": "Ecclesiastical History of the English People",
    "historia ecclesiastica gentis anglorum": "Ecclesiastical History of the English People",

    # Golden Legend
    "golden legend": "The Golden Legend",
    "legenda aurea": "The Golden Legend",
    "voragine": "The Golden Legend",
    "jacobus de voragine": "The Golden Legend",
    "lives of the saints": "The Golden Legend",
    # Athanasius's and Basil's letters; Aristotle filled in (scripts/build_library_gaps.py)
    "festal letters": "Festal Letters of Athanasius",
    "athanasius festal letters": "Festal Letters of Athanasius",
    "festal letter": "Festal Letters of Athanasius",
    "athanasius letters": "Letters of Athanasius",
    "basil letters": "Letters of Basil",
    "basil's letters": "Letters of Basil",
    "generation of animals": "On the Generation of Animals",
    "de generatione animalium": "On the Generation of Animals",
    "on youth and old age": "On Youth, Old Age, Life and Death",
    "youth and old age": "On Youth, Old Age, Life and Death",
    "on life and death": "On Youth, Old Age, Life and Death",
    "on breathing": "On Youth, Old Age, Life and Death",
    "patriarch timothy": "Apology for Christianity to Caliph Al-Mahdi",
    "timothy apology": "Apology for Christianity to Caliph Al-Mahdi",
    "apology to al-mahdi": "Apology for Christianity to Caliph Al-Mahdi",
    # Pearse supplements to existing authors
    "proof of apostolic preaching": "The Proof of the Apostolic Preaching",
    "epideixis": "The Proof of the Apostolic Preaching",
    "demonstratio evangelica": "Demonstratio Evangelica",
    "proof of the gospel": "Demonstratio Evangelica",
    "praeparatio evangelica": "Praeparatio Evangelica",
    "preparation of the gospel": "Praeparatio Evangelica",
    "theophania eusebius": "Theophania",
    "against hierocles": "Against Hierocles",
    "martyrs in palestine": "History of the Martyrs in Palestine",
    "letters of ambrose": "Letters of Ambrose",
    "against the jews chrysostom": "Against the Jews",
    "adversus judaeos": "Against the Jews",
    "four discourses on lazarus": "Four Discourses on Lazarus",
    "commentary on romans theodoret": "Commentary on Romans",
    "against diodore and theodore": "Against Diodore and Theodore (Fragments)",

    # ── Mishnah (via Sefaria — these are handled as live lookups, ──────────
    # aliases here just help _suggest_books find them)
    "mishnah": "_sefaria_mishnah", "mishna": "_sefaria_mishnah",
    "m.": "_sefaria_mishnah",
    # ── Babylonian Talmud (via Sefaria) ─────────────────────────────────────────
    "talmud": "_sefaria_talmud", "gemara": "_sefaria_talmud",
    "bavli": "_sefaria_talmud", "babylonian talmud": "_sefaria_talmud", "talmud bavli": "_sefaria_talmud",
    "bt": "_sefaria_talmud",
    # ── Zohar (via Sefaria) ────────────────────────────────────────────────
    "zohar": "_sefaria_zohar", "the zohar": "_sefaria_zohar",
    "sefer hazohar": "_sefaria_zohar",
    # ── Jerusalem Talmud (via Sefaria) ───────────────────────────────────────
    "jerusalem talmud": "_sefaria_yerushalmi", "yerushalmi": "_sefaria_yerushalmi",
    "talmud yerushalmi": "_sefaria_yerushalmi", "palestinian talmud": "_sefaria_yerushalmi",
    "jt": "_sefaria_yerushalmi",
    # ── Tosefta (via Sefaria) ─────────────────────────────────────────────────
    "tosefta": "_sefaria_tosefta", "tosef": "_sefaria_tosefta",
    # ── Targumim (via Sefaria) ────────────────────────────────────────────────
    "targum onkelos": "_sefaria_targum", "onkelos": "_sefaria_targum",
    "targum jonathan": "_sefaria_targum", "targum yonatan": "_sefaria_targum",
    "targum pseudo-jonathan": "_sefaria_targum", "pseudo-jonathan": "_sefaria_targum",
    "targum neofiti": "_sefaria_targum", "neofiti": "_sefaria_targum",
    "targum": "_sefaria_targum",
    # ── Midrash Rabbah (via Sefaria) ──────────────────────────────────────────
    "bereshit rabbah": "_sefaria_midrash", "genesis rabbah": "_sefaria_midrash",
    "shemot rabbah": "_sefaria_midrash", "exodus rabbah": "_sefaria_midrash",
    "vayikra rabbah": "_sefaria_midrash", "leviticus rabbah": "_sefaria_midrash",
    "bamidbar rabbah": "_sefaria_midrash", "numbers rabbah": "_sefaria_midrash",
    "devarim rabbah": "_sefaria_midrash", "deuteronomy rabbah": "_sefaria_midrash",
    "ruth rabbah": "_sefaria_midrash", "esther rabbah": "_sefaria_midrash",
    "eichah rabbah": "_sefaria_midrash", "lamentations rabbah": "_sefaria_midrash",
    "shir hashirim rabbah": "_sefaria_midrash", "song of songs rabbah": "_sefaria_midrash",
    "kohelet rabbah": "_sefaria_midrash", "ecclesiastes rabbah": "_sefaria_midrash",
    "midrash rabbah": "_sefaria_midrash", "midrash": "_sefaria_midrash",
    # ── Mishneh Torah (via Sefaria) ──────────────────────────────────────────────
    "mishneh torah": "_sefaria_mishneh_torah", "yad hachazakah": "_sefaria_mishneh_torah",
    "rambam": "_sefaria_mishneh_torah", "maimonides": "_sefaria_mishneh_torah",
    # ── Guide for the Perplexed (via Sefaria) ─────────────────────────────────
    "guide for the perplexed": "_sefaria_guide", "moreh nevukhim": "_sefaria_guide",
    "moreh nebukim": "_sefaria_guide", "guide of the perplexed": "_sefaria_guide",
    "mechilta": "_sefaria_midrash", "mekhilta": "_sefaria_midrash",
    "sifra": "_sefaria_midrash", "sifre": "_sefaria_midrash", "sifrei": "_sefaria_midrash",
    # ── Kabbalah (via Sefaria) ────────────────────────────────────────────────
    "sefer yetzirah": "_sefaria_kabbalah", "book of formation": "_sefaria_kabbalah",
    "sefer habahir": "_sefaria_kabbalah", "bahir": "_sefaria_kabbalah",
    "tikkunei zohar": "_sefaria_kabbalah", "tikkunim": "_sefaria_kabbalah",
    "zohar chadash": "_sefaria_kabbalah",
    "etz chaim": "_sefaria_kabbalah", "tree of life": "_sefaria_kabbalah",
    "tanya": "_sefaria_kabbalah",
    # ── Hadith (via fawazahmed0 CDN) ───────────────────────────────────────
    "hadith": "_hadith", "hadith bukhari": "_hadith",
    "bukhari": "_hadith", "sahih bukhari": "_hadith",
    "muslim": "_hadith", "sahih muslim": "_hadith",
    "abu dawud": "_hadith", "tirmidhi": "_hadith",
    "nasai": "_hadith", "ibn majah": "_hadith",
    "muwatta": "_hadith", "nawawi": "_hadith", "nawawi 40": "_hadith",
    "dehlawi": "_hadith", "shah waliullah": "_hadith", "forty hadith of dehlawi": "_hadith",
    "qudsi": "_hadith", "hadith qudsi": "_hadith", "forty hadith qudsi": "_hadith",
    "1ne": "1 Nephi", "1 ne": "1 Nephi", "1nep": "1 Nephi",
    "2ne": "2 Nephi", "2 ne": "2 Nephi", "2nep": "2 Nephi",
    "jacob": "Jacob",
    "enos": "Enos",
    "jarom": "Jarom",
    "omni": "Omni",
    "wom": "Words of Mormon",
    "mosiah": "Mosiah",
    "alma": "Alma",
    "hel": "Helaman",
    "3ne": "3 Nephi", "3 ne": "3 Nephi",
    "4ne": "4 Nephi", "4 ne": "4 Nephi",
    "morm": "Mormon",
    "ether": "Ether",
    "moro": "Moroni",
    # ── LDS: D&C ──────────────────────────────────────────────────────────
    "dc": "Doctrine and Covenants", "d&c": "Doctrine and Covenants",
    "d and c": "Doctrine and Covenants",
    # ── LDS: Pearl of Great Price ──────────────────────────────────────────
    "moses": "Moses",
    "abr": "Abraham",
    "jsm": "Joseph Smith—Matthew", "js-m": "Joseph Smith—Matthew",
    "jsh": "Joseph Smith—History", "js-h": "Joseph Smith—History",
    "aof": "Articles of Faith",

    # ── Ancient Near East ──────────────────────────────────────────────────────
    # Baal Cycle — cite as !verse Baal 1:5  (episode : section)
    "baal and yamm":       "Baal and Yamm",
    "baal yamm":           "Baal and Yamm",
    "baal 1":              "Baal and Yamm",
    "the palace of baal":  "The Palace of Baal",
    "palace of baal":      "The Palace of Baal",
    "baal palace":         "The Palace of Baal",
    "baal 2":              "The Palace of Baal",
    "baal and mot":        "Baal and Mot",
    "baal mot":            "Baal and Mot",
    "baal 3":              "Baal and Mot",
    # Mu'allaqat — cite as !verse Muallaqat 1:5  (ode : stanza)
    "muallaqat 1":         "Muallaqat: Imru' al-Qais",
    "muallaqat imru":      "Muallaqat: Imru' al-Qais",
    "imru al-qais":        "Muallaqat: Imru' al-Qais",
    "imru":                "Muallaqat: Imru' al-Qais",
    "muallaqat 2":         "Muallaqat: Tarafa ibn al-'Abd",
    "tarafa":              "Muallaqat: Tarafa ibn al-'Abd",
    "muallaqat 3":         "Muallaqat: Zuhayr ibn Abi Sulma",
    "zuhayr":              "Muallaqat: Zuhayr ibn Abi Sulma",
    "muallaqat 4":         "Muallaqat: Labid ibn Rabi'ah",
    "labid":               "Muallaqat: Labid ibn Rabi'ah",
    "muallaqat 5":         "Muallaqat: Antara ibn Shaddad",
    "antara":              "Muallaqat: Antara ibn Shaddad",
    "antar":               "Muallaqat: Antara ibn Shaddad",
    "muallaqat 6":         "Muallaqat: Amr ibn Kulthum",
    "amr ibn kulthum":     "Muallaqat: Amr ibn Kulthum",
    "muallaqat 7":         "Muallaqat: Al-Harith ibn Hilliza",
    "al-harith":           "Muallaqat: Al-Harith ibn Hilliza",
    "harith":              "Muallaqat: Al-Harith ibn Hilliza",
    # Ahikar
    "ahikar": "The Story of Ahikar",
    "story of ahikar": "The Story of Ahikar",
    "ahiqar": "The Story of Ahikar",
    # Hymn to the Aten
    "hymn to the aten": "The Great Hymn to the Aten",
    "great hymn to the aten": "The Great Hymn to the Aten",
    "aten": "The Great Hymn to the Aten",
    "akhenaten hymn": "The Great Hymn to the Aten",
    # Gilgamesh — individual tablets via "Gilgamesh N" syntax handled by intercept
    "gilgamesh":           "Gilgamesh — Tablet First",
    # Book of the Dead
    "book of the dead":    "Book of the Dead",
    "book of dead":        "Book of the Dead",
    "pert em hru":         "Book of the Dead",
    "coming forth by day": "Book of the Dead",
    # Leiden Hymns
    "leiden hymns": "The Leiden Hymns",
    "hymns to amun": "The Leiden Hymns",
    "leiden": "The Leiden Hymns",
    # Instruction of Amenemope
    "amenemope": "The Instruction of Amenemope",
    "instruction of amenemope": "The Instruction of Amenemope",
    # Book of Two Ways
    "book of two ways": "The Book of Two Ways",
    "two ways": "The Book of Two Ways",
    "coffin texts 1042": "The Book of Two Ways",
    # Other names for Bible books, which the closest-name guess had answered with the wrong book
    # (Ecclesiasticus as Ecclesiastes, Acts of the Apostles as the Acts of Thaddaeus)
    "song of songs": "Song of Solomon",
    "canticles": "Song of Solomon",
    "canticle of canticles": "Song of Solomon",
    "ecclesiasticus": "Sirach",
    "acts of the apostles": "Acts",
    "the acts": "Acts",
    "tobias": "Tobit",
    "josue": "Joshua",
    # Cyprian's twelfth treatise (scripts/build_fathers.py)
    "testimonies against the jews": "Three Books of Testimonies Against the Jews",
    "testimonies": "Three Books of Testimonies Against the Jews",
    "ad quirinum": "Three Books of Testimonies Against the Jews",
}

# Priority order when the same book name exists in multiple corpora
# (first match wins unless the user specifies a corpus)
# Traditions as users name them -> (label, the corpora that hold them). Used by
# `!search ... in:buddhist` and `!theme` (which shows one passage per tradition,
# in this order).
TRADITIONS = {
    "bible":     ("📖 Bible", ("kjv",)),
    "jewish":    ("✡️ Jewish", ("jewish", "qumran")),
    "christian": ("⛪ Christian writers", ("apostolic_fathers", "patristics", "medieval", "reformation")),
    "apocrypha": ("👼 Apocrypha", ("charles", "brenton", "nt_apocrypha")),
    "islamic":   ("☪️ Islamic", ("quran",)),
    "sufi":      ("🌹 Sufi", ("sufi",)),
    "hindu":     ("🕉️ Hindu", ("dharmic",)),
    "sikh":      ("🪯 Sikh", ("sikh",)),
    "jain":      ("🤚 Jain", ("jain",)),
    "buddhist":  ("☸️ Buddhist", ("buddhist",)),
    "chinese":   ("☯️ Chinese", ("chinese",)),
    "shinto":    ("⛩️ Shinto", ("shinto",)),
    "zoroastrian": ("🔥 Zoroastrian", ("zoroastrian",)),
    "classical": ("🏛️ Greek & Roman", ("classical",)),
    "gnostic":   ("🧿 Gnostic", ("gnostic",)),
    "norse":     ("🌲 Norse", ("norse",)),
    "finnish":   ("🦢 Finnish", ("finnish",)),
    "celtic":    ("☘️ Celtic", ("celtic",)),
    "ballads":   ("🎻 Folk tales & ballads", ("ballads",)),
    "arthurian": ("⚔️ Arthurian legend", ("arthurian",)),
    "neareast":  ("🌙 Ancient Near East", ("ancient_near_east",)),
    "mesoamerican": ("🌽 Mesoamerican", ("mesoamerican",)),
    "bahai":     ("🌍 Baháʼí", ("bahai",)),
    "lds":       ("📯 Latter-day Saint", ("lds",)),
}
TRADITION_ALIASES = {
    "christianity": "christian", "church": "christian", "fathers": "christian", "patristic": "christian",
    "judaism": "jewish", "islam": "islamic", "muslim": "islamic", "quran": "islamic",
    "hinduism": "hindu", "dharmic": "hindu", "vedic": "hindu", "buddhism": "buddhist",
    "taoist": "chinese", "daoist": "chinese", "confucian": "chinese", "china": "chinese",
    "greek": "classical", "roman": "classical", "stoic": "classical", "gnosticism": "gnostic",
    "ane": "neareast", "babylonian": "neareast", "egyptian": "neareast", "mormon": "lds",
    "bahá'í": "bahai", "baha'i": "bahai", "pseudepigrapha": "apocrypha",
    "sikhism": "sikh", "jainism": "jain", "jaina": "jain", "japanese": "shinto", "japan": "shinto",
    "zoroastrianism": "zoroastrian", "parsi": "zoroastrian", "avestan": "zoroastrian",
    "maya": "mesoamerican", "mayan": "mesoamerican", "welsh": "celtic", "finland": "finnish",
    "arthur": "arthurian", "arthurian legend": "arthurian", "camelot": "arthurian", "grail": "arthurian",
    "ballad": "ballads", "folk": "ballads", "fairy tales": "ballads", "grimm": "ballads", "tales": "ballads", "child": "ballads", "child ballads": "ballads",
}


def tradition(name: str):
    """The TRADITIONS key for what a user typed ("Buddhism", "daoist"), or None."""
    key = name.strip().lower()
    key = TRADITION_ALIASES.get(key, key)
    return key if key in TRADITIONS else None


def _edit_distance(a: str, b: str) -> int:
    """Letters added, dropped, changed or swapped to turn a into b (Damerau-Levenshtein)."""
    if abs(len(a) - len(b)) > 3:
        return 99
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


_ROMAN_CHAPTER = re.compile(r"^([IVXLC]+)\.(\S+)$")


def _roman_int(numeral: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for a, b in zip(numeral, numeral[1:] + " "):
        total += -values[a] if values.get(b, 0) > values[a] else values[a]
    return total


def _arabic_chapter(key: str) -> str:
    m = _ROMAN_CHAPTER.match(key)
    return f"{_roman_int(m.group(1))}.{m.group(2)}" if m else key


# corpus -> its TRADITIONS key
CORPUS_TRADITION = {corpus: key for key, (_, corpora) in TRADITIONS.items() for corpus in corpora}

# Easter eggs: read by name for those who know (!verse vivec), but never listed, suggested,
# searched or drawn at random (the owner: "it's not meant to show up when looking")
HIDDEN_BOOKS = frozenset({"Vivec"})


def _tagged(result, key: str):
    """A passage fetched from an online library, marked as belonging to the tradition `key`."""
    if result is not None and result.get("found"):
        result["tradition"] = key
    return result


CORPUS_PRIORITY = ["kjv", "lds", "brenton", "charles", "nt_apocrypha", "apostolic_fathers", "quran", "classical", "jewish", "bahai", "qumran", "gnostic", "dharmic", "buddhist", "chinese", "sufi", "sikh", "jain", "shinto", "zoroastrian", "mesoamerican", "finnish", "celtic", "norse", "ancient_near_east", "patristics", "medieval", "reformation", "ballads", "arthurian"]


# Shepherd of Hermas: (first, last) Lightfoot continuous chapter of each
# Vision / Mandate / Similitude, for traditional "Herm Sim 9.1.3" citations.
_HERMAS_PARTS: dict[str, tuple[str, list[tuple[int, int]]]] = {
    "v": ("Vision", [(1, 4), (5, 8), (9, 21), (22, 24), (25, 25)]),
    "m": ("Mandate", [(26, 26), (27, 27), (28, 28), (29, 32), (33, 34), (35, 36),
                      (37, 37), (38, 38), (39, 39), (40, 42), (43, 43), (44, 49)]),
    "s": ("Similitude", [(50, 50), (51, 51), (52, 52), (53, 53), (54, 60),
                         (61, 65), (66, 66), (67, 77), (78, 110), (111, 114)]),
}
_HERMAS_REF = re.compile(
    r"^(?:(?:the\s+)?shepherd(?:\s+of\s+hermas)?|herm(?:as)?)\.?,?\s*"
    r"(?P<part>vis(?:ion)?s?|man(?:date)?s?|sim(?:ilitude)?s?)\.?\s*"
    r"(?P<n>\d+)"
    r"(?:[:.](?P<chap>\d+)"
    r"(?:[:.](?P<verse>\d+)(?:\s*[-–—]\s*(?P<verse_end>\d+))?)?)?$",
    re.IGNORECASE,
)


class ScriptureLookup:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        # corpus_name → { book_name → { chapter_str → { verse_str → text } } }
        self._data: dict[str, dict] = {}
        # book_name (lower) → (corpus_name, canonical_name)
        self._book_index: dict[str, tuple[str, str]] = {}
        # canonical book_name → source string for footer display
        self._book_sources: dict[str, str] = {}
        self._corpus_sources: dict[str, dict[str, str]] = {}
        self._book_file: dict[tuple, str] = {}           # (corpus, book) -> the data file it came from
        self._renamed: dict[str, list] = {}               # a shared title -> the "Title (Author)" names given
        # LRU cache for search_by_corpus (up to 64 queries)
        self._search_cache: dict = {}
        self._theme_cache: dict[str, list] = {}
        self._load_all()

    # ── Loading ────────────────────────────────────────────────────────────────

    def _load_all(self):
        corpus_dirs = {
            "kjv":     ["kjv_canon.json", "kjv_apocrypha.json"],
            "lds":     ["book_of_mormon.json", "doctrine_and_covenants.json", "pearl_of_great_price.json"],
            "brenton": ["brenton_extras.json"],
            "charles": ["book_of_enoch.json", "book_of_jubilees.json", "testaments_of_twelve_patriarchs.json", "assumption_of_moses.json", "ascension_of_isaiah.json", "sibylline_oracles.json", "letter_of_aristeas.json", "books_of_adam_and_eve.json", "zadokite_fragments.json", "secrets_of_enoch.json", "forgotten_books_of_eden.json"],
            "nt_apocrypha": ["anf8_apocrypha.json", "anf9_apocrypha.json"],
            "apostolic_fathers": [
                "1_clement.json",
                "2_clement.json",
                "ignatius_ephesians.json",
                "ignatius_magnesians.json",
                "ignatius_trallians.json",
                "ignatius_romans.json",
                "ignatius_philadelphians.json",
                "ignatius_smyrnaeans.json",
                "ignatius_polycarp.json",
                "polycarp_philippians.json",
                "martyrdom_of_polycarp.json",
                "epistle_of_barnabas.json",
                "didache.json",
                "shepherd_of_hermas.json",
                "divine_names.json",
                "mystical_theology.json",
                "on_the_heavenly_hierarchy.json",
                "on_the_ecclesiastical_hierarchy.json",
                "letters_of_dionysius.json",
                "liturgy_of_st_dionysius.json",
            ],
            "quran": ["quran_pickthall.json"],
            "classical": [
                "golden_verses.json",
                "orphic_hymns.json",
                "homeric_hymns.json",
                "corpus_hermeticum.json",
                "definitions_of_hermes.json",
                "emerald_tablet.json",
                "asclepius.json",
                "chaldaean_oracles.json",
                "hesiod_theogony.json",
                "vivec_sermons.json",
                "proclus.json",
                "elements_of_theology.json",
                "delphi.json",
                "aeneid.json",
                "plato.json",
                "homer.json",
                "plotinus.json",
                "porphyry.json",
                "iamblichus.json",
                "aristotle_perseus.json",
                "aristotle_mit.json",
                "aristotle_more.json",
                "plato_spuria.json",
                "hesiod_evelyn_white.json",
                "meditations_long.json",
                "enchiridion_higginson.json",
                "julian.json",
                "sallustius.json",
                "isis_and_osiris.json",          # Plutarch (Babbitt): not in the Perseus Plutarch
                "aesop.json",                    # Townsend (scripts/build_aesop.py)
                "phaedrus.json",                 # Riley (scripts/build_fables.py)
                "tetrabiblos.json",              # Ptolemy, and his Centiloquy (scripts/build_astrology.py)
                "proclus_theology.json",
                "hierocles.json",
                "marinus.json",
                "pythagorean_sentences.json",
                "divine_names.json",
                "mystical_theology.json",
                "on_the_heavenly_hierarchy.json",
                "on_the_ecclesiastical_hierarchy.json",
            ],
            "jewish": [
                "josephus.json",
                "philo.json",
            ],
            "bahai": [
                "kitab_i_aqdas.json",
                "hidden_words_arabic.json",
                "hidden_words_persian.json",
                "gleanings.json",
                "prayers_and_meditations.json",
                "some_answered_questions.json",
                "kitab_i_iqan.json",
                "epistle_to_son_of_wolf.json",
            ],
            "qumran": [
                "1qha.json",
                "cd.json",
                "1qs.json",
                "1qm.json",
                "1qphab.json",
                "1qsa.json",
                "1qsb.json",
                "1qisaa.json",
                "4q22.json",
                "4q41.json",
                "4q86.json",
                "4q114.json",
            ],
            "gnostic": [
                "ginza_rba.json",
                "mandaean_book_of_john.json",
                "nag_hammadi_zinner.json",
                "gospel_of_thomas.json",
                "manichaean_psalms.json",
            ],
            "buddhist": [
                "dhammapada.json",
                "diamond_sutra.json",
                "sutta_nipata.json",
                "lotus_sutra.json",
                "milinda.json",
                "jataka.json",
            ],
            "chinese": [
                "tao_te_ching.json",
                "analects.json",
                "i_ching.json",
                "zhuangzi.json",
                "mencius.json",
                "great_learning_mean.json",
            ],
            "sufi": [
                "hafiz_bell.json",
                "masnavi_whinfield.json",
                "rubaiyat_fitzgerald.json",
            ],
            "sikh": ["guru_granth_sahib.json"],
            "jain": ["jaina_sutras.json"],
            "shinto": ["kojiki.json", "nihongi.json"],
            "zoroastrian": ["gathas.json", "avesta.json"],
            "mesoamerican": ["popol_vuh.json"],
            "finnish": ["kalevala.json"],
            "celtic": ["mabinogion.json"],
            "arthurian": [                       # the Arthurian legend (scripts/build_arthurian.py)
                "malory.json",
                "chretien.json",
                "parzival.json",
                "high_history.json",
                "queste.json",
                "tristan_bedier.json",
                "gawain.json",
                "marie_de_france.json",
                "geoffrey.json",
                "wace.json",
                "layamon.json",
                "nennius.json",
                "morien.json",
                "libeaus.json",
                "launfal.json",
                "tarn_wadeling.json",
                "tyolet.json",
            ],
            "ballads": ["child.json",             # Child's ballads (scripts/build_child.py)
                        "grimm.json",             # the Grimms' tales, Hunt (scripts/build_grimm.py)
                        "la_fontaine.json",       # Thornbury (scripts/build_fables.py)
                        "talking_beasts.json",    # the world's fables, Wiggin and Smith (build_fables.py)
                        "reynard.json"],          # Caxton, ed. Morley (scripts/build_beasts.py)
            "norse": [
                "poetic_edda.json",
            ],
            "ancient_near_east": [
                "baal_cycle_en.json",
                "enuma_elish.json",
                "muallaqat_en.json",
                "gilgamesh.json",
                "great_hymn_to_aten.json",
                "book_of_the_dead.json",
                "leiden_hymns.json",
                "instruction_of_amenemope.json",
                "book_of_two_ways.json",
                "story_of_ahikar.json",
            ],
            "dharmic": [
                "rig_veda.json",
                "yajur_veda.json",
                "sama_veda.json",
                "atharva_veda.json",
                "bhagavad_gita.json",
                "upanishads_paramananda.json",
                "upanishads_muller.json",
                "laws_of_manu.json",
                "yoga_sutras.json",
            ],
            "patristics": [
                # ── Original 15 (ANF/NPNF epub) ───────────────────────────
                "clement_of_alexandria.json",
                "tertullian.json",
                "origen.json",
                "athanasius.json",
                "basil_the_great.json",
                "gregory_of_nyssa.json",
                "gregory_nazianzen.json",
                "chrysostom.json",
                "augustine.json",
                "jerome.json",
                "cyril_of_alexandria.json",
                "leo_the_great.json",
                "john_of_damascus.json",
                "ephrem_the_syrian.json",
                "gregory_the_great.json",
                # ── Ante-Nicene (ANF epub) ────────────────────────────────
                "alexander_of_alexandria.json",
                "alexander_of_lycopolis.json",
                "aphrahat.json",
                "archelaus.json",
                "aristides_the_philosopher.json",
                "arnobius.json",
                "athenagoras.json",
                "bardesanes.json",
                "barnabas.json",
                "caius.json",
                "clement_of_rome.json",
                "commodianus.json",
                "cyprian_of_carthage.json",
                "dionysius_of_rome.json",
                "dionysius_the_great.json",
                "gregory_thaumaturgus.json",
                "hippolytus.json",
                "ignatius_of_antioch.json",
                "irenaeus_of_lyons.json",
                "julius_africanus.json",
                "justin_martyr.json",
                "lactantius.json",
                "malchion.json",
                "mar_jacob.json",
                "mathetes.json",
                "methodius.json",
                "minucius_felix.json",
                "moses_of_chorene.json",
                "novatian.json",
                "pamphilus.json",
                "papias.json",
                "peter_of_alexandria.json",
                "polycarp.json",
                "rufinus.json",
                "tatian.json",
                "theodotus.json",
                "theophilus.json",
                "venantius.json",
                "victorinus.json",
                # ── Nicene & Post-Nicene (ANF/NPNF epub) ─────────────────
                "cyril_of_jerusalem.json",
                "gennadius_of_marseilles.json",
                "hilary_of_poitiers.json",
                "john_cassian.json",
                "socrates_scholasticus.json",
                "sozomen.json",
                "sulpitius_severus.json",
                "vincent_of_lrins.json",
                # ── Pearse / tertullian.org ───────────────────────────────
                "agapius_of_hierapolis.json",
                "ambrose.json",
                "asterius_of_amasea.json",
                "cosmas_indicopleustes.json",
                "dioscorus_of_alexandria.json",
                "epiphanius.json",
                "eunomius.json",
                "eusebius_of_caesarea.json",
                "evagrius_scholasticus.json",
                "gildas.json",
                "hermias.json",
                "isidore_of_seville.json",
                "john_bar_penkaye.json",
                "john_of_ephesus.json",
                "leontius_of_byzantium.json",
                "macarius_magnes.json",
                "nestorius.json",
                "optatus_of_milevis.json",
                "pacian_of_barcelona.json",
                "palladius.json",
                "philostorgius.json",
                "philoxenus_of_hierapolis.json",
                "photius.json",
                "possidius.json",
                "pseudo_hegesippus.json",
                "salvian.json",
                "severus_of_antioch.json",
                "sidonius_apollinaris.json",
                "theodore_of_mopsuestia.json",
                "theodoret.json",
                "timothy_i.json",
                # ── Added from Schaff (scripts/build_fathers.py) ──────────
                "church_councils.json",
                "apostolic_constitutions.json",
                "early_liturgies.json",
                "ancient_syriac_documents.json",
                "remains_of_the_second_and_third_centuries.json",
                "anatolius_and_minor_writers.json",
                # ── The Philokalia (scripts/build_philokalia.py) ──────────
                "philokalia.json",
                # ── Budge's Paradise of the Holy Fathers, from Wikisource (scripts/build_paradise.py)
                "paradise_of_the_fathers.json",
            ],
            "medieval": [
                "bede.json",
                "physiologus.json",              # Mladenova & Stoykov (scripts/build_beasts.py)
                "golden_legend.json",
                "imitation_of_christ.json",
                "rule_of_benedict.json",
                "divine_comedy_longfellow.json",
                "cloud_of_unknowing.json",
                "julian_revelations.json",
                "practice_of_presence.json",
                "swedenborg.json",
                "lilly_astrology.json",          # Lilly ed. Zadkiel (scripts/build_astrology.py)
                "sepharial_astrology.json",      # Sepharial, 1920 (scripts/build_sepharial.py)
                "blake.json",
                "milton.json",
                "pilgrims_progress.json",
            ],
            # the Reformation and its heirs (scripts/build_reformation.py)
            "reformation": [
                "book_of_concord.json",
                "luther.json",
                "calvin.json",
                "confessions.json",
                "knox.json",
                "latimer.json",
                "anglican_divines.json",
                "wesley.json",
            ],
        }
        for corpus, filenames in corpus_dirs.items():
            self._data.setdefault(corpus, {})
            for fname in filenames:
                path = self.data_dir / corpus / fname
                if not path.exists():
                    print(f"[WARN] Missing data file: {path}")
                    continue
                with open(path, encoding="utf-8") as f:
                    payload = json.load(f)
                books = self._as_one_work(fname, payload.get("books", {}))
                self._make_room(corpus, books)
                self._data[corpus].update(books)
                # Store per-book source string for footer display
                file_source = payload.get("source", "")
                sources = {b: file_source for b in books} if file_source else {}
                # ...overridden per book where a file mixes translators (plato.json)
                sources.update(payload.get("book_sources", {}))
                self._book_sources.update(sources)
                # Book names repeat across corpora (Plato's "Apology" and
                # Rufinus' in patristics): keep each corpus's own credits too
                self._corpus_sources.setdefault(corpus, {}).update(sources)
                self._book_file.update({(corpus, b): fname for b in books})
        # The Perseus library (scripts/build_perseus.py): a file per author, all classical
        perseus = self.data_dir / "classical" / "perseus"
        if (perseus / "aliases.json").exists():         # catalogue titles: "Germania", "Annales"...
            for alias, book in json.loads((perseus / "aliases.json").read_text(encoding="utf-8")).items():
                ALIASES.setdefault(alias, book)
        for path in sorted(perseus.glob("*.json")):
            if path.name in ("index.json", "aliases.json", "originals.json"):
                continue
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            books = payload.get("books", {})
            self._make_room("classical", books)
            self._data["classical"].update(books)
            self._book_file.update({("classical", b): path.name for b in books})
            sources = {b: payload.get("source", "") for b in books}
            sources.update(payload.get("book_sources", {}))
            self._book_sources.update(sources)
            self._corpus_sources.setdefault("classical", {}).update(sources)
        self._aliases_to_renamed()
        for corpus in ("classical", "medieval", "ancient_near_east"):
            self._regroup_line_chunks(corpus, self._LINE_CHUNKED)
        # Chapters numbered "I.1" (book I, chapter 1: Aristotle's Physics, Topics...) as "1.1",
        # the way every other work's are -- the reference parser can't read a Roman numeral there
        for books in self._data.values():
            for book, chapters in books.items():
                if isinstance(chapters, dict) and chapters and all(_ROMAN_CHAPTER.match(k) for k in chapters):
                    renamed = {_arabic_chapter(k): v for k, v in chapters.items()}
                    if len(renamed) == len(chapters):
                        books[book] = renamed

        # Normalize chapter shape: some source files store a chapter as a bare
        # string (a single untitled passage) instead of {verse_num: text}.
        # Treat that string as verse "1" so lookups and random selection
        # don't crash on it (affects some ancient_near_east texts).
        for corpus, books in self._data.items():
            for book, chapters in books.items():
                if not isinstance(chapters, dict):
                    continue
                for chap_key, chap_val in list(chapters.items()):
                    if isinstance(chap_val, str):
                        chapters[chap_key] = {"1": chap_val}

        # Build book index respecting priority
        for corpus in CORPUS_PRIORITY:
            for book_name in self._data.get(corpus, {}):
                key = book_name.lower()
                if key not in self._book_index:
                    self._book_index[key] = (corpus, book_name)

    # Two Fathers often wrote works of the same title (Letters, Fragments, On the Holy Spirit, an
    # Ecclesiastical History), and a later file's book silently replaced an earlier one's of that name:
    # some 25 works were unreachable. The work that answered to the title before keeps it, so no
    # citation changes; the others are named with their author: "Ecclesiastical History (Socrates
    # Scholasticus)". An alias that names the author ("ecclesiastical history socrates") follows them.

    @staticmethod
    def _author_of(fname: str) -> str:
        words = fname.rsplit(".", 1)[0].replace("_", " ").split()
        small = {"of", "the", "and", "de"}
        return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))

    def _make_room(self, corpus: str, books: dict) -> None:
        """Before `books` are added: rename any book of the same title already there to "Title (Author)"."""
        stored = self._data.setdefault(corpus, {})
        for title in [b for b in books if b in stored]:
            earlier = self._book_file.get((corpus, title))
            if not earlier:
                continue
            name = f"{title} ({self._author_of(earlier)})"
            if name in stored or name in books:
                continue
            stored[name] = stored.pop(title)
            self._book_file[(corpus, name)] = earlier
            if title in self._book_sources:
                self._book_sources[name] = self._book_sources[title]
            if title in self._corpus_sources.get(corpus, {}):
                self._corpus_sources[corpus][name] = self._corpus_sources[corpus][title]
            self._renamed.setdefault(title, []).append(name)

    def _aliases_to_renamed(self) -> None:
        """"ecclesiastical history socrates" -> "Ecclesiastical History (Socrates Scholasticus)"."""
        for title, names in self._renamed.items():
            for name in names:
                author = name[len(title) + 2:-1].lower()
                words = [w for w in author.split() if len(w) > 3 and w not in ("great", "saint")]
                for alias, target in list(ALIASES.items()):
                    if target == title and any(w in alias for w in words):
                        ALIASES[alias] = name

    # Files that store a work a part per "book" -- Bede's five books as "Book I"..."Book V", the
    # Golden Legend a "book" per saint -- which left the works themselves impossible to cite, and
    # "Book I", "Lucy" or "Andrew" answering as books of their own
    _WHOLE_WORKS = {"bede.json": "Ecclesiastical History of the English People",
                    "golden_legend.json": "The Golden Legend"}

    def _as_one_work(self, fname: str, books: dict) -> dict:
        """Bede as one work cited book.chapter ("Bede 3.5:1"); the Golden Legend as one with a
        chapter per life, in its order, the life's title leading it ("Golden Legend 54")."""
        name = self._WHOLE_WORKS.get(fname)
        if name is None:
            return books
        work = {}
        for i, (part, chapters) in enumerate(books.items(), 1):
            m = re.fullmatch(r"Book ([IVX]+)", part)
            if m:
                for chap, verses in chapters.items():
                    work[f"{_roman_int(m.group(1))}.{chap}"] = verses
                continue
            verses = {}
            for chap_verses in chapters.values():
                for text in (chap_verses.values() if isinstance(chap_verses, dict) else [chap_verses]):
                    verses[str(len(verses) + 1)] = text
            if verses and not verses["1"].lstrip("*").lower().startswith(part.lower()[:20]):
                verses["1"] = f"*{part}*\n{verses['1']}"
            work[str(i)] = verses
        return {name: work}

    # ── Public API ─────────────────────────────────────────────────────────────

    def random_verse(self, rng=None, traditions=None) -> dict:
        """A random passage from anywhere (or from the TRADITIONS keys in `traditions`): a
        tradition first, each as likely as the next, then a book in it, then a passage in
        the book -- so the biggest texts (the Guru Granth Sahib's 60,000 lines, Plutarch)
        don't crowd out the rest, as picking among all passages at once did."""
        import random as _random
        rng = rng or _random
        # (Mishnah, Talmud, Zohar and hadith are live lookups, not in _data)
        SKIP_BOOKS = HIDDEN_BOOKS
        allowed, traditions = traditions, []
        for key, (_, corpora) in TRADITIONS.items():
            if allowed is not None and key not in allowed:
                continue
            books = [(c, b, key) for c in corpora for b, chapters in self._data.get(c, {}).items()
                     if b not in SKIP_BOOKS and any(chapters.values())
                     and not (key == "bible" and allowed is not None and "apocrypha" not in allowed
                              and b in BIBLE_APOCRYPHA)]
            if books:
                traditions.append(books)
        if not traditions:
            return {"found": False, "error": "No verse data loaded.", "suggestions": []}
        corpus, book, tradition_key = rng.choice(rng.choice(traditions))
        chapters = self._data[corpus][book]
        chap = rng.choice([c for c, v in chapters.items() if v])
        verse = rng.choice(list(chapters[chap]))
        text = self._data[corpus][book][chap][verse]
        source = self._book_sources.get(book, book)
        ref = f"{book} {chap}:{verse}"
        return {
            "found": True,
            "reference": ref,
            "text": text,
            "source": source,
            "book": book,
            "chapter": chap,
            "verse": verse,
            "tradition": tradition_key,
        }

    def random_verse_from_book(self, book_raw: str) -> dict:
        """Pick a random verse from a specific book."""
        import random as _random
        corpus, canon_book = self._resolve_book(book_raw)
        if canon_book and self._resolve_exact(book_raw)[1] is None and self._guessed(book_raw, canon_book):
            return self._did_you_mean(book_raw, book_raw.strip(), canon_book)
        if canon_book is None:
            return {
                "found": False,
                "error": f"Unknown book: **{book_raw}**",
                "suggestions": self._suggest_books(book_raw),
            }
        chapters = self._data[corpus].get(canon_book, {})
        if not chapters:
            return {"found": False, "error": f"No data found for **{canon_book}**.", "suggestions": []}

        # (some books have empty chapters -- gaps in the Enneads, Enoch -- which
        # random.choice would crash on)
        chap = _random.choice([c for c, v in chapters.items() if v] or list(chapters))
        verses = chapters[chap]
        if not verses:
            return {"found": False, "error": f"No data found for **{canon_book}**.", "suggestions": []}
        verse = _random.choice(list(verses.keys()))
        text = verses[verse]
        source = self._book_sources.get(canon_book, canon_book)
        return {
            "found": True,
            "reference": f"{canon_book} {chap}:{verse}",
            "text": text,
            "source": source,
            "book": canon_book,
            "chapter": chap,
            "verse": verse,
        }

    def random_verse_from_books(self, book_list: list[str]) -> dict:
        """Pick a random verse from a list of book names."""
        import random as _random
        candidates = []
        for book_name in book_list:
            for corpus in self._data.values():
                if book_name in corpus:
                    for chap, verses in corpus[book_name].items():
                        for verse in verses.keys():
                            candidates.append((book_name, corpus, chap, verse))
                    break
        if not candidates:
            return {"found": False, "error": "No verse data found for those books.", "suggestions": []}
        book_name, corpus, chap, verse = _random.choice(candidates)
        text = corpus[book_name][chap][verse]
        source = self._book_sources.get(book_name, book_name)
        return {
            "found": True,
            "reference": f"{book_name} {chap}:{verse}",
            "text": text,
            "source": source,
            "book": book_name,
            "chapter": chap,
            "verse": verse,
        }


    def corpora_names(self) -> list[str]:
        return [c for c in CORPUS_PRIORITY if self._data.get(c)]

    def chapter_count(self, book_name: str) -> int | None:
        """Return number of chapters for a locally-loaded book, or None."""
        for corpus in self._data.values():
            if book_name in corpus:
                return len(corpus[book_name])
        return None

    def chapter_keys(self, book_name: str) -> list[str] | None:
        """Return this book's real chapter keys, sorted, or None if not local."""
        for corpus in self._data.values():
            if book_name in corpus:
                def _sort_key(k):
                    try:
                        return [int(x) for x in re.split(r"[.\s]+", k) if x]
                    except ValueError:
                        return [0]
                return sorted(corpus[book_name].keys(), key=_sort_key)
        return None

    def chapter_verse_summary(self, book_name: str) -> list[int]:
        """Return [verse_count_ch1, verse_count_ch2, ...] in chapter order, or [] if not local."""
        keys = self.chapter_keys(book_name)
        if keys is None:
            return []
        for corpus in self._data.values():
            if book_name in corpus:
                return [len(corpus[book_name][k]) for k in keys]
        return []

    def section_books(self, book_list: list[str]) -> list[tuple[str, int | None]]:
        """Return [(book_name, chapter_count_or_None)] for a list of books,
        filtered to only those actually loaded (or always-available via API)."""
        loaded = {name for books in self._data.values() for name in books}
        mishnah_available = {
            v.replace("Mishnah_", "").replace("_", " ")
            for v in MISHNAH_TRACTATES.values()
        }
        talmud_available = set(TALMUD_TRACTATES.values())
        hadith_available  = set(COLLECTION_DISPLAY.values())
        always_available  = {"Zohar"} | mishnah_available | talmud_available | hadith_available

        result = []
        for b in book_list:
            if b in loaded or b in always_available:
                result.append((b, self.chapter_count(b)))
        return result

    # Works stored as one passage per few lines, keyed "book.firstline"
    # ("1.1", "1.5", ...: Murray's Homer, cut at his every-5th-line markers so
    # each passage matches the same Greek lines). Regrouped on load into
    # book -> {first line: text}, so "Iliad 1" is a book and "Iliad 1:7" the
    # passage containing line 7.
    _LINE_CHUNKED = ("Iliad", "Odyssey", "Inferno", "Purgatorio", "Paradiso",
                     "Works and Days", "Shield of Heracles", "Enuma Elish")

    def _regroup_line_chunks(self, corpus: str, books) -> None:
        for book in books:
            data = self._data.get(corpus, {}).get(book)
            if not data or not all(re.fullmatch(r"\d+\.\d+", k) for k in data):
                continue
            regrouped: dict[str, dict] = {}
            for key, val in data.items():
                b, line = key.split(".")
                text = val.get("1", "") if isinstance(val, dict) else val
                regrouped.setdefault(b, {})[line] = text
            for b in regrouped:
                regrouped[b] = dict(sorted(regrouped[b].items(), key=lambda kv: int(kv[0])))
            self._data[corpus][book] = regrouped

    @staticmethod
    def _line_span(chap_data: dict, start: int, end: int) -> tuple[int, int, list]:
        """For a line-chunked book: the passages covering lines start..end,
        as (first line, last line, [passage starts])."""
        starts = sorted(int(k) for k in chap_data)
        first = max((s for s in starts if s <= start), default=starts[0])
        chosen = [s for s in starts if first <= s <= end]
        nxt = [s for s in starts if s > chosen[-1]]
        # (the book's last passage: its length isn't recorded, so claim no more than was asked)
        last = nxt[0] - 1 if nxt else max(chosen[-1], min(chosen[-1] + 4, end))
        return first, last, chosen

    # Works whose verses are numbered straight through the book and cited by
    # that number alone ("Dhammapada 183"), though stored by chapter.
    _VERSE_NUMBERED = ("Dhammapada", "Sutta Nipata")

    def _locate_numbered_verse(self, book: str, chap_key: str, verse_start, verse_end):
        """A bare number beyond the last chapter is a verse number; a verse
        given with the wrong chapter is found in the right one."""
        chapters = self._data.get("buddhist", {}).get(book, {})
        if verse_start is None and chap_key.isdigit() and chap_key not in chapters:
            verse_start = verse_end = int(chap_key)
        if verse_start is None:
            return chap_key, verse_start, verse_end
        end = verse_end or verse_start
        if chap_key in chapters and str(verse_start) in chapters[chap_key]:
            return chap_key, verse_start, end
        for key, verses in chapters.items():
            if str(verse_start) in verses:
                return key, verse_start, end
            # verses translated as one are stored under the first, labelled
            # "(vv. 58–59)" / "(vv. 1006–1008)"
            for v, text in verses.items():
                m = re.match(r"(?:\*[^\n]*\*\n)?\(vv\. (\d+)–(\d+)\)", text)
                if m and int(m.group(1)) <= verse_start <= int(m.group(2)):
                    return key, int(v), max(end, int(m.group(2)))
        return chap_key, verse_start, verse_end

    def _guessed(self, typed: str, book: str) -> bool:
        """Whether reading `typed` as `book` is a guess too far to make silently: more than a slip of
        a letter or two from the book's name and every one of its aliases ("Against Heresies" was
        answered with Cicero's Against Verres; "Jhon" and "Genisis" are plainly John and Genesis)."""
        typed = typed.lower().strip()
        if re.match(r"\d\s", book) and not re.match(r"\d", typed):
            return True                                   # "Corinthians": the first or the second?
        names = [book.lower()] + [a for a, target in ALIASES.items() if target == book]
        allowed = 1 if len(typed) < 8 else 2
        return min(_edit_distance(typed, n) for n in names) > allowed

    def _did_you_mean(self, reference: str, typed: str, guess: str) -> dict:
        """The reply to a book I don't have, with the closest few to choose from."""
        rest = reference.strip()[len(typed):]
        names = [guess] + [s for s in self._suggest_books(typed) if s != guess]
        refs = [f"{name}{rest}" for name in names[:3]]
        return {"found": False, "error": f"I don't have a book called **{typed}**.",
                "suggestions": refs, "did_you_mean": refs}

    def get_verse(self, reference: str, _quran_api: bool = True) -> dict:
        """A passage by reference, tagged with the TRADITIONS key it belongs to ("tradition",
        None when unsure), so a server that has turned that tradition off can leave it out."""
        result = self._get_verse(reference, _quran_api)
        typed = re.match(r"^(.+?)\s+[\d¶]", reference.strip())
        if result.get("found") and typed:
            typed = typed.group(1)
            book = result.get("book")                         # (some paths give only the reference)
            if not book:
                named = re.match(r"^(.+?)\s+[\d¶]", result.get("reference", ""))
                book = named.group(1) if named else None
            if (book and self._resolve_exact(typed)[1] is None and self._resolve_fuzzy(typed)[1] == book
                    and self._guessed(typed, book)):
                return self._did_you_mean(reference, typed, book)
        if result.get("found") and "tradition" not in result:
            result["tradition"] = self.tradition_of(result)
        return result

    def tradition_of(self, result: dict):
        """The TRADITIONS key of a passage: its own "tradition" when it has one (a title can be in two
        corpora), else from its book; None when unsure."""
        if result.get("tradition"):
            return result["tradition"]
        book = result.get("book")
        if not book:
            m = re.match(r"^(.+?)\s+[\d¶]", result.get("reference", ""))
            book = m.group(1) if m else None
        corpus = self._resolve_book(book)[0] if book else None
        return CORPUS_TRADITION.get(corpus)

    # ── How a reference is read ────────────────────────────────────────────────
    # A reference goes to the first reader below that recognises it; the order matters (Plato's
    # "Republic 514a" before the Talmud's "Berakhot 2a", which both end in a number and a letter).
    # Each takes the reference and returns a result, or None to pass it on. Then the general
    # "Book chapter:verse" parser; then, for a book that isn't stored here, the online libraries.
    # tests/test_reference_readers.py pins the order and each reader.

    def _readers_before_parsing(self, online: bool = True) -> list:
        """[(name, read(ref), the tradition its results belong to, or None to work it out)]."""
        readers = [
            ("the Quran, from the Quran API", self._read_quran, "islamic"),
            ("the Pali Canon, from SuttaCentral", self._read_sutta, "buddhist"),
            ("the Gita's other translations, from the Gita API", self._read_gita, "hindu"),
            ("Sikh scripture, from BaniDB", self._read_bani, "sikh"),
        ] if online else []
        return readers + [
            ("the Epistle of Jeremiah (Baruch 6)", lambda ref: self._read_epistle_of_jeremiah(ref, online), None),
            ("the ancient Near East (Baal N:M, Muallaqat N:M)", self._try_ancient_near_east, None),
            ("Plato by Stephanus page", self._try_stephanus, None),
            ("the Babylonian Talmud by page", self._read_talmud, "jewish"),
            ("the Zohar", self._read_zohar, "jewish"),
            ("Delphi 1:N and 2:N", self._read_delphi, None),
            ("Child's ballads by number and version (Child 12A:5)", self._read_child, "ballads"),
            ("the Shepherd of Hermas by Vision, Mandate or Similitude", self._try_hermas, None),
            ("anything Sefaria has that the parser can't read", self._read_unparseable, "jewish"),
        ]

    def _readers_for_unknown_books(self) -> list:
        """[(name, read(ref, book, chapter, verse, end), tradition)] for a book that isn't stored here."""
        return [
            ("the Mishnah", lambda ref, b, c, v, e: self._try_sefaria(b, c, v, e), "jewish"),
            ("the Jerusalem Talmud", lambda ref, b, c, v, e: self._try_yerushalmi(b, c, v), "jewish"),
            ("the Tosefta", lambda ref, b, c, v, e: self._try_tosefta(b, c, v), "jewish"),
            ("the Targumim", lambda ref, b, c, v, e: self._try_targum(ref), "jewish"),
            ("the Midrash", lambda ref, b, c, v, e: self._try_midrash(b, c, v), "jewish"),
            ("Kabbalah", lambda ref, b, c, v, e: self._try_kabbalah(b, c, v), "jewish"),
            ("the Mishneh Torah", lambda ref, b, c, v, e: self._try_mishneh_torah(ref), "jewish"),
            ("the Guide for the Perplexed", lambda ref, b, c, v, e: self._try_guide(ref), "jewish"),
            ("the hadith", lambda ref, b, c, v, e: self._try_hadith(ref), "islamic"),
            ("the rest of Sefaria's library (Rashi on Genesis, the Kuzari...)",
             lambda ref, b, c, v, e: __import__("sefaria_lookup").fetch_sefaria_any(ref), "jewish"),
        ]

    def _homer_lines(self, ref: str) -> str:
        """Homer is cited book.line ("Iliad 6.440-465"); the general parser only takes a dot without a
        range, so the dot is read as a colon."""
        m = re.match(r"^(.+?)\s+(\d+)\.(\d+\s*[-–]\s*\d+)$", ref)
        if m and self._resolve_book(m.group(1))[1] in self._LINE_CHUNKED:
            return f"{m.group(1)} {m.group(2)}:{m.group(3)}"
        return ref

    def _read_quran(self, ref):
        """Abdel Haleem (or any translation named after it) from the Quran API, with our own Pickthall
        for "pickthall" and whenever the API can't be reached."""
        import quran_lookup
        return quran_lookup.get_quran(ref, lambda r: self.get_verse(r, _quran_api=False))

    def _read_sutta(self, ref):
        """MN 1, SN 56.11, AN 3.65..."""
        import sutta_lookup
        return sutta_lookup.get_sutta(ref)

    def _read_gita(self, ref):
        """The Gita in a named translation or commentary (plain "Gita 2:47" stays our Purohit)."""
        import gita_lookup
        return gita_lookup.get_gita(ref, lambda r: self.get_verse(r, _quran_api=False))

    def _read_bani(self, ref):
        """The Dasam Granth, Bhai Gurdas, more Guru Granth Sahib translations."""
        import banidb_lookup
        return banidb_lookup.get_bani(ref, lambda r: self.get_verse(r, _quran_api=False))

    def _read_epistle_of_jeremiah(self, ref, online=True):
        """Chapter 6 of Baruch in the KJV's Apocrypha. It has one chapter: "Epistle of Jeremiah 1" is
        all of it, "1:5" or "5" its fifth verse."""
        m = re.match(r"^(?:the\s+)?(?:epistle|letter|ep\.?|let\.?)\s*(?:of\s+)?jer(?:emiah|\.)?"
                     r"(?:\s+(1:)?(\d+(?:\s*[-–]\s*\d+)?))?\s*$", ref, re.IGNORECASE)
        if not m:
            return None
        whole = m.group(2) is None or (m.group(1) is None and m.group(2) == "1")
        return self._get_verse("Baruch 6" if whole else f"Baruch 6:{m.group(2)}", online)

    def _read_talmud(self, ref):
        """"Talmud Berakhot 2a:3", "Gemara Shabbat 31a", "Berakhot 2a:3": a page (daf) and side."""
        return get_talmud(ref) if re.search(r"\d+[ab]", ref, re.IGNORECASE) else None

    def _read_zohar(self, ref):
        """"Zohar Bereshit 5", "Zohar 1:1a:3", or "Zohar" alone for one at random."""
        if not re.match(r"^(?:the\s+)?zohar\b", ref, re.IGNORECASE):
            return None
        return self._try_zohar_raw(ref) or {
            "found": False,
            "error": "Could not fetch that Zohar reference.\nFormat: `Zohar Bereshit 5` or just `Zohar` for random.",
            "suggestions": []}

    def _read_delphi(self, ref):
        """Delphi 1:N (the maxims) and Delphi 2:N (the oracular statements)."""
        delphi_m = re.match(r"^delphi\s+([12]):(\d+)$", ref, re.IGNORECASE)
        if not delphi_m:
            return None
        sub, num = delphi_m.group(1), delphi_m.group(2)
        book = "Delphic Maxims" if sub == "1" else "Oracular Statements"
        entries = self._data.get("classical", {}).get(book, {})
        if entries.get(num) is None:
            max_n = max((int(k) for k in entries), default=0)
            return {"found": False, "error": f"**{book}** has no entry {num}. (Max: {max_n})", "suggestions": []}
        return {"found": True, "reference": f"Delphi {sub}:{num}", "text": entries[num].get("1", ""),
                "source": book, "book": book, "chapter": int(num), "verse": 1}

    def _read_child(self, ref):
        """"Child 12" (version A of Lord Randal), "Child Ballads 12B", "Child 84A:3-5": a ballad by its number,
        version letter and stanzas. Its versions are chapters "12A", "12B"..., which the general parser can't
        read (a chapter there is a number)."""
        m = re.match(r"^(?:child(?:'s)?(?:\s+ballads?)?|ballad)\s*#?\s*(\d{1,3})\s*([A-Za-z]{0,2})"
                     r"(?:\s*:\s*(\d+)(?:\s*[-–]\s*(\d+))?)?\s*$", ref, re.IGNORECASE)
        book = self._data.get("ballads", {}).get("Child Ballads")
        if not m or not book:
            return None
        n, letters = int(m.group(1)), m.group(2).upper()
        versions = sorted((k for k in book if re.fullmatch(rf"{n}[A-Z]*", k)), key=lambda k: (len(k), k))
        if not versions:
            return {"found": False, "error": f"Child's ballads are numbered 1 to 305; there's no {n}.",
                    "suggestions": []}
        chapter = f"{n}{letters}" if letters else versions[0]
        if chapter not in book:
            return {"found": False, "error": f"Child {n} has versions {', '.join(v[len(str(n)):] or '(one)' for v in versions)}"
                                             f"; there's no {letters}.", "suggestions": []}
        stanzas = book[chapter]
        source = self._book_sources.get("Child Ballads", "")
        if m.group(3) is None:
            texts = [f"**[{k}]** {t}" for k, t in stanzas.items()]
            return {"found": True, "reference": f"Child {chapter}", "text": "\n".join(texts), "source": source,
                    "book": "Child Ballads", "chapter": chapter,
                    "pages": ["\n".join(texts[i:i + 15]) for i in range(0, len(texts), 15)]}
        first, last = int(m.group(3)), int(m.group(4) or m.group(3))
        texts = [f"**[{k}]** {stanzas[str(k)]}" for k in range(first, last + 1) if str(k) in stanzas]
        if not texts:
            return {"found": False, "error": f"Child {chapter} has stanzas {min(map(int, stanzas))} to "
                                             f"{max(map(int, stanzas))}.", "suggestions": []}
        span = f"{first}" if first == last else f"{first}–{last}"
        return {"found": True, "reference": f"Child {chapter}:{span}", "text": "\n".join(texts), "source": source,
                "book": "Child Ballads", "chapter": chapter, "verse": first}

    def _read_unparseable(self, ref):
        """A reference the general parser can't read may still be in Sefaria's library
        ("Jerusalem Talmud Makkot 2:7:2-3:7:1")."""
        if self._parse_reference(ref) is not None:
            return None
        import sefaria_lookup
        return sefaria_lookup.fetch_sefaria_any(ref)

    def _get_verse(self, reference: str, _quran_api: bool = True) -> dict:
        """
        Parse a free-form reference like "John 3:16" or "D&C 76:22-24"
        and return the verse text.
        """
        ref = self._homer_lines(reference.strip())
        for _name, read, tradition_key in self._readers_before_parsing(_quran_api):
            result = read(ref)
            if result is not None:
                return _tagged(result, tradition_key) if tradition_key else result

        parsed = self._parse_reference(ref)
        if parsed is None:
            return {
                "found": False,
                "error": f'Could not parse reference: **{ref}**\nTry: `Book Chapter:Verse`',
                "suggestions": self._suggest_books(ref),
            }

        # Ranges in a book we don't have may still be in Sefaria's library ("Mishnah Oholot 10:7-11:1")
        if len(parsed) == 6 and self._resolve_book(parsed[0])[1] is None:
            import sefaria_lookup
            any_result = sefaria_lookup.fetch_sefaria_any(ref)
            if any_result is not None:
                return _tagged(any_result, "jewish")

        # Cross-chapter range sentinel
        if len(parsed) == 6 and parsed[5] == "cross_chapter":
            book_raw, c1, v1, c2, v2, _ = parsed
            return self.get_verse_range(book_raw, c1, v1, c2, v2)

        # Multi-chapter range sentinel
        if len(parsed) == 6 and parsed[5] == "chap_range":
            book_raw, c1, _, c2, _, _ = parsed
            return self.get_chapter_range(book_raw, c1, c2)

        book_raw, chapter, verse_start, verse_end = parsed
        corpus, canon_book = self._resolve_book(book_raw)

        # ── Kitab-i-Aqdas: paragraph-based, ignore verse number ──────────────
        if canon_book == "Kitab-i-Aqdas":
            chap_data = self._data.get("bahai", {}).get("Kitab-i-Aqdas", {}).get(str(chapter))
            if chap_data is None:
                max_p = max((int(k) for k in self._data.get("bahai", {}).get("Kitab-i-Aqdas", {})), default=190)
                return {"found": False, "error": f"**Kitáb-i-Aqdas** has no paragraph {chapter}. (Max: {max_p})", "suggestions": []}
            text = chap_data.get("1", "")
            return {"found": True, "reference": f"Kitáb-i-Aqdas ¶{chapter}",
                    "text": text, "source": "Bahá'í World Centre (1992)",
                    "book": "Kitab-i-Aqdas", "chapter": chapter, "verse": 1}
        if canon_book is None:
            for _name, read, tradition_key in self._readers_for_unknown_books():
                result = read(ref, book_raw, chapter, verse_start, verse_end)
                if result is not None:
                    return _tagged(result, tradition_key)
            return {
                "found": False,
                "error": f'Unknown book: **{book_raw}**',
                "suggestions": self._suggest_books(book_raw),
            }

        chap_key = chapter if isinstance(chapter, str) else str(chapter)
        # Books whose chapters are themselves "book.chapter" (Imitation of
        # Christ 3.5, Rig Veda 10.121): "3.5" with no verse is that chapter
        book_chapters = self._data[corpus].get(canon_book, {}) if corpus else {}
        if (verse_start is not None and verse_end is None and chap_key not in book_chapters
                and f"{chap_key}.{verse_start}" in book_chapters):
            chap_key, chapter, verse_start = f"{chap_key}.{verse_start}", f"{chap_key}.{verse_start}", None
        # A one-part poem cited by line alone ("Works and Days 289")
        if (list(book_chapters) == ["1"] and verse_start is None          # ("Samson Agonistes 41" too)
                and chap_key.isdigit() and chap_key != "1"):
            verse_start = verse_end = int(chap_key)
            chap_key = chapter = "1"
        if canon_book in self._VERSE_NUMBERED:
            chap_key, verse_start, verse_end = self._locate_numbered_verse(
                canon_book, chap_key, verse_start, verse_end)
            chapter = chap_key
        chap_data = self._data[corpus].get(canon_book, {}).get(chap_key)
        if chap_data is None:
            def _chap_sort(k):
                try: return [int(x) for x in k.split('.')]
                except: return [0]
            all_keys = sorted(self._data[corpus][canon_book].keys(), key=_chap_sort)
            max_chap = all_keys[-1] if all_keys else "0"
            min_chap = all_keys[0] if all_keys else "0"
            range_note = f"{min_chap}–{max_chap}" if min_chap != "1" else max_chap
            return {
                "found": False,
                "error": f'**{canon_book}** has no chapter {chapter}. (Available: {range_note})',
                "suggestions": [],
            }

        source_map = {
            "kjv":               "King James Bible (with Apocrypha)",
            "lds":               "LDS Standard Works",
            "brenton":           "Brenton Septuagint",
            "charles":           "R.H. Charles",
            "apostolic_fathers": "Apostolic Fathers (J.B. Lightfoot)",
            "quran":             "The Glorious Quran (Pickthall)",
            "classical":         "Classical & Ancient Texts",
            "jewish":            "Jewish Hellenistic Texts",
            "bahai":             "Bahá'í Writings",
            "qumran":            "Open Dead Sea (machine draft)",
            "gnostic":           "Gnostic & Esoteric Texts",
            "dharmic":           "Dharmic Scriptures Team (2008)",
            "buddhist":          "Buddhist Texts",
            "nt_apocrypha":      "Apocrypha of the New Testament (ANF VIII)",
            "chinese":           "Chinese Classics (Legge)",
            "sufi":              "Sufi Poetry",
            "sikh":              "Sikh Scripture",
            "jain":              "Jaina Sutras (Jacobi)",
            "shinto":            "Shinto Texts",
            "zoroastrian":       "Zoroastrian Texts",
            "mesoamerican":      "Mesoamerican Texts",
            "finnish":           "The Kalevala",
            "celtic":            "The Mabinogion",
            "norse":            "Trans. Henry Adams Bellows (1923)",
            "patristics":       "Church Fathers (ANF/NPNF/Pearse)",
            "medieval":         "Medieval (Bede, Golden Legend)",
            "reformation":      "Reformation (Luther, Calvin, the confessions)",
            "ancient_near_east":          "Ancient Near Eastern Texts",
        }

        # Determine source string — prefer per-book source, fall back to corpus map
        source = self._book_sources.get(canon_book, source_map.get(corpus, corpus))

        # Psalms 151-155 are stored as book "Psalm 151", chapter "151" --
        # don't label them "Psalm 151 151:1".
        chap_label = canon_book if canon_book.endswith(f" {chapter}") else f"{canon_book} {chapter}"

        # Whole chapter requested (no verse number given)
        if verse_start is None:
            sorted_verses = sorted(chap_data.keys(), key=lambda x: (int(re.sub(r'\D', '', x) or 0), x))
            texts = [f"**[{v}]** {chap_data[v]}" for v in sorted_verses]

            # Split into pages of 20 verses
            PAGE_SIZE = 15
            pages = ["\n".join(texts[i:i+PAGE_SIZE]) for i in range(0, len(texts), PAGE_SIZE)]

            return {
                "found": True,
                "reference": chap_label,
                "text": "\n".join(texts),
                "source": source,
                "pages": pages,   # present if chapter needs pagination
            }

        if verse_end is None:
            verse_end = verse_start

        if canon_book in self._LINE_CHUNKED and chap_data:
            final = max(int(k) for k in chap_data)
            if verse_start > final + 4:
                return {
                    "found": False,
                    "error": f"{canon_book} {chapter} has no line {verse_start} (its last passage starts at line {final}).",
                    "suggestions": [],
                }
            first, last, chosen = self._line_span(chap_data, verse_start, verse_end)
            texts = [f"**[{s}]** {chap_data[str(s)]}" for s in chosen]
            span = f"{first}" if first == last else f"{first}–{last}"
            return {
                "found": True,
                "reference": f"{chap_label}:{span}",
                "text": "\n".join(texts),
                "source": source,
            }

        texts = []
        for v in range(verse_start, verse_end + 1):
            val = chap_data.get(str(v))
            if val:
                t = val if isinstance(val, str) else val.get("1", "")
                if t:
                    texts.append(f"**[{v}]** {t}")

        if not texts:
            max_v = max((int(k) for k in chap_data), default=0)
            return {
                "found": False,
                "error": f'Verse {verse_start} not found in {canon_book} {chapter}. (Max verse: {max_v})',
                "suggestions": [],
            }

        verse_label = f"{verse_start}" if verse_start == verse_end else f"{verse_start}–{verse_end}"
        return {
            "found": True,
            "reference": f"{chap_label}:{verse_label}",
            "text": "\n".join(texts),
            "source": source,
        }

    def search(self, query: str, limit: int = 5, offset: int = 0) -> tuple[list[dict], int]:
        """
        Full-text search across all loaded data.
        Returns (results, total_count).
        Exact phrase matches rank above all-words-present matches.
        """
        q = query.lower().strip()
        words = q.split()
        all_hits = []
        for corpus, books in self._data.items():
            for book, chapters in books.items():
                if book in HIDDEN_BOOKS:
                    continue
                for chap, verses in chapters.items():
                    for verse, text in verses.items():
                        t = text.lower() if isinstance(text, str) else ""
                        if not t:
                            continue
                        if q in t:
                            score = 2
                        elif all(w in t for w in words):
                            score = 1
                        else:
                            continue
                        all_hits.append({
                            "reference": f"{book} {chap}:{verse}",
                            "text": text,
                            "source": self._book_sources.get(book, corpus),
                            "book": book,
                            "_score": score,
                        })
        all_hits.sort(key=lambda x: (-x["_score"], x["reference"]))
        total = len(all_hits)
        results = all_hits[offset:offset + limit]
        for r in results:
            del r["_score"]
        return results, total

    def search_by_corpus(self, query: str, corpora=None) -> dict[str, list[dict]]:
        """
        Full-text search grouped by corpus, optionally only in `corpora`
        (see TRADITIONS). Returns {corpus_label: [hit, ...]} with all hits.
        Results are cached per query (up to 64 queries).
        """
        q = query.lower().strip()
        if not re.search(r"[^\W_]", q):                    # nothing to look for: "$", "*", "~"
            return {}
        corpora = frozenset(corpora) if corpora else None
        # Check cache
        cached = self._search_cache.get((q, corpora))
        if cached is not None:
            return cached

        words = q.split()

        _LABELS = {
            "kjv":              "📖 Bible (KJV)",
            "lds":              "📯 LDS Standard Works",
            "brenton":          "📖 Brenton Septuagint",
            "charles":          "👼 Pseudepigrapha (Charles)",
            "apostolic_fathers":"⛪ Apostolic Fathers",
            "quran":            "☪️ Quran & Hadith",
            "classical":        "🏛️ Classical",
            "jewish":           "✡️ Jewish Texts",
            "bahai":            "🌍 Baháʼí",
            "qumran":           "🏺 Dead Sea Scrolls",
            "gnostic":          "🧿 Gnostic / Hermetic",
            "dharmic":          "☸️ Dharmic",
            "buddhist":         "☸️ Buddhist",
            "nt_apocrypha":     "📜 New Testament Apocrypha",
            "chinese":          "☯️ Chinese Classics",
            "sufi":             "🌹 Sufi Poetry",
            "sikh":             "🪯 Sikh",
            "jain":             "🤚 Jain",
            "shinto":           "⛩️ Shinto",
            "zoroastrian":      "🔥 Zoroastrian",
            "mesoamerican":     "🌽 Mesoamerican",
            "finnish":          "🦢 Finnish",
            "celtic":           "☘️ Celtic",
            "norse":            "🌲 Norse",
            "ancient_near_east":          "🌙 Ancient Near East",
            "patristics":       "⛪ Church Fathers",
            "medieval":         "📜 Medieval",
            "reformation":      "✝️ Reformation",
        }

        by_corpus: dict[str, list[dict]] = {}
        for corpus, books in self._data.items():
            if corpora and corpus not in corpora:
                continue
            hits = []
            for book, chapters in books.items():
                if book in HIDDEN_BOOKS:
                    continue
                for chap, verses in chapters.items():
                    for verse, text in verses.items():
                        t = text.lower() if isinstance(text, str) else ""
                        if not t:
                            continue
                        if q in t:
                            score = 2
                        elif all(w in t for w in words):
                            score = 1
                        else:
                            continue
                        hits.append({
                            "reference": f"{book} {chap}:{verse}",
                            "text": text,
                            "source": self._book_sources.get(book, corpus),
                            "book": book,
                            "_score": score,
                        })
            if hits:
                hits.sort(key=lambda x: (-x["_score"], x["reference"]))
                for h in hits:
                    del h["_score"]
                label = _LABELS.get(corpus, corpus)
                by_corpus[label] = hits

        # Simple LRU: evict oldest if over 64 entries
        if len(self._search_cache) >= 64:
            oldest = next(iter(self._search_cache))
            self._search_cache.pop(oldest, None)        # (two searches may finish at once, each in its thread)
        self._search_cache[(q, corpora)] = by_corpus
        return by_corpus

    @staticmethod
    def _stem(word: str) -> str:
        """A crude stem, so "forgiveness" also finds forgive/forgiven/forgiving."""
        for suffix in ("fulness", "iness", "ness", "ings", "ing", "edly", "ied", "ies", "ed", "es", "s", "ful", "ly"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[:-len(suffix)]
                break
        return word[:-1] if word.endswith(("e", "y")) and len(word) > 3 else word

    # endings a theme word may take: care -> cares, cared, caring, careth, careful, carefully...
    _ENDINGS = r"(?:s|es|d|ed|n|en|ing|ings|th|eth|st|est|r|er|ers|ness|ful|fully|fulness|less|ly|'s)"

    @classmethod
    def word_regex(cls, word: str) -> str:
        """The word and its inflections, not every word it starts: "care" finds cared,
        caring, careth and careful, but not carry or cart; "mercy" finds mercies, merciful."""
        stem = cls._stem(word)
        forms = rf"{re.escape(stem)}[eyi]?{cls._ENDINGS}?"
        if stem != word:                                  # "car" alone isn't a form of "care"
            forms = rf"{re.escape(stem)}(?:[eyi]{cls._ENDINGS}?|{cls._ENDINGS})"
        return rf"\b{forms}\b"

    def theme_passages(self, query: str) -> list:
        """One passage per tradition (TRADITIONS order) mentioning every word
        of `query`: [(tradition label, hit)], hit = {"reference", "text", "book"}.
        Ranked by: the exact phrase; how often the theme comes up (a passage
        *about* love, not one that mentions it once); how densely; and a
        quotable length (40-600 characters)."""
        q = query.lower().strip()
        cached = self._theme_cache.get(q)
        if cached is not None:
            return cached
        # a theme is words: "$", "*" or "34" would only match symbols and verse numbers
        words = [w for w in (re.sub(r"^[^\w]+|[^\w]+$", "", w) for w in q.split()) if re.search(r"[^\W\d_]", w)]
        if not words:
            return []
        patterns = [re.compile(self.word_regex(w), re.IGNORECASE) for w in words]
        out = []
        for key, (label, corpora) in TRADITIONS.items():
            best = None
            for corpus in corpora:
                for book, chapters in self._data.get(corpus, {}).items():
                    for chap, verses in chapters.items():
                        for verse, text in verses.items():
                            if not isinstance(text, str) or not 40 <= len(text) <= 600:
                                continue
                            if not all(p.search(text) for p in patterns):
                                continue
                            hits = sum(len(p.findall(text)) for p in patterns)
                            score = (q in text.lower(), min(hits, 3), round(hits * 100 / len(text), 1))
                            if best is None or score > best[0]:
                                best = (score, {"reference": f"{book} {chap}:{verse}", "text": text, "book": book})
            if best:
                out.append((label, best[1]))
        if len(self._theme_cache) >= 32:
            self._theme_cache.pop(next(iter(self._theme_cache), None), None)
        self._theme_cache[q] = out
        return out

    def get_verse_range(self, book_raw: str, chap_start: int, verse_start: int,
                        chap_end: int, verse_end: int) -> dict:
        """Fetch a cross-chapter range, e.g. John 7:53–8:11."""
        corpus, canon_book = self._resolve_book(book_raw)
        if canon_book is None:
            return {"found": False, "error": f"Unknown book: **{book_raw}**", "suggestions": self._suggest_books(book_raw)}
        book_data = self._data[corpus].get(canon_book, {})
        source = self._book_sources.get(canon_book, corpus)
        texts = []
        for chap_n in range(chap_start, chap_end + 1):
            chap_data = book_data.get(str(chap_n), {})
            if not chap_data:
                continue
            max_v = max((int(k) for k in chap_data if k.isdigit()), default=0)
            v_from = verse_start if chap_n == chap_start else 1
            v_to   = verse_end   if chap_n == chap_end   else max_v
            for v in range(v_from, v_to + 1):
                val = chap_data.get(str(v))
                if val:
                    t = val if isinstance(val, str) else val.get("1", "")
                    if t:
                        texts.append(f"**[{chap_n}:{v}]** {t}")
        if not texts:
            return {"found": False, "error": f"No verses found for **{canon_book} {chap_start}:{verse_start}–{chap_end}:{verse_end}**.", "suggestions": []}
        return {"found": True, "reference": f"{canon_book} {chap_start}:{verse_start}–{chap_end}:{verse_end}",
                "text": "\n".join(texts), "source": source}

    def get_chapter_range(self, book_raw: str, chap_start: int, chap_end: int) -> dict:
        """Fetch multiple whole chapters, e.g. John 3-5."""
        corpus, canon_book = self._resolve_book(book_raw)
        if canon_book is None:
            return {"found": False, "error": f"Unknown book: **{book_raw}**", "suggestions": self._suggest_books(book_raw)}
        book_data = self._data[corpus].get(canon_book, {})
        source = self._book_sources.get(canon_book, corpus)

        all_texts = []
        for chap_n in range(chap_start, chap_end + 1):
            chap_data = book_data.get(str(chap_n))
            if not chap_data:
                continue
            sorted_vs = sorted(chap_data.keys(), key=lambda x: (int(re.sub(r'\D','',x) or 0), x))
            all_texts.append(f"**── Chapter {chap_n} ──**")
            all_texts.extend(f"**[{v}]** {chap_data[v]}" for v in sorted_vs)

        if not all_texts:
            return {"found": False, "error": f"No chapters found for **{canon_book} {chap_start}–{chap_end}**.", "suggestions": []}

        PAGE = 15
        pages = ["\n".join(all_texts[i:i+PAGE]) for i in range(0, len(all_texts), PAGE)]
        return {
            "found": True,
            "reference": f"{canon_book} {chap_start}–{chap_end}",
            "text": "\n".join(all_texts),
            "source": source,
            "pages": pages if len(pages) > 1 else None,
        }

    def _try_sefaria(self, book_raw: str, chapter: int, verse_start, verse_end) -> Optional[dict]:
        """
        Try Mishnah, Talmud, or Zohar via Sefaria.
        Returns a result dict if found, or None.
        """
        book_lc = book_raw.lower().strip()

        # ── Zohar ─────────────────────────────────────────────────────────────
        # User types: "Zohar 1:1a:3"  → book_raw="Zohar 1", chapter parsed weirdly
        # Better: detect "zohar" prefix and re-parse the full original string
        # Also handles "Zohar Bereshit" from BOOKS_TREE (book_raw has parasha)
        if book_lc in ("zohar", "the zohar", "sefer hazohar"):
            return None  # handled by _try_zohar_raw
        if book_lc.startswith("zohar "):
            # e.g. book_raw="Zohar Bereshit", chapter=5 → fetch_zohar("Bereshit", 5)
            from sefaria_lookup import fetch_zohar
            parasha = book_raw.strip()[6:].strip()  # strip "Zohar "
            segment = chapter if chapter else verse_start
            result = fetch_zohar(parasha, segment)
            return result if result and result.get("found") else None

        # ── Talmud — detect daf-style chapter ─────────────────────────────────
        # "Talmud Berakhot 2a:3" → _parse_reference gives book="Talmud Berakhot 2a", chapter=3
        # We need to detect "2a" at end of book_raw and re-route
        talmud_in_book = re.match(
            r"^(.*?)\s+(\d+[ab])$", book_raw, re.IGNORECASE
        )
        if talmud_in_book:
            tractate_raw = talmud_in_book.group(1).strip()
            daf          = talmud_in_book.group(2).lower()
            # Strip "talmud"/"gemara" prefix from tractate_raw if present
            tractate_raw = re.sub(
                r"^(?:talmud|gemara|bavli|bt)\s+", "", tractate_raw,
                flags=re.IGNORECASE
            ).strip()
            tractate = resolve_talmud_tractate(tractate_raw)
            if tractate:
                from sefaria_lookup import fetch_talmud
                # chapter here is the section number (from "2a:3" → chapter=3)
                section = verse_start if verse_start else chapter
                return fetch_talmud(tractate, daf, section if verse_start else None)

        # ── Mishnah ────────────────────────────────────────────────────────────
        index = resolve_tractate(book_lc)
        if index is None:
            return None

        if verse_start is None:
            return fetch_mishnah_chapter(index, chapter)
        else:
            end = verse_end if verse_end else verse_start
            if verse_start == end:
                return fetch_mishnah(index, chapter, verse_start)
            else:
                texts = []
                for v in range(verse_start, end + 1):
                    r = fetch_mishnah(index, chapter, v)
                    if r["found"]:
                        texts.append(f"**[{v}]** {r['text']}")
                if texts:
                    index_display = index.replace("Mishnah_", "").replace("_", " ")
                    v_label = f"{verse_start}–{end}"
                    return {
                        "found": True,
                        "reference": f"Mishnah {index_display} {chapter}:{v_label}",
                        "text": "\n".join(texts),
                        "source": r.get("source", "Sefaria"),
                    }
                return None

    def _try_hermas(self, raw_ref: str) -> Optional[dict]:
        """Traditional Shepherd of Hermas citations -> Lightfoot's continuous
        chapters, which is how the data is stored.
          Herm Sim 9        → Similitude 9, its chapter 1   (continuous 78)
          Herm Sim 9:1      → Similitude 9, chapter 1       (continuous 78)
          Herm Sim 9:1:3    → ... verse 3   (also 9.1.3, and 9:1:3-5 ranges)
        Plain "Hermas 78:3" is left to the normal parser (continuous numbering)."""
        m = _HERMAS_REF.match(raw_ref.strip())
        if not m:
            return None
        part_key = m.group("part").lower()[0]          # v / m / s
        part_name, ranges = _HERMAS_PARTS[part_key]
        n = int(m.group("n"))
        chap = int(m.group("chap") or 1)
        verse = m.group("verse")
        verse_end = m.group("verse_end")

        if not 1 <= n <= len(ranges):
            return {"found": False,
                    "error": f"The Shepherd of Hermas has {len(ranges)} {part_name}s (no {part_name} {n}).",
                    "suggestions": []}
        first, last = ranges[n - 1]
        if not 1 <= chap <= last - first + 1:
            return {"found": False,
                    "error": f"{part_name} {n} has {last - first + 1} chapter(s) (no chapter {chap}).",
                    "suggestions": []}
        continuous = first + chap - 1

        inner_ref = f"Shepherd of Hermas {continuous}"
        if verse:
            inner_ref += f":{verse}" + (f"-{verse_end}" if verse_end else "")
        result = self.get_verse(inner_ref)
        label = f"{n}.{chap}" + (f".{verse}" if verse else "") + (f"–{verse_end}" if verse_end else "")
        if result.get("found"):
            result["reference"] = f"Shepherd of Hermas, {part_name} {label} (ch. {continuous})"
        elif "has no chapter" in result.get("error", ""):
            result["error"] = (f"{part_name} {n}.{chap} (continuous ch. {continuous}) "
                               f"isn't in the local text of the Shepherd of Hermas.")
        return result

    def _try_zohar_raw(self, raw_ref: str) -> Optional[dict]:
        """
        Try to parse and fetch a Zohar reference.
        Handles: "Zohar Bereshit 5", "Zohar Introduction", bare "Zohar" for random.
        """
        import random as _random
        stripped = re.sub(r"^(?:the\s+)?zohar\s*", "", raw_ref, flags=re.IGNORECASE).strip()

        # Bare "Zohar" — pick a random parasha and segment
        if not stripped:
            from sefaria_lookup import ZOHAR_PARASHOT, fetch_zohar
            parasha, max_seg = _random.choice(ZOHAR_PARASHOT)
            segment = _random.randint(1, min(max_seg, 30))
            result = fetch_zohar(parasha, segment)
            if not result.get("found"):
                result = fetch_zohar(parasha, 1)
            return result if result.get("found") else None

        from sefaria_lookup import parse_zohar_ref, fetch_zohar
        parsed = parse_zohar_ref("zohar " + stripped)
        if parsed is None:
            return None
        parasha, segment = parsed
        return fetch_zohar(parasha, segment)

    def _try_ancient_near_east(self, raw_ref: str) -> Optional[dict]:
        """
        Intercept ANE references before generic parsing.
        Formats:
          Baal 1:5      → Episode 1 (Baal and Yamm), section 5
          Baal 2        → Episode 2 (The Palace of Baal), random section
          Muallaqat 1:5 → Ode I (Imru' al-Qais), stanza 5
          Muallaqat 1   → Ode I, random stanza
          Also: "Baal and Yamm 5", "Tarafa 10", etc. via ALIASES
        """
        _BAAL_BOOKS = {
            "1": "Baal and Yamm",
            "2": "The Palace of Baal",
            "3": "Baal and Mot",
        }
        _MUA_BOOKS = {
            "1": "Muallaqat: Imru' al-Qais",
            "2": "Muallaqat: Tarafa ibn al-'Abd",
            "3": "Muallaqat: Zuhayr ibn Abi Sulma",
            "4": "Muallaqat: Labid ibn Rabi'ah",
            "5": "Muallaqat: Antara ibn Shaddad",
            "6": "Muallaqat: Amr ibn Kulthum",
            "7": "Muallaqat: Al-Harith ibn Hilliza",
        }
        import re as _re, random as _rand

        # Match "Baal N" or "Baal N:M"
        m = _re.match(r"^baal\s+(\d)(?::(\d+))?$", raw_ref.strip(), _re.IGNORECASE)
        if m:
            book_name = _BAAL_BOOKS.get(m.group(1))
            if book_name:
                section = m.group(2)
                return self._ane_fetch("ancient_near_east", book_name, section)

        # Match "Muallaqat N" or "Muallaqat N:M"
        m = _re.match(r"^(?:mu\'allaqat|muallaqat|muallaqa)\s+(\d)(?::(\d+))?$",
                      raw_ref.strip(), _re.IGNORECASE)
        if m:
            book_name = _MUA_BOOKS.get(m.group(1))
            if book_name:
                section = m.group(2)
                return self._ane_fetch("ancient_near_east", book_name, section)

        # Match "Gilgamesh N" or "Gilgamesh N:M" (tablet:section)
        _gil_match = _re.match(r"^gilgamesh[^\d]*(\d{1,2})(?::(\d+))?$",
                               raw_ref.strip(), _re.IGNORECASE)
        if _gil_match:
            gil_book = "Gilgamesh Tablet " + _gil_match.group(1)
            return self._ane_fetch("ancient_near_east", gil_book, _gil_match.group(2))

        # Single-book texts — keyword lookup, optional section number
        _SINGLE_BOOKS = [
            ("aten",             "The Great Hymn to the Aten"),
            ("hymn to the aten", "The Great Hymn to the Aten"),
            ("book of the dead", "Book of the Dead"),
            ("pert em hru",      "Book of the Dead"),
            ("leiden hymns",     "The Leiden Hymns"),
            ("hymns to amun",    "The Leiden Hymns"),
            ("amenemope",        "The Instruction of Amenemope"),
            ("two ways",         "The Book of Two Ways"),
            ("book of two ways", "The Book of Two Ways"),
            ("coffin texts",     "The Book of Two Ways"),
            ("ahikar",           "The Story of Ahikar"),
            ("ahiqar",           "The Story of Ahikar"),
        ]
        ref_lc = raw_ref.strip().lower()
        for keyword, book_name in _SINGLE_BOOKS:
            if ref_lc == keyword:
                return self._ane_fetch("ancient_near_east", book_name, None)
            if ref_lc.startswith(keyword + " "):
                rest = ref_lc[len(keyword):].strip()
                if rest.isdigit():
                    return self._ane_fetch("ancient_near_east", book_name, rest)

        return None

    def _ane_fetch(self, corpus: str, book_name: str, section: str | None) -> Optional[dict]:
        """Fetch a section from an ANE book by book name and optional section number.
        If section is None, return the entire book paginated (like !verse Iliad 1)."""
        import random as _rand
        book_data = self._data.get(corpus, {}).get(book_name)
        if book_data is None:
            return {"found": False,
                    "error": f"**{book_name}** not found. Is `data/ancient_near_east/` populated?",
                    "suggestions": []}
        source = self._book_sources.get(book_name, corpus)

        # Sections are stored in the standard schema as {"1": text}.
        def _section_text(value) -> str:
            return value if isinstance(value, str) else value.get("1", "")

        if section is None:
            # Return entire book, paginated like poem_lookup does
            items = sorted(((k, _section_text(v)) for k, v in book_data.items()),
                           key=lambda x: int(x[0]) if x[0].isdigit() else 0)
            PAGE = 3  # ANE sections are long — 3 per page
            pages, chunk = [], []
            for _, text in items:
                chunk.append(text)
                if len(chunk) >= PAGE:
                    pages.append("\n\n---\n\n".join(chunk))
                    chunk = []
            if chunk:
                pages.append("\n\n---\n\n".join(chunk))
            full_text = "\n\n---\n\n".join(v for _, v in items)
            return {
                "found": True,
                "reference": book_name,
                "text": pages[0] if pages else full_text,
                "source": source,
                "book": book_name,
                "chapter": "1",
                "verse": "1",
                "pages": pages if len(pages) > 1 else None,
            }

        if section not in book_data:
            max_sec = max((int(k) for k in book_data if k.isdigit()), default=1)
            return {"found": False,
                    "error": f"**{book_name}** has no section {section}. (Max: {max_sec})",
                    "suggestions": []}
        text = _section_text(book_data[section])
        return {
            "found": True,
            "reference": f"{book_name} {section}",
            "text": text,
            "source": source,
            "book": book_name,
            "chapter": section,
            "verse": section,
        }

    def _try_yerushalmi(self, book_raw: str, chapter: int, halakhah) -> Optional[dict]:
        """Jerusalem Talmud via Sefaria. Cite: !verse Jerusalem Talmud Berakhot 1:1"""
        # Strip prefix
        import re as _re
        stripped = _re.sub(
            r"^(?:jerusalem\s+talmud|yerushalmi|talmud\s+yerushalmi|jt)\s+",
            "", book_raw.lower().strip()
        )
        tractate_key = stripped.strip()
        sefaria_name = YERUSHALMI_TRACTATES.get(tractate_key)
        if sefaria_name is None:
            return None
        ref = f"{sefaria_name}.{chapter}"
        if halakhah:
            ref += f".{halakhah}"
        result = fetch_sefaria_generic(ref)
        if result and result.get("found"):
            display = sefaria_name.replace("Jerusalem_Talmud_", "").replace("_", " ")
            v_label = f"{chapter}:{halakhah}" if halakhah else str(chapter)
            result["reference"] = f"Jerusalem Talmud {display} {v_label}"
            result["source"] = "trans. Guggenheimer"
        return result

    def _try_tosefta(self, book_raw: str, chapter: int, verse_start) -> Optional[dict]:
        """Tosefta via Sefaria. Cite: !verse Tosefta Berakhot 1:1"""
        import re as _re
        stripped = _re.sub(r"^tosefta\s+", "", book_raw.lower().strip())
        # Map to Sefaria name — same tractate names as Mishnah
        index = resolve_tractate(stripped)
        if index is None:
            return None
        sefaria_name = "Tosefta_" + index.replace("Mishnah_", "")
        ref = f"{sefaria_name}.{chapter}"
        if verse_start:
            ref += f".{verse_start}"
        result = fetch_sefaria_generic(ref)
        if result and result.get("found"):
            display = sefaria_name.replace("Tosefta_", "").replace("_", " ")
            v_label = f"{chapter}:{verse_start}" if verse_start else str(chapter)
            result["reference"] = f"Tosefta {display} {v_label}"
            result["source"] = "Sefaria"
        return result

    def _try_targum(self, raw_ref: str) -> Optional[dict]:
        """Targumim via Sefaria. Cite: !verse Targum Onkelos Genesis 1:1"""
        import re as _re
        raw_lc = raw_ref.lower().strip()
        # Identify which targum
        targum_sefaria = None
        remainder = raw_lc
        for key in sorted(TARGUM_NAMES, key=len, reverse=True):
            if raw_lc.startswith(key):
                targum_sefaria = TARGUM_NAMES[key]
                remainder = raw_lc[len(key):].strip()
                break
        if targum_sefaria is None:
            return None
        if not remainder:
            return None
        # remainder should be "Genesis 1:1" etc.
        parsed = self._parse_reference(remainder)
        if parsed is None:
            return None
        book_raw, chapter, verse_start, verse_end = parsed
        _, canon_book = self._resolve_book(book_raw)
        if canon_book is None:
            return None
        # Map canon book to Sefaria targum ref format. Onkelos's real Sefaria
        # title is "Onkelos Genesis" (verified directly against the API,
        # confirmed against "Targum_Onkelos,_Genesis" 404ing) -- other targum
        # variants use different conventions (e.g. "Targum Jonathan on Isaiah")
        # not handled here, since only Onkelos is exposed via !books.
        book_url = canon_book.replace(" ", "_")
        if targum_sefaria == "Onkelos":
            ref = f"Onkelos_{book_url}.{chapter}"
            tname = "Targum Onkelos"
        else:
            ref = f"{targum_sefaria},{book_url}.{chapter}"
            tname = targum_sefaria.replace("_", " ")
        if verse_start:
            ref += f".{verse_start}"
        result = fetch_sefaria_generic(ref)
        if result and result.get("found"):
            v_label = f"{chapter}:{verse_start}" if verse_start else str(chapter)
            result["reference"] = f"{tname} {canon_book} {v_label}"
            result["source"] = "Sefaria"
        return result

    def _try_midrash(self, book_raw: str, chapter: int, verse_start) -> Optional[dict]:
        """Midrash Rabbah and other Midrashim via Sefaria. Cite: !verse Bereshit Rabbah 1:1"""
        key = book_raw.lower().strip()
        sefaria_name = MIDRASH_NAMES.get(key)
        if sefaria_name is None:
            return None
        ref = f"{sefaria_name}.{chapter}"
        if verse_start:
            ref += f".{verse_start}"
        result = fetch_sefaria_generic(ref)
        if result and result.get("found"):
            display = sefaria_name.replace("_", " ").replace("d\'", "d'")
            v_label = f"{chapter}:{verse_start}" if verse_start else str(chapter)
            result["reference"] = f"{display} {v_label}"
            result["source"] = "Sefaria"
        return result

    def _try_kabbalah(self, book_raw: str, chapter: int, verse_start) -> Optional[dict]:
        """Kabbalistic texts via Sefaria beyond Zohar.
        Cite: !verse Sefer Yetzirah 1:1
        Tanya: !verse Tanya 1:5  (part 1, chapter 5)
               !verse Tanya 2:1  (part 2 = Shaar HaYichud, chapter 1)
        """
        key = book_raw.lower().strip()
        sefaria_name = KABBALAH_NAMES.get(key)
        if sefaria_name is None:
            return None

        # Tanya: chapter = part number, verse_start = chapter within that part
        if key == "tanya":
            part_num = chapter if chapter else 1
            chapter_in_part = verse_start if verse_start else 1
            part_info = TANYA_PARTS.get(part_num)
            if part_info is None:
                # Out of range — default to Part I
                part_info = TANYA_PARTS[1]
                part_num = 1
            tref, max_chaps = part_info
            ref = f"{tref}.{chapter_in_part}"
            result = fetch_sefaria_generic(ref)
            if result and result.get("found"):
                part_names = {
                    1: "Likkutei Amarim",
                    2: "Shaar HaYichud VehaEmunah",
                    3: "Iggeret HaTeshuvah",
                    4: "Iggeret HaKodesh",
                    5: "Kuntres Acharon",
                }
                pname = part_names.get(part_num, f"Part {part_num}")
                result["reference"] = f"Tanya, {pname} ch. {chapter_in_part}"
                result["source"] = "Sefaria"
            return result

        # All other Kabbalah texts
        ref = f"{sefaria_name}.{chapter}"
        if verse_start:
            ref += f".{verse_start}"
        result = fetch_sefaria_generic(ref)
        if result and result.get("found"):
            display = sefaria_name.replace("_", " ")
            v_label = f"{chapter}:{verse_start}" if verse_start else str(chapter)
            result["reference"] = f"{display} {v_label}"
            result["source"] = "Sefaria"
        return result

    def _try_mishneh_torah(self, raw_ref: str) -> Optional[dict]:
        """Mishneh Torah via Sefaria. Cite: !verse Mishneh Torah, Repentance 1:1"""
        import re as _re
        # Format: "Mishneh Torah, Section Name chapter:halacha"
        # Require one of the prefix aliases to actually be present -- re.sub
        # with no match just returns the string unchanged, which previously
        # let ANY unrelated "Name N" or "Name N:M" reference (e.g. "Guide for
        # the Perplexed 1:1") fall through to the generic parse below,
        # construct a bogus Mishneh-Torah tref, 404 against Sefaria, and
        # short-circuit the dispatch chain before it ever reached the
        # reference's real handler.
        prefix_re = _re.compile(
            r"^(?:mishneh torah|yad hachazakah|rambam|maimonides)\b[,\s]*",
            _re.IGNORECASE,
        )
        m_prefix = prefix_re.match(raw_ref.strip())
        if not m_prefix:
            return None
        stripped = raw_ref.strip()[m_prefix.end():].strip().lstrip(",").strip()
        if not stripped:
            return None
        # Parse "Section Name chapter:halacha" or "Section Name chapter"
        m = _re.match(r"^(.+?)\s+(\d+)(?::(\d+))?$", stripped)
        if not m:
            return None
        section = m.group(1).strip()
        chapter = m.group(2)
        halacha = m.group(3)
        # Build Sefaria tref
        section_tref = section.replace(" ", "_").replace(",", "")
        tref = f"Mishneh_Torah,_{section_tref}.{chapter}"
        if halacha:
            tref += f".{halacha}"
        result = fetch_sefaria_generic(tref)
        if result and result.get("found"):
            v_label = f"{chapter}:{halacha}" if halacha else chapter
            result["reference"] = f"Mishneh Torah, {section} {v_label}"
            result["source"] = "trans. Touger"
        return result

    def _try_guide(self, raw_ref: str) -> Optional[dict]:
        """Guide for the Perplexed via Sefaria. Cite: !verse Guide for the Perplexed 1:1"""
        import re as _re
        stripped = _re.sub(
            r"^(?:guide for the perplexed|guide of the perplexed|moreh nevukhim|moreh nebukim)\s*",
            "", raw_ref.strip(), flags=_re.IGNORECASE
        ).strip()
        if not stripped:
            return None
        m = _re.match(r"^(\d+)(?::(\d+))?$", stripped)
        if not m:
            return None
        part = m.group(1)
        chapter = m.group(2)
        # Sefaria's real title is "Guide for the Perplexed, Part N" -- verified
        # directly against the API ("Guide_for_the_Perplexed,_1" 400s;
        # "Guide_for_the_Perplexed,_Part_1" is correct).
        tref = f"Guide_for_the_Perplexed,_Part_{part}"
        if chapter:
            tref += f".{chapter}"
        result = fetch_sefaria_generic(tref)
        if result and result.get("found"):
            label = f"Part {part}" + (f", Ch. {chapter}" if chapter else "")
            result["reference"] = f"Guide for the Perplexed {label}"
            result["source"] = "Sefaria"
        return result

    def _try_hadith(self, raw_ref: str) -> Optional[dict]:
        """Try to resolve the full raw reference as a hadith."""
        return get_hadith(raw_ref)

    def _try_stephanus(self, raw_ref: str) -> Optional[dict]:
        """
        Try to resolve a Plato Stephanus reference.
        Formats accepted:
          "Apology 17a"         → Apology, section 17a
          "Republic 514a"       → Republic, section 514a (book-qualified key tried)
          "Republic 7.514a"     → Republic, section 7.514a
          "Republic 7.514"      → Republic, chapter 7, section 514 (any subsection)
        Returns None if this doesn't look like a Plato ref.
        """
        # Pattern: <words> <optional_book_num.><stephanus_page><optional_letter>
        # [- <end page><end letter>], e.g. "Apology 17a", "Republic 7.514a",
        # "Republic 514", "Republic 361e-362a", "Republic 514a-c", "Republic 514-515"
        m = re.match(
            r"^(.+?)\s+(?:(\d+)\.)?(\d+)([a-e]?)(?:\s*[-–]\s*(\d+)?([a-e])?)?$",
            raw_ref.strip(),
            re.IGNORECASE,
        )
        if not m:
            return None

        book_raw = m.group(1).strip()
        book_num = m.group(2)   # e.g. "7" for Republic 7.514a
        page     = m.group(3)   # e.g. "514"
        section  = m.group(4).lower()  # e.g. "a"
        end_page, end_section = m.group(5), (m.group(6) or "").lower()
        is_range = bool(end_page or end_section)

        # Resolve book name
        corpus, canon_book = self._resolve_book(book_raw)
        if canon_book is None:
            return None

        # Only applies to Plato dialogues
        plato_books = set(ALIASES[k] for k in ALIASES if k in (
            "euthyphro","apology","crito","phaedo","cratylus","theaetetus",
            "sophist","statesman","parmenides","philebus","symposium","phaedrus",
            "alcibiades i","alcibiades ii","hipparchus","rival lovers","theages",
            "charmides","laches","lysis","euthydemus","protagoras","gorgias",
            "meno","greater hippias","lesser hippias","ion","menexenus","cleitophon",
            "republic","timaeus","critias","minos","laws","epinomis","letters",
            "axiochus","on justice","on virtue","demodocus","sisyphus","eryxias",
            "definitions",
        ))
        if canon_book not in plato_books:
            return None

        chap_data = self._data.get(corpus, {}).get(canon_book, {})
        if not chap_data:
            return None

        # Build candidate keys to try, in priority order
        candidates = []
        if book_num and section:
            candidates.append(f"{book_num}.{page}{section}")
        if book_num:
            for s in "abcde":
                candidates.append(f"{book_num}.{page}{s}")
        if section:
            candidates.append(f"{page}{section}")
        for s in "abcde":
            candidates.append(f"{page}{s}")
        candidates.append(page)

        def section_text(val):
            # verse dict wrapper {"1": text} or bare string
            return val.get("1", next(iter(val.values()), "")) if isinstance(val, dict) else val

        source = self._corpus_sources.get(corpus, {}).get(canon_book, "Plato")
        start = next((k for k in candidates if k in chap_data), None)
        if is_range and start is not None:
            return self._stephanus_range(canon_book, chap_data, start, end_page or page, end_section,
                                         section_text, source)

        for key in candidates:
            if key in chap_data:
                text = section_text(chap_data[key])
                return {
                    "found": True,
                    "reference": f"{canon_book} {key}",
                    "text": text,
                    "source": source,
                    "book": canon_book,
                    "chapter": key,
                    "verse": 1,
                }

        # Section not found — report closest available
        available = sorted(chap_data.keys())[:5]
        return {
            "found": False,
            "error": f"**{canon_book} {book_num+'.' if book_num else ''}{page}{section}** not found. Available sections start at: {', '.join(available)}",
            "suggestions": [],
        }

    # ── stepping through a book: ◀ Previous · Next ▶ · 📖 Whole chapter ──────────

    def _units(self, corpus: str, book: str) -> list:
        """Every (chapter, verse) of a book, in reading order."""
        def order(keys):
            keys = list(keys)
            return sorted(keys, key=int) if all(k.isdigit() for k in keys) else keys
        chapters = self._data[corpus][book]
        return [(c, v) for c in order(chapters) if isinstance(chapters[c], dict) for v in order(chapters[c])]

    @staticmethod
    def _unit_ref(book: str, chapters: dict, c: str, v: str) -> str:
        """The reference that opens just this unit: "Timaeus 67b" for a one-passage chapter, else "John 3:16"."""
        return f"{book} {c}" if list(chapters[c]) == ["1"] else f"{book} {c}:{v}"

    def neighbours(self, reference: str) -> dict:
        """{"prev", "next", "chapter"}: the references that open the passage before and after the one a
        result's `reference` shows, and its whole chapter; each None where there's nothing to show. A whole
        chapter steps a chapter at a time. {} for anything this library doesn't hold itself (a translation
        read online, the Talmud...), which can't be stepped through here."""
        m = re.fullmatch(r"(?P<book>.+) (?P<c>[\w.]+?)(?::(?P<v1>\w+)(?:[–-](?P<v2>\w+))?)?(?:[–-](?P<c2>[\w.]+))?",
                         reference.strip())
        if not m:
            return {}
        corpus, book = self._resolve_exact(m["book"])
        if not book or book != m["book"] or m["c"] not in self._data[corpus].get(book, {}):
            return {}
        chapters = self._data[corpus][book]
        units = self._units(corpus, book)
        c = m["c"]
        whole = not m["v1"] and len(chapters[c]) > 1
        if whole:                                            # a chapter: step by chapters
            names = list(dict.fromkeys(u[0] for u in units))
            i = names.index(c)
            j = names.index(m["c2"]) if m["c2"] in names else i
            return {"prev": f"{book} {names[i - 1]}" if i > 0 else None,
                    "next": f"{book} {names[j + 1]}" if j + 1 < len(names) else None, "chapter": None}
        def unit(ch, v):
            """(ch, v), or for a text stored in chunks of lines (Enuma Elish 1:1-8 is the chunk at line 1),
            the chunk that holds line v."""
            if (ch, v) in units or not v.isdigit() or not all(k.isdigit() for k in chapters[ch]):
                return (ch, v)
            held = [k for k in chapters[ch] if int(k) <= int(v)]
            return (ch, max(held, key=int)) if held else (ch, v)

        first = unit(c, m["v1"] or next(iter(chapters[c])))
        last_c = m["c2"] if m["c2"] in chapters and not m["v1"] else c
        last = unit(last_c, m["v2"] or m["v1"] or list(chapters[last_c])[-1])
        if first not in units or last not in units:
            return {}
        i, j = units.index(first), units.index(last)
        return {"prev": self._unit_ref(book, chapters, *units[i - 1]) if i > 0 else None,
                "next": self._unit_ref(book, chapters, *units[j + 1]) if j + 1 < len(units) else None,
                "chapter": f"{book} {c}" if len(chapters[c]) > 1 else None}

    _STEPHANUS_PAGE_CHARS = 3500     # a range longer than this is split into pages

    @staticmethod
    def _stephanus_range(book: str, chap_data: dict, start: str, end_page: str, end_section: str,
                         section_text, source: str) -> dict:
        """Sections start..end in Stephanus order. The end is a section
        ("362a"), or a whole page ("515": through its last section)."""
        keys = list(chap_data)
        if end_section:
            end = f"{end_page}{end_section}" if f"{end_page}{end_section}" in chap_data else None
        else:
            on_page = [k for k in keys if re.fullmatch(rf"(?:\d+\.)?{end_page}[a-e]?", k)]
            end = on_page[-1] if on_page else None
        if end is None:
            return {"found": False, "suggestions": [],
                    "error": f"**{book} {end_page}{end_section}** not found (the range's end)."}
        i, j = keys.index(start), keys.index(end)
        if j < i:
            return {"found": False, "suggestions": [],
                    "error": f"**{book} {start}–{end}**: the range ends before it starts."}
        parts = [f"**[{k}]** {section_text(chap_data[k])}" for k in keys[i:j + 1]]
        pages, current = [], ""
        for part in parts:
            if current and len(current) + len(part) > ScriptureLookup._STEPHANUS_PAGE_CHARS:
                pages.append(current)
                current = ""
            current = f"{current}\n{part}" if current else part
        pages.append(current)
        return {
            "found": True,
            "reference": f"{book} {start}–{end}" if start != end else f"{book} {start}",
            "text": "\n".join(parts),
            "source": source,
            "book": book,
            "chapter": start,
            "verse": 1,
            "pages": pages if len(pages) > 1 else None,
        }

    # ── Parsing ────────────────────────────────────────────────────────────────

    def _parse_reference(self, ref: str):
        """
        Split a reference string into (book, chapter, verse_start, verse_end).
        Handles:
          - 'John 3:16'
          - 'John 3:16-21'
          - 'John 7:53-8:11'  → 6-tuple sentinel (..., 'cross_chapter')
          - 'Rig Veda 10.121:9'
          - 'Rig Veda 10.121.9'
        """
        ref = ref.strip()

        # ── Multi-chapter range: "Book C1-C2" (e.g. "John 3-5") ─────────────
        m_chap_range = re.match(
            r"^(.*)\s+(\d+)\s*[-–—]\s*(\d+)$", ref, re.UNICODE)
        if m_chap_range:
            book = m_chap_range.group(1).strip()
            c1, c2 = int(m_chap_range.group(2)), int(m_chap_range.group(3))
            # Only treat as chapter range if it looks like a plausible range (not a verse range)
            if book and c1 < c2 and c2 - c1 <= 20:
                return (book, c1, None, c2, None, "chap_range")

        # ── Cross-chapter range: "Book C1:V1-C2:V2" ──────────────────────────
        m_cross = re.match(
            r"^(.*)\s+(\d+):(\d+)\s*[-–—]\s*(\d+):(\d+)$", ref, re.UNICODE)
        if m_cross:
            book = m_cross.group(1).strip()
            if book:
                return (book, int(m_cross.group(2)), int(m_cross.group(3)),
                        int(m_cross.group(4)), int(m_cross.group(5)), "cross_chapter")

        # ── Dotted chapter with explicit colon: "Book N.N.N:V" ───────────────
        m_dot_colon = re.match(
            r"^(.*)\s+(\d+(?:\.\d+)+):(\d+)(?:\s*[-–—]\s*(\d+))?$",
            ref, re.UNICODE)
        if m_dot_colon:
            book = m_dot_colon.group(1).strip()
            if book:
                return (book, m_dot_colon.group(2),
                        int(m_dot_colon.group(3)),
                        int(m_dot_colon.group(4)) if m_dot_colon.group(4) else None)

        # ── Dotted chapter without colon: "Book N.N.N" ───────────────────────
        m_dot_bare = re.match(r"^(.*)\s+(\d+(?:\.\d+)+)$", ref, re.UNICODE)
        if m_dot_bare:
            book = m_dot_bare.group(1).strip()
            dotted = m_dot_bare.group(2)
            if book and '.' in dotted:
                last_dot = dotted.rfind('.')
                return book, dotted[:last_dot], int(dotted[last_dot+1:]), None

        # Lazy book group: a greedy one swallows "John 3:16 -" as the book
        # name when whitespace follows the range dash ("John 3:16 - 18").
        m = re.match(
            r"^(.*?)\s+(\d+)(?::(\d+)(?:\s*[-–—]\s*(\d+))?)?$", ref, re.UNICODE)
        if not m:
            return None

        book = m.group(1).strip()
        chapter = int(m.group(2))
        verse_start = int(m.group(3)) if m.group(3) else None
        verse_end   = int(m.group(4)) if m.group(4) else None

        if not book:
            return None

        if book.lower() in ("psalm", "psalms") and 151 <= chapter <= 155:
            book = f"Psalm {chapter}"

        return book, chapter, verse_start, verse_end

    def _resolve_book(self, raw: str) -> tuple[Optional[str], Optional[str]]:
        """Return (corpus, canonical_book_name) or (None, None): the book by name or alias, else
        the closest name (so "1 Jhon" is 1 John -- see _guessed for when that's too far a guess)."""
        exact = self._resolve_exact(raw)
        return exact if exact[1] else self._resolve_fuzzy(raw)

    def _resolve_exact(self, raw: str) -> tuple[Optional[str], Optional[str]]:
        """(corpus, book) for a book's own name or one of its aliases; (None, None) otherwise."""
        key = raw.lower().strip()
        # Roman-numbered books ("I Kings", "II Corinthians", Sefaria's style); the Douay
        # "3 Kings" and "4 Kings" are the King James 1 and 2 Kings
        roman = re.match(r"^(iv|iii|ii|i)\s+(\S.*)$", key)
        if roman:                                       # (only for a book we know: not "I Ching")
            numbered = f"{['i', 'ii', 'iii', 'iv'].index(roman.group(1)) + 1} {roman.group(2)}"
            numbered = {"3 kings": "1 kings", "4 kings": "2 kings"}.get(numbered, numbered)
            if numbered in ALIASES or numbered in self._book_index:
                key = raw = numbered
        key = {"3 kings": "1 kings", "4 kings": "2 kings"}.get(key, key)
        # "First Samuel", "2nd Timothy"; "the Gospel of John", "the Gospel according to St Luke"
        key = re.sub(r"^(?:first|1st)\s+", "1 ", key)
        key = re.sub(r"^(?:second|2nd)\s+", "2 ", key)
        key = re.sub(r"^(?:third|3rd)\s+", "3 ", key)
        key = re.sub(r"^(?:the\s+)?gospel\s+(?:of|according\s+to)\s+(?:st\.?\s+|saint\s+)?(matthew|mark|luke|john)$",
                     r"\1", key)
        # 1. Direct alias lookup
        if key in ALIASES:
            canon = ALIASES[key]
            entry = self._book_index.get(canon.lower())
            if entry:
                return entry
        # 2. Direct name lookup (case-insensitive)
        entry = self._book_index.get(key)
        if entry:
            return entry
        # 3. With or without a leading "The" ("Great Catechism" is The Great Catechism)
        other = key[4:] if key.startswith("the ") else "the " + key
        entry = self._book_index.get(other) or (self._book_index.get(ALIASES[other].lower()) if other in ALIASES else None)
        if entry:
            return entry
        return None, None

    def _resolve_fuzzy(self, raw: str) -> tuple[Optional[str], Optional[str]]:
        """The book whose name is closest to `raw`, if any is close enough."""
        key = raw.lower().strip()
        # 3. Fuzzy match on alias values + book index keys
        candidates = list(ALIASES.values()) + [v[1] for v in self._book_index.values()]
        number = re.match(r"^(\d)\s", key)
        if number:                                      # a misspelt "1 Jhon" may become 1 John, never 3 John
            candidates = [c for c in candidates if c.startswith(number.group(1))]
        matches = get_close_matches(raw, candidates, n=1, cutoff=0.7)
        if matches:
            canon = matches[0]
            entry = self._book_index.get(canon.lower())
            if entry:
                return entry
        return None, None

    def _suggest_books(self, raw: str) -> list[str]:
        local_candidates = [v[1] for v in self._book_index.values() if v[1] not in HIDDEN_BOOKS]
        mishnah_candidates = [
            v.replace("Mishnah_", "").replace("_", " ")
            for v in MISHNAH_TRACTATES.values()
        ]
        talmud_candidates = list(TALMUD_TRACTATES.values())
        hadith_candidates = list(COLLECTION_DISPLAY.values())
        all_candidates = local_candidates + mishnah_candidates + talmud_candidates + hadith_candidates
        return get_close_matches(raw, all_candidates, n=3, cutoff=0.4)


# ── Douay-Rheims Bible ─────────────────────────────────────────────────────────

# Maps KJV canonical book names → DR book names where they differ
_KJV_TO_DR: dict[str, str] = {
    "Joshua":           "Josue",
    "1 Samuel":         "1 Kings",
    "2 Samuel":         "2 Kings",
    "1 Kings":          "3 Kings",
    "2 Kings":          "4 Kings",
    "1 Chronicles":     "1 Paralipomenon",
    "2 Chronicles":     "2 Paralipomenon",
    "Ezra":             "1 Esdras",
    "Nehemiah":         "2 Esdras",
    "Tobit":            "Tobias",
    "Song of Solomon":  "Canticles",
    "Song of Songs":    "Canticles",
    "Isaiah":           "Isaias",
    "Jeremiah":         "Jeremias",
    "Ezekiel":          "Ezechiel",
    "Hosea":            "Osee",
    "Obadiah":          "Abdias",
    "Jonah":            "Jonas",
    "Micah":            "Micheas",
    "Habakkuk":         "Habacuc",
    "Zephaniah":        "Sophonias",
    "Haggai":           "Aggeus",
    "Zechariah":        "Zacharias",
    "Malachi":          "Malachias",
    "1 Maccabees":      "1 Machabees",
    "2 Maccabees":      "2 Machabees",
    "Revelation":       "Apocalypse",
}

# DR-specific names users might type directly (e.g. "Josue 1:1 DRB")
_DR_USER_ALIASES: dict[str, str] = {
    "josue": "Josue",
    "1 paralipomenon": "1 Paralipomenon",
    "2 paralipomenon": "2 Paralipomenon",
    "paralipomenon": "1 Paralipomenon",
    "1 esdras": "1 Esdras",
    "2 esdras": "2 Esdras",
    "tobias": "Tobias",
    "canticles": "Canticles",
    "canticle of canticles": "Canticles",
    "isaias": "Isaias",
    "jeremias": "Jeremias",
    "ezechiel": "Ezechiel",
    "osee": "Osee",
    "abdias": "Abdias",
    "jonas": "Jonas",
    "micheas": "Micheas",
    "habacuc": "Habacuc",
    "sophonias": "Sophonias",
    "aggeus": "Aggeus",
    "zacharias": "Zacharias",
    "malachias": "Malachias",
    "1 machabees": "1 Machabees",
    "2 machabees": "2 Machabees",
    "apocalypse": "Apocalypse",
    "3 kings": "3 Kings",
    "4 kings": "4 Kings",
}

# DRB translation suffixes users can append to a reference
DRB_SUFFIXES = {"drb", "drv", "dr", "douay", "douay-rheims", "douay rheims"}

# Knox translation suffix — routes to local knox.json corpus
KNOX_SUFFIXES = {"knox", "knox bible", "rk", "ronald knox"}

_drb_data: Optional[dict] = None

# ── Bible section book lists (used by !verse Bible shortcuts) ─────────────────

BIBLE_OT = [
    "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua",
    "Judges","Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings",
    "1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther","Job",
    "Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah",
    "Jeremiah","Lamentations","Ezekiel","Daniel","Hosea","Joel",
    "Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah",
    "Haggai","Zechariah","Malachi",
]
BIBLE_NT = [
    "Matthew","Mark","Luke","John","Acts","Romans",
    "1 Corinthians","2 Corinthians","Galatians","Ephesians",
    "Philippians","Colossians","1 Thessalonians","2 Thessalonians",
    "1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James",
    "1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
]
BIBLE_APOCRYPHA = [
    "1 Esdras","2 Esdras","Tobit","Judith","Additions to Esther",
    "Wisdom of Solomon","Sirach","Baruch","Epistle of Jeremiah",
    "Song of the Three Children","Susanna","Bel and the Dragon",
    "Prayer of Manasseh","1 Maccabees","2 Maccabees",
]


def _load_drb() -> Optional[dict]:
    global _drb_data
    if _drb_data is None:
        path = Path(__file__).parent / "data" / "drb.json"
        if path.exists():
            _drb_data = json.loads(path.read_text(encoding="utf-8"))
    return _drb_data


def get_verse_drb(reference: str) -> dict:
    """
    Look up a verse in the Douay-Rheims Bible.
    Reference should already have the DRB suffix stripped.
    Accepts KJV book names and DR-specific names.
    Returns same dict format as ScriptureLookup.get_verse().
    """
    data = _load_drb()
    if data is None:
        return {"found": False, "error": "Douay-Rheims data not found (drb.json missing).", "suggestions": []}

    # Parse reference
    m = re.match(
        r"^((?:\d\s*)?[A-Za-z][A-Za-z\s&'\-]+?)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+))?$",
        reference.strip(), re.IGNORECASE
    )
    if not m:
        return {"found": False, "error": f"Could not parse reference: **{reference}**\nTry: `John 3:16 DRB`", "suggestions": []}

    book_raw = m.group(1).strip()
    chapter  = m.group(2)
    verse_s  = int(m.group(3))
    verse_e  = int(m.group(4)) if m.group(4) else verse_s

    # Resolve book name: check DR aliases first, then KJV→DR map, then direct match
    key = book_raw.lower()
    dr_book = _DR_USER_ALIASES.get(key)
    if dr_book is None:
        # Try KJV canonical name (title-cased)
        for kjv_name, drb_name in _KJV_TO_DR.items():
            if key == kjv_name.lower():
                dr_book = drb_name
                break
    if dr_book is None:
        # Try direct match against DR book names (e.g. "John", "Genesis")
        for drb_name in data.keys():
            if key == drb_name.lower():
                dr_book = drb_name
                break

    if dr_book is None:
        # Special case: KJV 1/2 Esdras are NOT in DR
        if key in ("1 esdras", "2 esdras") and "1 Esdras" not in data:
            return {"found": False,
                    "error": f"**1-2 Esdras** in the KJV Apocrypha are not present in the Douay-Rheims. "
                             f"DR uses **1 Esdras** = Ezra and **2 Esdras** = Nehemiah.",
                    "suggestions": ["1 Esdras DRB", "2 Esdras DRB"]}
        return {"found": False,
                "error": f"Book **{book_raw}** not found in the Douay-Rheims Bible.",
                "suggestions": []}

    chap_data = data.get(dr_book, {}).get(str(chapter))
    if chap_data is None:
        max_ch = max((int(k) for k in data[dr_book].keys()), default=0)
        return {"found": False,
                "error": f"**{dr_book}** has no chapter {chapter}. (Max: {max_ch})",
                "suggestions": []}

    # Collect verses
    texts = []
    for v in range(verse_s, verse_e + 1):
        t = chap_data.get(str(v))
        if t:
            # Strip italics markers (* used for supplied words in DR)
            t = t.replace("*", "")
            texts.append(t.strip())

    if not texts:
        max_v = max((int(k) for k in chap_data.keys()), default=0)
        return {"found": False,
                "error": f"**{dr_book} {chapter}** has no verse {verse_s}. (Max: {max_v})",
                "suggestions": []}

    ref_label = f"{dr_book} {chapter}:{verse_s}" + (f"–{verse_e}" if verse_e != verse_s else "")
    text = " ".join(texts)

    return {
        "found":     True,
        "reference": ref_label,
        "text":      text,
        "source":    "Douay-Rheims Bible (Challoner revision)",
        "book":      dr_book,
        "chapter":   int(chapter),
        "verse":     verse_s,
    }


# ── Knox Bible lookup ─────────────────────────────────────────────────────────
# Loaded on demand like DRB, not part of the main corpus.
# knox.json lives in data/kjv/ alongside kjv_canon.json.
# Build it by running: python build_knox.py

_knox_data: Optional[dict] = None

def _load_knox() -> Optional[dict]:
    """Load knox.json from data/kjv/. Returns book→chapter→verse dict or None."""
    global _knox_data
    if _knox_data is None:
        path = Path(__file__).parent / "data" / "kjv" / "knox.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            _knox_data = payload.get("books", {})
    return _knox_data


def get_verse_knox(reference: str) -> dict:
    """
    Look up a verse in the Knox Bible (local knox.json corpus).
    Reference should have the Knox suffix already stripped.
    Accepts standard KJV book names as well as Knox/Vulgate names
    (Josue, Tobias, Canticle, Machabees, Apocalypse, etc.).
    """
    data = _load_knox()
    if data is None:
        return {
            "found": False,
            "error": "Knox Bible data not found. Run `python build_knox.py` to build it.",
            "suggestions": [],
        }

    # Parse reference
    m = re.match(
        r"^((?:\d\s*)?[A-Za-z][A-Za-z\s&'\-]+?)\s+(\d+)(?::(\d+)(?:\s*[-–]\s*(\d+))?)?$",
        reference.strip(), re.IGNORECASE,
    )
    if not m:
        return {
            "found": False,
            "error": f"Could not parse: **{reference}**\nTry: `Tobit 1:1 Knox`",
            "suggestions": [],
        }

    book_raw = m.group(1).strip()
    chapter  = m.group(2)
    verse_s  = int(m.group(3)) if m.group(3) else None
    verse_e  = int(m.group(4)) if m.group(4) else verse_s

    # Resolve book name — Knox normalises Vulgate names to KJV names in build_knox.py,
    # but users may still type Knox/DRB-style names.
    _KNOX_NAME_MAP: dict[str, str] = {
        # Vulgate → KJV canonical (as stored in knox.json)
        "josue": "Joshua",
        "paralipomenon": "1 Chronicles",
        "1 paralipomenon": "1 Chronicles",
        "2 paralipomenon": "2 Chronicles",
        "tobias": "Tobit",
        "canticle": "Song of Solomon",
        "canticle of canticles": "Song of Solomon",
        "canticles": "Song of Solomon",
        "ecclesiasticus": "Sirach",
        "isaias": "Isaiah",
        "jeremias": "Jeremiah",
        "ezechiel": "Ezekiel",
        "osee": "Hosea",
        "abdias": "Obadiah",
        "jonas": "Jonah",
        "micheas": "Micah",
        "habacuc": "Habakkuk",
        "sophonias": "Zephaniah",
        "aggeus": "Haggai",
        "zacharias": "Zechariah",
        "malachias": "Malachi",
        "1 machabees": "1 Maccabees",
        "2 machabees": "2 Maccabees",
        "machabees": "1 Maccabees",
        "apocalypse": "Revelation",
        "3 kings": "1 Kings",
        "4 kings": "2 Kings",
        "1 kings": "1 Samuel",
        "2 kings": "2 Samuel",
        "1 esdras": "Ezra",
        "2 esdras": "Nehemiah",
        "wisdom": "Wisdom of Solomon",
    }

    key = book_raw.lower()
    canon_book = _KNOX_NAME_MAP.get(key)

    if canon_book is None:
        # Try direct match (case-insensitive) against loaded books
        for bname in data:
            if bname.lower() == key:
                canon_book = bname
                break

    if canon_book is None or canon_book not in data:
        # Fuzzy fallback
        from difflib import get_close_matches
        matches = get_close_matches(book_raw, list(data.keys()), n=1, cutoff=0.6)
        if matches:
            canon_book = matches[0]
        else:
            return {
                "found": False,
                "error": f"**{book_raw}** not found in the Knox Bible.",
                "suggestions": list(data.keys())[:5],
            }

    book_data = data[canon_book]
    chap_data = book_data.get(str(chapter))
    if chap_data is None:
        max_ch = max((int(k) for k in book_data), default=0)
        return {
            "found": False,
            "error": f"**{canon_book}** has no chapter {chapter}. (Max: {max_ch})",
            "suggestions": [],
        }

    # Whole chapter
    if verse_s is None:
        sorted_vs = sorted(chap_data.keys(), key=lambda x: int(x))
        texts = [f"**[{v}]** {chap_data[v]}" for v in sorted_vs]
        PAGE = 15
        pages = ["\n".join(texts[i:i+PAGE]) for i in range(0, len(texts), PAGE)]
        return {
            "found": True,
            "reference": f"{canon_book} {chapter} (Knox)",
            "text": "\n".join(texts),
            "source": "trans. Ronald Knox (1945–49)",
            "pages": pages if len(pages) > 1 else None,
        }

    # Specific verse(s)
    texts = []
    for v in range(verse_s, verse_e + 1):
        t = chap_data.get(str(v))
        if t:
            texts.append(f"**[{v}]** {t}" if verse_e != verse_s else t)

    if not texts:
        max_v = max((int(k) for k in chap_data), default=0)
        return {
            "found": False,
            "error": f"**{canon_book} {chapter}** has no verse {verse_s}. (Max: {max_v})",
            "suggestions": [],
        }

    v_label = str(verse_s) if verse_s == verse_e else f"{verse_s}–{verse_e}"
    return {
        "found": True,
        "reference": f"{canon_book} {chapter}:{v_label} (Knox)",
        "text": "\n".join(texts),
        "source": "trans. Ronald Knox (1945–49)",
        "book": canon_book,
        "chapter": int(chapter),
        "verse": verse_s,
    }
