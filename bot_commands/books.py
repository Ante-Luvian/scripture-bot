"""
!books hierarchical browser (with its per-corpus chapter tables) and !export.
"""
import asyncio
import discord
import io
import re
from hadith_lookup import get_hadith_section
from scripture_lookup import ScriptureLookup
from core import (
    _HADITH_DISPLAY_TO_KEY,
    guild_traditions,
    tradition_enabled,
    _make_chapter_nav_buttons,
    _send_result,
    bot,
    fetch_chapter_result,
    lookup,
)

# ── !books — Hierarchical scripture browser ────────────────────────────────────

BOOKS_TREE = [
    ("📖 The Bible", [
        ("Old Testament", [
            "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua",
            "Judges","Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings",
            "1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther","Job",
            "Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah",
            "Jeremiah","Lamentations","Ezekiel","Daniel","Hosea","Joel",
            "Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah",
            "Haggai","Zechariah","Malachi",
        ]),
        ("New Testament", [
            "Matthew","Mark","Luke","John","Acts","Romans",
            "1 Corinthians","2 Corinthians","Galatians","Ephesians",
            "Philippians","Colossians","1 Thessalonians","2 Thessalonians",
            "1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James",
            "1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
        ]),
    ]),
    ("👼 Apocrypha / Pseudepigrapha", [
        ("Apocrypha (KJV)", [
            "1 Esdras","2 Esdras","Tobit","Judith","Additions to Esther",
            "Wisdom of Solomon","Sirach","Baruch","Epistle of Jeremiah",
            "Song of the Three Children","Susanna","Bel and the Dragon",
            "Prayer of Manasseh","1 Maccabees","2 Maccabees",
        ]),
        ("Pseudepigrapha", [
            "3 Maccabees","4 Maccabees","Psalms of Solomon",
            "Psalm 151","Psalm 152","Psalm 153","Psalm 154","Psalm 155",
            "Book of Enoch","Book of Jubilees",
            "Testament of Reuben","Testament of Simeon","Testament of Levi",
            "Testament of Judah","Testament of Issachar","Testament of Zebulun",
            "Testament of Dan","Testament of Naphtali","Testament of Gad",
            "Testament of Asher","Testament of Joseph","Testament of Benjamin",
            "Assumption of Moses","Ascension of Isaiah","Sibylline Oracles",
            "Letter of Aristeas","Vita Adae et Evae","Apocalypse of Moses",
            "Fragments of a Zadokite Work",
            "2 Enoch",
            "First Book of Adam and Eve", "Second Book of Adam and Eve", "Odes of Solomon",
        ]),
        ("New Testament Apocrypha (Ante-Nicene Fathers VIII)", [
            ("Infancy Gospels", [
                "The Protevangelium of James", "The Gospel of Pseudo-Matthew",
                "The Gospel of the Nativity of Mary", "The History of Joseph the Carpenter",
                "Gospel of Thomas: First Greek Form", "Gospel of Thomas: Second Greek Form",
                "Gospel of Thomas: Latin Form", "The Arabic Gospel of the Infancy of the Saviour",
            ]),
            ("Pilate & the Descent into Hell (Gospel of Nicodemus)", [
                "Acts of Pilate: First Greek Form", "Acts of Pilate: Second Greek Form",
                "Acts of Pilate: Latin Form", "Descent of Christ into Hell: Greek Form",
                "Christ's Descent into Hell: Latin. First Version",
                "Christ's Descent into Hell: Latin. Second Version",
                "Letter of Pontius Pilate", "Report of Pilate: First Greek Form",
                "Report of Pilate: Second Greek Form", "The Giving Up of Pontius Pilate",
                "The Death of Pilate, Who Condemned Jesus", "The Narrative of Joseph",
                "The Avenging of the Saviour",
            ]),
            ("Acts of the Apostles", [
                "Acts of the Holy Apostles Peter and Paul", "Acts of Paul and Thecla",
                "The Acts of Barnabas", "The Acts of Philip",
                "Acts and Martyrdom of the Holy Apostle Andrew", "Acts of Andrew and Matthias",
                "Acts of Peter and Andrew", "Acts and Martyrdom of St. Matthew the Apostle",
                "Various Acts of Thomas", "Consummation of Thomas the Apostle",
                "Martyrdom of the Holy and Glorious Apostle Bartholomew",
                "Acts of the Holy Apostle Thaddaeus",
                "Acts of the Holy Apostle and Evangelist John the Theologian",
            ]),
            ("Revelations & the Passing of Mary", [
                "Revelation of Moses", "Revelation of Esdras", "Revelation of Paul", "Revelation of John",
                "The Book of John Concerning the Falling Asleep of Mary",
                "The Passing of Mary: First Latin Form", "The Passing of Mary: Second Latin Form",
            ]),
        ]),
    ]),
    ("✡️ Rabbinic & Kabbalistic", [
        ("Mishnah", [
            ("Seder Zeraim (Agriculture)", [
                "Berakhot","Peah","Demai","Kilayim","Sheviit",
                "Terumot","Maasrot","Maaser Sheni","Challah","Orlah","Bikkurim",
            ]),
            ("Seder Moed (Festivals)", [
                "Shabbat","Eruvin","Pesachim","Shekalim","Yoma","Sukkah",
                "Beitzah","Rosh Hashanah","Taanit","Megillah","Moed Katan","Chagigah",
            ]),
            ("Seder Nashim (Women)", [
                "Yevamot","Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin",
            ]),
            ("Seder Nezikin (Damages)", [
                "Bava Kamma","Bava Metzia","Bava Batra","Sanhedrin","Makkot",
                "Shevuot","Eduyot","Avodah Zarah","Avot","Horayot",
            ]),
            ("Seder Kodashim (Temple)", [
                "Zevachim","Menachot","Chullin","Bechorot","Arachin",
                "Temurah","Keritot","Meilah","Tamid","Middot","Kinnim",
            ]),
            ("Seder Taharot (Purity)", [
                "Keilim","Ohalot","Negaim","Parah","Taharot","Mikvaot",
                "Niddah","Machshirin","Zavim","Tevul Yom","Yadayim","Oktzin",
            ]),
        ]),
        ("Tosefta", [
            ("Seder Zeraim", [
                "Tosefta Berakhot","Tosefta Peah","Tosefta Demai","Tosefta Kilayim",
                "Tosefta Sheviit","Tosefta Terumot","Tosefta Maasrot",
                "Tosefta Maaser Sheni","Tosefta Challah","Tosefta Orlah","Tosefta Bikkurim",
            ]),
            ("Seder Moed", [
                "Tosefta Shabbat","Tosefta Eruvin","Tosefta Pesachim","Tosefta Shekalim",
                "Tosefta Yoma","Tosefta Sukkah","Tosefta Beitzah",
                "Tosefta Rosh Hashanah","Tosefta Taanit","Tosefta Megillah",
                "Tosefta Moed Katan","Tosefta Chagigah",
            ]),
            ("Seder Nashim", [
                "Tosefta Yevamot","Tosefta Ketubot","Tosefta Nedarim","Tosefta Nazir",
                "Tosefta Sotah","Tosefta Gittin","Tosefta Kiddushin",
            ]),
            ("Seder Nezikin", [
                "Tosefta Bava Kamma","Tosefta Bava Metzia","Tosefta Bava Batra",
                "Tosefta Sanhedrin","Tosefta Makkot","Tosefta Shevuot",
                "Tosefta Eduyot","Tosefta Avodah Zarah","Tosefta Horayot",
            ]),
        ]),
        ("Babylonian Talmud", [
            ("Seder Zeraim", ["Berakhot"]),
            ("Seder Moed", [
                "Shabbat","Eruvin","Pesachim","Shekalim","Yoma","Sukkah",
                "Beitzah","Rosh Hashanah","Taanit","Megillah","Moed Katan","Chagigah",
            ]),
            ("Seder Nashim", [
                "Yevamot","Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin",
            ]),
            ("Seder Nezikin", [
                "Bava Kamma","Bava Metzia","Bava Batra","Sanhedrin","Makkot",
                "Shevuot","Avodah Zarah","Horayot",
            ]),
            ("Seder Kodashim", [
                "Zevachim","Menachot","Chullin","Bechorot","Arachin",
                "Temurah","Keritot","Meilah","Tamid","Niddah",
            ]),
        ]),
        ("Jerusalem Talmud", [
            ("Seder Zeraim", [
                "Jerusalem Talmud Berakhot","Jerusalem Talmud Peah",
                "Jerusalem Talmud Demai","Jerusalem Talmud Kilayim",
                "Jerusalem Talmud Sheviit","Jerusalem Talmud Terumot",
                "Jerusalem Talmud Maaserot","Jerusalem Talmud Maaser Sheni",
                "Jerusalem Talmud Challah","Jerusalem Talmud Orlah",
                "Jerusalem Talmud Bikkurim",
            ]),
            ("Seder Moed", [
                "Jerusalem Talmud Shabbat","Jerusalem Talmud Eruvin",
                "Jerusalem Talmud Pesachim","Jerusalem Talmud Shekalim",
                "Jerusalem Talmud Yoma","Jerusalem Talmud Sukkah",
                "Jerusalem Talmud Beitzah","Jerusalem Talmud Rosh Hashanah",
                "Jerusalem Talmud Taanit","Jerusalem Talmud Megillah",
                "Jerusalem Talmud Moed Katan","Jerusalem Talmud Chagigah",
            ]),
            ("Seder Nashim", [
                "Jerusalem Talmud Yevamot","Jerusalem Talmud Ketubot",
                "Jerusalem Talmud Nedarim","Jerusalem Talmud Nazir",
                "Jerusalem Talmud Sotah","Jerusalem Talmud Gittin",
                "Jerusalem Talmud Kiddushin",
            ]),
            ("Seder Nezikin", [
                "Jerusalem Talmud Bava Kamma","Jerusalem Talmud Bava Metzia",
                "Jerusalem Talmud Bava Batra","Jerusalem Talmud Sanhedrin",
                "Jerusalem Talmud Makkot","Jerusalem Talmud Shevuot",
                "Jerusalem Talmud Avodah Zarah","Jerusalem Talmud Horayot",
                "Jerusalem Talmud Niddah",
            ]),
        ]),
        ("Targumim", [
            ("Torah Targumim", [
                "Targum Onkelos Genesis","Targum Onkelos Exodus",
                "Targum Onkelos Leviticus","Targum Onkelos Numbers",
                "Targum Onkelos Deuteronomy",
                "Targum Pseudo-Jonathan Genesis","Targum Pseudo-Jonathan Exodus",
                "Targum Neofiti Genesis","Targum Neofiti Exodus",
            ]),
            ("Prophets & Writings", [
                "Targum Jonathan Isaiah","Targum Jonathan Jeremiah",
                "Targum Jonathan Ezekiel","Targum Jonathan Hosea",
                "Targum Jonathan Psalms","Targum Jonathan Proverbs",
                "Targum Jonathan Job",
            ]),
        ]),
        ("Midrash", [
            ("Midrash Rabbah", [
                "Bereshit Rabbah","Shemot Rabbah","Vayikra Rabbah",
                "Bamidbar Rabbah","Devarim Rabbah","Ruth Rabbah",
                "Esther Rabbah","Eichah Rabbah","Shir HaShirim Rabbah",
                "Kohelet Rabbah",
            ]),
            ("Halachic Midrash", [
                "Mechilta","Sifra","Sifre Bamidbar","Sifre Devarim",
            ]),
            ("Aggadic Midrash", [
                "Pirkei DeRabbi Eliezer","Midrash Tanchuma",
            ]),
        ]),
        ("Maimonides", [
            ("Mishneh Torah — Book 1: HaMadda", [
                "Mishneh Torah, Foundations of the Torah",
                "Mishneh Torah, Human Dispositions",
                "Mishneh Torah, Torah Study",
                "Mishneh Torah, Foreign Worship and Customs of the Nations",
                "Mishneh Torah, Repentance",
            ]),
            ("Mishneh Torah — Book 2: Ahavah", [
                "Mishneh Torah, Reading the Shema",
                "Mishneh Torah, Prayer and the Priestly Blessing",
                "Mishneh Torah, Tefillin, Mezuzah and the Torah Scroll",
                "Mishneh Torah, Fringes",
                "Mishneh Torah, Blessings",
                "Mishneh Torah, Circumcision",
                "Mishneh Torah, The Order of Prayer",
            ]),
            ("Mishneh Torah — Book 3: Zemanim", [
                "Mishneh Torah, Sabbath",
                "Mishneh Torah, Eruvin",
                "Mishneh Torah, Rest on the Tenth of Tishrei",
                "Mishneh Torah, Rest on a Holiday",
                "Mishneh Torah, Leavened and Unleavened Bread",
                "Mishneh Torah, Shofar, Sukkah and Lulav",
                "Mishneh Torah, Sheqel Dues",
                "Mishneh Torah, Sanctification of the New Month",
                "Mishneh Torah, Fasts",
                "Mishneh Torah, Megillah and Hanukkah",
            ]),
            ("Mishneh Torah — Book 4–5: Nashim & Kedushah", [
                "Mishneh Torah, Marriage",
                "Mishneh Torah, Divorce",
                "Mishneh Torah, Levirate Marriage and Release",
                "Mishneh Torah, Virgin Maiden",
                "Mishneh Torah, Sotah",
                "Mishneh Torah, Forbidden Intercourse",
                "Mishneh Torah, Forbidden Foods",
                "Mishneh Torah, Slaughter",
            ]),
            ("Mishneh Torah — Books 6–7: Haflaah & Zeraim", [
                "Mishneh Torah, Oaths",
                "Mishneh Torah, Vows",
                "Mishneh Torah, Naziriteship",
                "Mishneh Torah, Appraisals and Devoted Property",
                "Mishneh Torah, Diverse Species",
                "Mishneh Torah, Gifts to the Poor",
                "Mishneh Torah, Heave Offerings",
                "Mishneh Torah, Tithes",
                "Mishneh Torah, Second Tithe and Fourth Year Produce",
                "Mishneh Torah, First Fruits and other Gifts to Priests Outside the Temple",
                "Mishneh Torah, Sabbatical Year and the Jubilee",
            ]),
            ("Mishneh Torah — Books 8–10: Temple, Offerings & Purity", [
                "Mishneh Torah, The Chosen Temple",
                "Mishneh Torah, Vessels of the Sanctuary and Those who Serve Therein",
                "Mishneh Torah, Admission into the Sanctuary",
                "Mishneh Torah, Sacrificial Procedure",
                "Mishneh Torah, Daily Offerings and Additional Offerings",
                "Mishneh Torah, The Yom Kippur Service",
                "Mishneh Torah, Paschal Offering",
                "Mishneh Torah, Festival Offering",
                "Mishneh Torah, Firstborn",
                "Mishneh Torah, Corpse Impurity",
                "Mishneh Torah, Red Heifer",
                "Mishneh Torah, Leprosy",
                "Mishneh Torah, Immersion Pools",
            ]),
            ("Mishneh Torah — Books 11–14: Civil & Judicial", [
                "Mishneh Torah, Property Damage",
                "Mishneh Torah, Theft",
                "Mishneh Torah, Robbery and Lost Property",
                "Mishneh Torah, Murderers and the Preservation of Life",
                "Mishneh Torah, Sales",
                "Mishneh Torah, Neighbors",
                "Mishneh Torah, Agents and Partners",
                "Mishneh Torah, Hiring",
                "Mishneh Torah, Creditor and Debtor",
                "Mishneh Torah, Inheritance",
                "Mishneh Torah, Courts",
                "Mishneh Torah, Testimony",
                "Mishneh Torah, Mourning",
                "Mishneh Torah, Kings and Wars",
            ]),
            ("Other Works", [
                "Guide for the Perplexed",
                "Mishnah Torah",
            ]),
        ]),
        ("Kabbalah", [
            ("Zohar", [
                "Zohar Introduction",
                "Zohar Bereshit","Zohar Noach","Zohar Lech Lecha",
                "Zohar Vayera","Zohar Chayei Sarah","Zohar Toldot",
                "Zohar Vayetze","Zohar Vayishlach","Zohar Vayeshev",
                "Zohar Miketz","Zohar Vayigash","Zohar Vayechi",
                "Zohar Shemot","Zohar Vaera","Zohar Bo",
                "Zohar Beshalach","Zohar Yitro","Zohar Mishpatim",
                "Zohar Terumah","Zohar Tetzaveh","Zohar Ki Tisa",
                "Zohar Vayakhel","Zohar Pekudei","Zohar Vayikra",
                "Zohar Tzav","Zohar Shmini","Zohar Tazria",
                "Zohar Metzora","Zohar Acharei Mot","Zohar Kedoshim",
                "Zohar Emor","Zohar Behar","Zohar Bechukotai",
                "Zohar Bamidbar","Zohar Nasso","Zohar Behaalotcha",
                "Zohar Shelach Lecha","Zohar Korach","Zohar Chukat",
                "Zohar Balak","Zohar Pinchas","Zohar Matot",
                "Zohar Vaetchanan","Zohar Eikev","Zohar Re'eh",
                "Zohar Shoftim","Zohar Ki Teitzei","Zohar Ki Tavo",
                "Zohar Vayeilech","Zohar Haazinu","Zohar Vezot Haberachah",
            ]),
            ("Other Kabbalah", [
                "Sefer Yetzirah",
                "Sefer HaBahir",
                "Tikkunei Zohar",
                "Zohar Chadash",
                "Tanya",
            ]),
        ]),
    ]),
    ("☪️ Islamic", [
        ("Quran", [
            ("Juz 1–2: Al-Faatiha through Al-Baqara", [
                "Quran 1 — Al-Faatiha (The Opening, 7v)",
                "Quran 2 — Al-Baqara (The Cow, 286v)",
            ]),
            ("Juz 3–5: Aali Imran through An-Nisaa", [
                "Quran 3 — Aali Imran (Family of Imran, 200v)",
                "Quran 4 — An-Nisaa (The Women, 176v)",
            ]),
            ("Juz 6–7: Al-Maaida through Al-Araaf", [
                "Quran 5 — Al-Maaida (The Table, 120v)",
                "Quran 6 — Al-Anaam (The Cattle, 165v)",
                "Quran 7 — Al-Araaf (The Heights, 206v)",
            ]),
            ("Juz 8–10: Al-Anfaal through Yunus", [
                "Quran 8 — Al-Anfaal (The Spoils of War, 75v)",
                "Quran 9 — At-Tawba (The Repentance, 129v)",
                "Quran 10 — Yunus (Jonah, 109v)",
            ]),
            ("Juz 11–13: Hud through Ar-Rad", [
                "Quran 11 — Hud (Hud, 123v)",
                "Quran 12 — Yusuf (Joseph, 111v)",
                "Quran 13 — Ar-Rad (The Thunder, 43v)",
                "Quran 14 — Ibrahim (Abraham, 52v)",
                "Quran 15 — Al-Hijr (The Rocky Tract, 99v)",
            ]),
            ("Juz 14–16: An-Nahl through Taa-Haa", [
                "Quran 16 — An-Nahl (The Bee, 128v)",
                "Quran 17 — Al-Israa (The Night Journey, 111v)",
                "Quran 18 — Al-Kahf (The Cave, 110v)",
                "Quran 19 — Maryam (Mary, 98v)",
                "Quran 20 — Taa-Haa (Ta-Ha, 135v)",
            ]),
            ("Juz 17–20: Al-Anbiyaa through An-Naml", [
                "Quran 21 — Al-Anbiyaa (The Prophets, 112v)",
                "Quran 22 — Al-Hajj (The Pilgrimage, 78v)",
                "Quran 23 — Al-Muminoon (The Believers, 118v)",
                "Quran 24 — An-Noor (The Light, 64v)",
                "Quran 25 — Al-Furqaan (The Criterion, 77v)",
                "Quran 26 — Ash-Shuaraa (The Poets, 227v)",
                "Quran 27 — An-Naml (The Ant, 93v)",
            ]),
            ("Juz 20–23: Al-Qasas through Al-Ahzaab", [
                "Quran 28 — Al-Qasas (The Stories, 88v)",
                "Quran 29 — Al-Ankaboot (The Spider, 69v)",
                "Quran 30 — Ar-Room (The Romans, 60v)",
                "Quran 31 — Luqman (Luqman, 34v)",
                "Quran 32 — As-Sajda (The Prostration, 30v)",
                "Quran 33 — Al-Ahzaab (The Clans, 73v)",
            ]),
            ("Juz 22–26: Saba through Az-Zumar", [
                "Quran 34 — Saba (Sheba, 54v)",
                "Quran 35 — Faatir (The Originator, 45v)",
                "Quran 36 — Yaseen (Ya-Seen, 83v)",
                "Quran 37 — As-Saaffaat (Those Ranged in Ranks, 182v)",
                "Quran 38 — Saad (The Letter Sad, 88v)",
                "Quran 39 — Az-Zumar (The Groups, 75v)",
            ]),
            ("Juz 24–28: Ghafir through Al-Fath", [
                "Quran 40 — Ghafir (The Forgiver, 85v)",
                "Quran 41 — Fussilat (Explained in Detail, 54v)",
                "Quran 42 — Ash-Shura (The Consultation, 53v)",
                "Quran 43 — Az-Zukhruf (The Gold Adornments, 89v)",
                "Quran 44 — Ad-Dukhaan (The Smoke, 59v)",
                "Quran 45 — Al-Jaathiya (The Kneeling, 37v)",
                "Quran 46 — Al-Ahqaf (The Wind-Curved Sandhills, 35v)",
                "Quran 47 — Muhammad (Muhammad, 38v)",
                "Quran 48 — Al-Fath (The Victory, 29v)",
            ]),
            ("Juz 26–29: Al-Hujuraat through Al-Mulk", [
                "Quran 49 — Al-Hujuraat (The Rooms, 18v)",
                "Quran 50 — Qaaf (The Letter Qaf, 45v)",
                "Quran 51 — Adh-Dhaariyat (The Winnowing Winds, 60v)",
                "Quran 52 — At-Toor (The Mount, 49v)",
                "Quran 53 — An-Najm (The Star, 62v)",
                "Quran 54 — Al-Qamar (The Moon, 55v)",
                "Quran 55 — Ar-Rahmaan (The Beneficent, 78v)",
                "Quran 56 — Al-Waaqia (The Inevitable, 96v)",
                "Quran 57 — Al-Hadid (The Iron, 29v)",
                "Quran 58 — Al-Mujaadila (The Pleading Woman, 22v)",
                "Quran 59 — Al-Hashr (The Exile, 24v)",
                "Quran 60 — Al-Mumtahana (She That is Examined, 13v)",
                "Quran 61 — As-Saff (The Ranks, 14v)",
                "Quran 62 — Al-Jumu'a (The Congregation, 11v)",
                "Quran 63 — Al-Munafiqoon (The Hypocrites, 11v)",
                "Quran 64 — At-Taghaabun (The Mutual Disillusion, 18v)",
                "Quran 65 — At-Talaaq (The Divorce, 12v)",
                "Quran 66 — At-Tahrim (The Prohibition, 12v)",
                "Quran 67 — Al-Mulk (The Sovereignty, 30v)",
            ]),
            ("Juz 29–30: Al-Qalam through An-Naas", [
                "Quran 68 — Al-Qalam (The Pen, 52v)",
                "Quran 69 — Al-Haaqqa (The Reality, 52v)",
                "Quran 70 — Al-Maarij (The Ascending Stairways, 44v)",
                "Quran 71 — Nooh (Noah, 28v)",
                "Quran 72 — Al-Jinn (The Jinn, 28v)",
                "Quran 73 — Al-Muzzammil (The Enshrouded One, 20v)",
                "Quran 74 — Al-Muddaththir (The Cloaked One, 56v)",
                "Quran 75 — Al-Qiyaama (The Resurrection, 40v)",
                "Quran 76 — Al-Insaan (The Man, 31v)",
                "Quran 77 — Al-Mursalaat (The Emissaries, 50v)",
                "Quran 78 — An-Naba (The Tidings, 40v)",
                "Quran 79 — An-Naaziat (Those who Drag Forth, 46v)",
                "Quran 80 — Abasa (He Frowned, 42v)",
                "Quran 81 — At-Takwir (The Overthrowing, 29v)",
                "Quran 82 — Al-Infitar (The Cleaving, 19v)",
                "Quran 83 — Al-Mutaffifin (The Defrauding, 36v)",
                "Quran 84 — Al-Inshiqaaq (The Splitting Open, 25v)",
                "Quran 85 — Al-Burooj (The Mansions of the Stars, 22v)",
                "Quran 86 — At-Taariq (The Morning Star, 17v)",
                "Quran 87 — Al-Ala (The Most High, 19v)",
                "Quran 88 — Al-Ghaashiya (The Overwhelming, 26v)",
                "Quran 89 — Al-Fajr (The Dawn, 30v)",
                "Quran 90 — Al-Balad (The City, 20v)",
                "Quran 91 — Ash-Shams (The Sun, 15v)",
                "Quran 92 — Al-Layl (The Night, 21v)",
                "Quran 93 — Ad-Duhaa (The Morning Hours, 11v)",
                "Quran 94 — Ash-Sharh (The Relief, 8v)",
                "Quran 95 — At-Tin (The Fig, 8v)",
                "Quran 96 — Al-Alaq (The Clot, 19v)",
                "Quran 97 — Al-Qadr (The Power, 5v)",
                "Quran 98 — Al-Bayyina (The Clear Proof, 8v)",
                "Quran 99 — Az-Zalzala (The Earthquake, 8v)",
                "Quran 100 — Al-Aadiyaat (The Courser, 11v)",
                "Quran 101 — Al-Qaaria (The Calamity, 11v)",
                "Quran 102 — At-Takaathur (The Rivalry, 8v)",
                "Quran 103 — Al-Asr (The Declining Day, 3v)",
                "Quran 104 — Al-Humaza (The Traducer, 9v)",
                "Quran 105 — Al-Fil (The Elephant, 5v)",
                "Quran 106 — Quraysh (Quraysh, 4v)",
                "Quran 107 — Al-Maaun (The Small Kindnesses, 7v)",
                "Quran 108 — Al-Kawthar (The Abundance, 3v)",
                "Quran 109 — Al-Kaafiroon (The Disbelievers, 6v)",
                "Quran 110 — An-Nasr (The Divine Support, 3v)",
                "Quran 111 — Al-Masad (The Palm Fibre, 5v)",
                "Quran 112 — Al-Ikhlaas (The Sincerity, 4v)",
                "Quran 113 — Al-Falaq (The Daybreak, 5v)",
                "Quran 114 — An-Naas (Mankind, 6v)",
            ]),
        ]),
        ("Sufi & Persian Poetry", [
            "Divan of Hafiz",
            "Masnavi",
            "Rubaiyat",
        ]),
        ("Hadith", [
            ("The Six Books (Kutub al-Sittah)", [
                "Sahih al-Bukhari",
                "Sahih Muslim",
                "Sunan Abu Dawud",
                "Jami at-Tirmidhi",
                "Sunan an-Nasa'i",
                "Sunan Ibn Majah",
            ]),
            ("Other Collections", [
                "Muwatta Malik",
                "Forty Hadith of Nawawi",
                "Forty Hadith of Dehlawi",
                "Forty Hadith Qudsi",
            ]),
        ]),
    ]),
    ("🏛️ Classical", [
        ("Epic Poetry", [
            ("Homer", ["Iliad", "Odyssey"]),
            ("Virgil", ["Aeneid"]),
        ]),
        ("Theogonies & Hymns", [
            ("Hesiod", ["Theogony", "Works and Days", "Shield of Heracles"]),
            ("Homeric", ["Homeric Hymns"]),
            ("Orphic", ["Orphic Hymns"]),
            ("Pythagorean", ["Golden Verses of Pythagoras"]),
        ]),
        ("Platonic & Neoplatonic", [
            ("Orphic", ["Orphic Hymns"]),
            ("Pythagorean", [
                "Golden Verses of Pythagoras",
                "Golden Sentences of Democrates",
                "Pythagorean Sentences of Demophilus",
                "Similitudes of Demophilus",
                "Pythagorean Sentences from Stobaeus",
                "Select Sentences of Sextus the Pythagorean",
                "Pythagorean Sentences from Iamblichus",
                "Symbols of Pythagoras",
            ]),
            ("Plato", [
                "Euthyphro", "Apology", "Crito", "Phaedo", "Cratylus",
                "Theaetetus", "Sophist", "Statesman", "Parmenides", "Philebus",
                "Symposium", "Phaedrus", "Alcibiades I", "Alcibiades II",
                "Hipparchus", "Rival Lovers", "Theages", "Charmides", "Laches",
                "Lysis", "Euthydemus", "Protagoras", "Gorgias", "Meno",
                "Greater Hippias", "Lesser Hippias", "Ion", "Menexenus",
                "Cleitophon", "Republic", "Timaeus", "Critias", "Minos",
                "Laws", "Epinomis", "Letters",
                "Axiochus", "Eryxias",
            ]),
            ("Philo of Alexandria", [
                "On the Creation",
                "Allegorical Interpretation I",
                "Allegorical Interpretation II",
                "Allegorical Interpretation III",
                "On the Cherubim",
                "On the Birth of Abel",
                "Worse Attacks the Better",
                "On the Posterity of Cain",
                "On the Giants",
                "On the Unchangeableness of God",
                "On Husbandry",
                "On Noah's Work as a Planter",
                "On Drunkenness",
                "On Sobriety",
                "On the Confusion of Tongues",
                "On the Migration of Abraham",
                "Who is the Heir of Divine Things",
                "On Mating",
                "On Flight and Finding",
                "On the Change of Names",
                "On Abraham",
                "On Joseph",
                "On the Life of Moses I",
                "On the Life of Moses II",
                "The Decalogue",
                "The Special Laws I",
                "The Special Laws II",
                "The Special Laws III",
                "The Special Laws IV",
                "On the Virtues",
                "On Rewards and Punishments",
                "Every Good Man is Free",
                "On the Contemplative Life",
                "On the Eternity of the World",
                "Flaccus",
                "On the Embassy to Gaius",
                "Questions on Genesis I",
                "Questions on Genesis II",
                "Questions on Genesis III",
            ]),
            ("Plotinus", ["Enneads"]),
            ("Porphyry", [
                "Life of Plotinus",
                "Life of Pythagoras",
                "On Abstinence",
                "On the Cave of the Nymphs",
                "Auxiliaries to the Intelligibles",
                "Letter to Marcella",
            ]),
            ("Iamblichus", [
                "On the Mysteries",
                "Life of Pythagoras",
            ]),
            ("Julian", [
                "Hymn to King Helios",
                "Hymn to the Mother of Gods",
                "Against the Galilaeans",
                "The Caesars",
            ]),
            ("Sallustius", ["On the Gods and the World"]),
            ("Proclus", [
                "Hymns of Proclus",
                "Theology of Plato",
                "Elements of Theology",
            ]),
            ("Hierocles", ["Commentary on the Golden Verses"]),
            ("Marinus", ["Life of Proclus"]),
            ("Dionysius the Areopagite", [
                "Divine Names",
                "Mystical Theology",
                "On the Heavenly Hierarchy",
                "On the Ecclesiastical Hierarchy",
            ]),
        ]),
        ("Aristotelian", [
            ("Ethics & Politics", [
                "Nicomachean Ethics",
                "Eudemian Ethics",
                "Politics",
                "Economics",
                "Athenian Constitution",
            ]),
            ("Logic (Organon)", [
                "Categories",
                "On Interpretation",
                "Prior Analytics",
                "Posterior Analytics",
                "Topics",
                "On Sophistical Refutations",
            ]),
            ("Natural Philosophy", [
                "Physics",
                "On the Heavens",
                "On Generation and Corruption",
                "Meteorology",
                "On the Soul",
                "On Memory and Reminiscence",
                "On Dreams",
                "On Sleep and Sleeplessness",
                "On Prophesying by Dreams",
                "On Sense and the Sensible",
                "On Longevity and Shortness of Life",
                "On Youth, Old Age, Life and Death",
            ]),
            ("Biology", [
                "History of Animals",
                "On the Parts of Animals",
                "On the Motion of Animals",
                "On the Gait of Animals",
                "On the Generation of Animals",
            ]),
            ("Rhetoric & Poetics", [
                "Rhetoric",
                "Poetics",
                "Metaphysics",
            ]),
        ]),
        ("Stoic", [
            ("Marcus Aurelius", ["Meditations"]),
            ("Epictetus", ["Enchiridion of Epictetus"]),
        ]),
        ("Hermetic", [
            "Corpus Hermeticum",
            "Asclepius",
        ]),
        ("Oracular", [
            "Delphic Maxims",
            "Oracular Statements",
            "Chaldaean Oracles",
        ]),
    ]),
    ("📯 LDS", [
        ("Book of Mormon", [
            "1 Nephi","2 Nephi","Jacob","Enos","Jarom","Omni",
            "Words of Mormon","Mosiah","Alma","Helaman","3 Nephi","4 Nephi",
            "Mormon","Ether","Moroni",
        ]),
        ("Doctrine & Covenants", [
            "Doctrine and Covenants",
        ]),
        ("Pearl of Great Price", [
            "Moses","Abraham","Joseph Smith—Matthew","Joseph Smith—History",
            "Articles of Faith",
        ]),
    ]),
    ("🌍 Bahá'í", [
        "Kitab-i-Aqdas",
        "The Hidden Words (Arabic)",
        "The Hidden Words (Persian)",
        "Gleanings from the Writings of Baha'u'llah",
        "Prayers and Meditations",
        "Some Answered Questions",
        "Kitab-i-Iqan",
        "Epistle to the Son of the Wolf",
    ]),
    ("🏺 Dead Sea Scrolls", [
        "Hodayot",
        "Damascus Document",
        "Community Rule",
        "War Scroll",
        "Pesher Habakkuk",
        "Rule of the Congregation",
        "Rule of Blessings",
        "Isaiah (1QIsaa)",
        "Exodus (4Q22)",
        "Deuteronomy (4Q41)",
        "Psalms (4Q86)",
        "Daniel (4Q114)",
    ]),
    ("🔥 Zoroastrian", [
        ("The Avesta", ["Gathas", "Yasna", "Yashts", "Vendidad"]),
        ("Pahlavi texts", ["Bundahishn"]),
    ]),
    ("🪯 Sikh", [
        "Guru Granth Sahib",
        "Japji",
    ]),
    ("🤚 Jain", [
        "Akaranga Sutra",
        "Sutrakritanga",
        "Uttaradhyayana Sutra",
        "Kalpa Sutra",
    ]),
    ("⛩️ Shinto", [
        "Kojiki",
        "Nihongi",
    ]),
    ("🌽 Mesoamerican", [
        "Popol Vuh",
    ]),
    ("🦢 Finnish", [
        "Kalevala",
    ]),
    ("☘️ Celtic", [
        "Mabinogion",
    ]),
    ("🧿 Gnostic", [
        ("Gospel of Thomas (trans. Lambdin)", [
            "Gospel of Thomas",
        ]),
        ("Mandaean", [
            "Ginza Rba",
            "Book of John",
        ]),
        ("The Nag Hammadi Library (trans. Samuel Zinner)", [
            "The Prayer of Paul, the Apostle", "The Secret Book of James",
            "Treatise on the Resurrection", "The Tripartite Tractate",
            "The Substance of the Archons", "On the Origin of the World",
            "The Exegesis on the Soul", "The Book of Thomas the Contender",
            "The Sacred Book of the Great Unseen Spirit", "Eugnostos the Blessed",
            "The Sophia of Jesus Christ", "The Dialogue of the Savior",
            "The Apocalypse of Paul", "The Second Apocalypse of James",
            "The Apocalypse of Adam", "The Acts of Peter and the Twelve Apostles",
            "The Thunder, Perfect Mind", "The Authentic Logos",
            "The Idea of Our Great Power", "The Discourse on the Eighth and Ninth",
            "The Prayer of Thanksgiving", "Excerpt from the Perfect Discourse",
            "The Paraphrase of Shem", "The Second Discourse of the Great Seth",
            "The Apocalypse of Peter", "The Teachings of Silvanus",
            "The Three Steles of Seth", "Zostrianos", "The Letter of Peter to Philip",
            "Melchizedek", "The Thought of Norea", "The Testimony of Truth",
            "Marsanes", "The Interpretation of Knowledge",
            "A Valentinian Exposition and Liturgical Readings",
            "Allogenes (The Stranger)", "Hypsiphrone", "The Sentences of Sextus",
            "Trimorphic Protennoia (Three Forms of Primal Thought)",
            "Corpus Hermeticum XIII, On Rebirth", "The Act of Peter",
        ]),
        ("Manichaean (trans. C.R.C. Allberry, 1938)", [
            "Manichaean Psalms to Jesus",
            "Manichaean Bema Psalms",
            "Manichaean Psalms of Thomas",
            "Manichaean Psalms (Separate)",
        ]),
    ]),
    ("🌲 Norse", [
        ("Poetic Edda", [
            "Voluspo", "Hovamol", "Vafthruthnismol", "Grimnismol", "Skirnismol",
            "Harbarthsljoth", "Hymiskvitha", "Lokasenna", "Thrymskvitha", "Alvissmol",
            "Baldrs Draumar", "Rigsthula", "Hyndluljoth", "Svipdagsmol",
            "Völundarkvitha", "Helgakvitha Hjorvarthssonar",
            "Helgakvitha Hundingsbana I", "Helgakvitha Hundingsbana II",
            "Fra Dautha Sinfjotla", "Gripisspo", "Reginsmol", "Fafnismol",
            "Sigrdrifumol", "Brot af Sigurtharkvithu", "Guthrunarkvitha I",
            "Sigurtharkvitha en Skamma", "Helreith Brynhildar", "Drap Niflunga",
            "Guthrunarkvitha II", "Guthrunarkvitha III", "Oddrunargratr",
            "Atlakvitha en Gronlenzka", "Atlamol en Gronlenzku",
            "Guthrunarhvot", "Hamthesmol",
        ]),
    ]),
    ("🌙 Ancient Near East", [
        ("Mesopotamian", [
            "Enuma Elish",
            ("The Epic of Gilgamesh", [
                "Gilgamesh 1 — The Tyranny of Gilgamesh (6 sec.)",
                "Gilgamesh 2 — The Meeting of Gilgamesh and Enkidu (5 sec.)",
                "Gilgamesh 3 — Expedition to the Forest of Cedars (6 sec.)",
                "Gilgamesh 4 — Arrival at the Gate of the Forest (3 sec.)",
                "Gilgamesh 5 — The Fight with Humbaba (4 sec.)",
                "Gilgamesh 6 — The Goddess Ishtar (1 sec.)",
                "Gilgamesh 7 — The Death of Enkidu (2 sec.)",
                "Gilgamesh 8 — The Mourning of Gilgamesh (1 sec.)",
                "Gilgamesh 9 — Gilgamesh Seeks Eternal Life (2 sec.)",
                "Gilgamesh 10 — How Gilgamesh Reached Uta-Napishtim (5 sec.)",
                "Gilgamesh 11 — The Flood (1 sec.)",
                "Gilgamesh 12 — Gilgamesh Enquires of the Dead (1 sec.)",
            ]),
        ]),
        ("Canaanite", [
            ("The Baal Cycle", [
                "Baal 1 — Baal and Yamm (8 sections)",
                "Baal 2 — The Palace of Baal (10 sections)",
                "Baal 3 — Baal and Mot (8 sections)",
            ]),
        ]),
        ("Egyptian", [
            "The Great Hymn to the Aten",
            "Book of the Dead",
            "The Leiden Hymns",
            "The Instruction of Amenemope",
            "The Book of Two Ways",
        ]),
        ("Aramaic / Syriac", [
            "The Story of Ahikar",
        ]),
        ("Pre-Islamic Arabic", [
            ("The Mu'allaqat — Seven Suspended Odes", [
                "Muallaqat 1 — Imru' al-Qais (60 stanzas)",
                "Muallaqat 2 — Tarafa ibn al-'Abd (33 stanzas)",
                "Muallaqat 3 — Zuhayr ibn Abi Sulma (34 stanzas)",
                "Muallaqat 4 — Labid ibn Rabi'ah (32 stanzas)",
                "Muallaqat 5 — Antara ibn Shaddad (36 stanzas)",
                "Muallaqat 6 — Amr ibn Kulthum (29 stanzas)",
                "Muallaqat 7 — Al-Harith ibn Hilliza (24 stanzas)",
            ]),
        ]),
    ]),
    ("☸️ Dharmic", [
        ("Vedas", [
            "Rig Veda",
            "Yajur Veda",
            "Sama Veda",
            "Atharva Veda",
        ]),
        ("Upanishads", [
            "Isa Upanishad",
            "Katha Upanishad",
            "Kena Upanishad",
            "Chandogya Upanishad",
            "Brihadaranyaka Upanishad",
            "Mundaka Upanishad",
            "Taittiriya Upanishad",
            "Svetasvatara Upanishad",
            "Prasna Upanishad",
            "Kaushitaki Upanishad",
            "Maitrayana Upanishad",
            "Aitareya Aranyaka",
        ]),
        ("Bhagavad Gita", [
            "Bhagavad Gita",
        ]),
        ("Yoga & Law", [
            "Yoga Sutras",
            "Laws of Manu",
        ]),
    ]),
    ("☸️ Buddhist", [
        "Dhammapada",
        "Sutta Nipata",
        "Jataka",
        "Questions of King Milinda",
        "Diamond Sutra",
        "Lotus Sutra",
    ]),
    ("☯️ Chinese Classics", [
        ("Laozi & Zhuangzi", ["Tao Te Ching", "Zhuangzi"]),
        ("Confucius & Mencius", ["Analects", "Mencius", "Great Learning", "Doctrine of the Mean"]),
        ("The Book of Changes", ["I Ching"]),
    ]),
    ("⛪ Patristics & Church History", [
        ("Apostolic Fathers", [
            "1 Clement","2 Clement",
            "Ignatius to the Ephesians","Ignatius to the Magnesians",
            "Ignatius to the Trallians","Ignatius to the Romans",
            "Ignatius to the Philadelphians","Ignatius to the Smyrnaeans",
            "Ignatius to Polycarp",
            "Polycarp to the Philippians","Martyrdom of Polycarp",
            "Epistle of Barnabas","Didache","Shepherd of Hermas",
        ]),
        ("Dionysius the Areopagite", [
            "Divine Names","Mystical Theology",
            "On the Heavenly Hierarchy","On the Ecclesiastical Hierarchy",
            "Letters of Dionysius","Liturgy of St. Dionysius",
        ]),
        ("Ante-Nicene Fathers", [
            ("Justin Martyr", [
                "First Apology","Second Apology","Dialogue with Trypho",
                "Hortatory Address to the Greeks","Discourse to the Greeks",
            ]),
            ("Irenaeus of Lyons", [
                "Against Heresies",
                "Fragments from the Lost Writings of Irenaeus",
            ]),
            ("Clement of Alexandria", [
                "Exhortation to the Heathen","The Instructor","Stromateis",
                "Who is the Rich Man That Shall Be Saved?",
            ]),
            ("Tertullian", [
                "Apology","On the Prescription of Heretics","Against Marcion",
                "On the Soul","On the Resurrection of the Flesh","Against Praxeas",
                "On Baptism","On Repentance","On Patience","On Prayer","On Idolatry",
                "Scorpiace","Against Hermogenes","On Modesty","On the Veiling of Virgins",
                "De Spectaculis (The Shows)","An Answer to the Jews",
                "Against the Valentinians","On Exhortation to Chastity","On Monogamy",
            ]),
            ("Origen", [
                "De Principiis","Against Celsus","Philocalia",
                "Commentary on the Gospel of John",
                "Commentary on the Gospel of Matthew",
            ]),
            ("Hippolytus", [
                "The Refutation of All Heresies","The Antichrist",
                "Against the Heresy of Noetus",
            ]),
            ("Athenagoras", [
                "A Plea for the Christians","The Resurrection of the Dead",
            ]),
            ("Tatian", ["Address to the Greeks","The Diatessaron"]),
            ("Theophilus", ["Theophilus to Autolycus"]),
            ("Minucius Felix", ["Octavius"]),
            ("Lactantius", [
                "The Divine Institutes","The Epitome of the Divine Institutes",
                "On the Anger of God","On the Workmanship of God",
                "Of the Manner In Which the Persecutors Died",
            ]),
            ("Cyprian of Carthage", [
                "The Treatises of Cyprian","The Life and Passion of Cyprian",
            ]),
            ("Novatian", ["Treatise Concerning the Trinity","On the Jewish Meats"]),
            ("Methodius", [
                "The Banquet of the Ten Virgins","Concerning Free Will",
            ]),
            ("Dionysius the Great", [
                "Epistles and Epistolary Fragments",
                "Exegetical Fragments","Miscellaneous Fragments",
            ]),
            ("Arnobius", ["Against the Heathen"]),
            ("Aphrahat", ["Demonstrations"]),
            ("Clement of Rome", [
                "First Epistle","Second Epistle",
                "Recognitions","Clementine Homilies",
            ]),
            ("Julius Africanus", ["Extant Writings"]),
            ("Gregory Thaumaturgus", [
                "The Oration and Panegyric Addressed to Origen",
                "Canonical Epistle","Twelve Topics on the Faith",
            ]),
        ]),
        ("Nicene Fathers", [
            ("Eusebius of Caesarea", [
                "Church History","Life of Constantine",
                "Oration in Praise of Constantine",
            ]),
            ("Athanasius", [
                "On the Incarnation","Discourses Against the Arians",
                "On the Decrees of Nicaea","Apologia Contra Arianos",
                "Life of Antony","Historia Arianorum","De Sententia Dionysii",
                "Festal Letters of Athanasius", "Letters of Athanasius",
            ]),
            ("Hilary of Poitiers", [
                "On the Trinity","On the Councils, or the Faith of the Easterns",
            ]),
            ("Cyril of Jerusalem", ["Catechetical Lectures"]),
            ("Basil the Great", [
                "Hexaemeron","On the Holy Spirit",
                "Address to Young Men","Letters of Basil",
            ]),
            ("Gregory Nazianzen", [
                "Orations","Orations Against Julian","Letters of Gregory Nazianzen",
            ]),
            ("Gregory of Nyssa", [
                "On the Soul and the Resurrection","The Great Catechism",
                "On the Making of Man","Against Eunomius",
                "On Virginity","Life of Macrina","Letters of Gregory of Nyssa",
            ]),
            ("Ambrose", [
                "On the Christian Faith (De fide)","On the Holy Spirit",
                "On the Mysteries","On the Duties of the Clergy",
                "Concerning Virgins","On Repentance","Letters",
            ]),
            ("John Chrysostom", [
                "On the Priesthood","Homilies on Matthew","Homilies on John",
                "Homilies on Acts","Homilies on Romans",
                "Homilies on 1 Corinthians","Homilies on 2 Corinthians",
                "Homilies on Ephesians","Homilies on Philippians",
                "Homilies on Colossians","Homilies on Hebrews",
                "Homilies on the Statues","Homilies on Titus","Homilies on Philemon",
                "Commentary on Galatians",
            ]),
            ("Ephrem the Syrian", [
                "Discourses to Hypatius","Against Marcion","Against Mani",
                "On Virginity","Nisibene Hymns",
            ]),
        ]),
        ("Post-Nicene Fathers", [
            ("Augustine of Hippo", [
                "Confessions","City of God","On the Trinity","Enchiridion",
                "On Christian Doctrine","On Nature and Grace",
                "On the Spirit and the Letter",
                "On the Morals of the Catholic Church","Letters of Augustine",
                "Tractates on the Gospel of John",
                "The Enarrations, or Expositions, on the Psalms",
                "Reply to Faustus the Manichaean","On Grace and Free Will",
                "On Baptism, Against the Donatists","The Harmony of the Gospels",
            ]),
            ("Jerome", [
                "Letters","Lives of Illustrious Men","Commentary on Daniel",
                "Against Jovinianus","Against Vigilantius","Against the Pelagians",
                "The Life of Malchus, the Captive Monk","The Life of S. Hilarion",
            ]),
            ("John Cassian", [
                "Institutes","Conferences",
                "On the Incarnation of the Lord (Against Nestorius)",
            ]),
            ("Cyril of Alexandria", [
                "Against Nestorius","Commentary on John","Commentary on Luke",
                "That Christ is One","Scholia on the Incarnation","Against Julian",
            ]),
            ("Leo the Great", ["Sermons","Letters of Leo"]),
            ("Theodoret", [
                "Ecclesiastical History","Letters",
                'Dialogues ("Eranistes" or "Polymorphus")',
            ]),
            ("Socrates Scholasticus", ["Ecclesiastical History"]),
            ("Sozomen", ["Ecclesiastical History"]),
            ("Sulpitius Severus", [
                "On the Life of St. Martin","Dialogues","Sacred History",
            ]),
            ("John of Damascus", [
                "Exposition of the Orthodox Faith","Philosophical Chapters",
            ]),
            ("Gregory the Great", [
                "Dialogues","Pastoral Rule","Letters of Gregory the Great",
            ]),
            ("Vincent of Lérins", [
                "Commonitory for the Antiquity and Universality of the Catholic Faith",
            ]),
        ]),
        ("Church History", [
            ("Josephus", [
                "Jewish Antiquities","Jewish War","Against Apion","Life",
            ]),
            ("Eusebius of Caesarea", [
                "Church History","Life of Constantine","Oration in Praise of Constantine",
                "Demonstratio Evangelica","Praeparatio Evangelica","Theophania",
            ]),
            ("Bede the Venerable", [
                "Ecclesiastical History of the English People",
            ]),
            ("Jacobus de Voragine", [
                "The Golden Legend",
            ]),
        ]),
        ("Medieval Classics", [
            ("St Benedict", ["Rule of Benedict"]),
            ("Thomas à Kempis", ["Imitation of Christ"]),
            ("Dante — The Divine Comedy", ["Inferno", "Purgatorio", "Paradiso"]),
        ]),
        ("Christian Mystics", [
            ("Anonymous (14th century)", ["Cloud of Unknowing"]),
            ("Julian of Norwich", ["Revelations of Divine Love"]),
            ("Brother Lawrence", ["Practice of the Presence of God"]),
        ]),
        ("Swedenborg", [
            ("The main works", [
                "Heaven and Hell", "Arcana Coelestia", "Divine Love and Wisdom", "Divine Providence",
                "True Christian Religion", "Conjugial Love", "Apocalypse Revealed", "Apocalypse Explained",
                "Earths in the Universe", "The New Jerusalem and its Heavenly Doctrine",
            ]),
            ("The shorter works", [
                "The Last Judgment", "The Last Judgment Continued", "The White Horse", "Doctrine of the Lord",
                "Doctrine of the Sacred Scripture", "Doctrine of Life", "Doctrine of Faith",
                "Brief Exposition of the Doctrine of the New Church", "Interaction of the Soul and Body",
                "Coronis", "Invitation to the New Church",
            ]),
            ("Published after his death", [
                "Spiritual Diary", "The Last Judgment (Posthumous)", "On the Athanasian Creed", "De Domino",
                "Prophets and Psalms", "De Verbo", "Divine Love", "Divine Wisdom", "Doctrine of Charity",
                "De Conjugio", "God the Saviour", "Canons of the New Church",
            ]),
        ]),
        ("John Bunyan", [
            ("John Bunyan", ["Pilgrim's Progress", "Pilgrim's Progress, Part Two"]),
        ]),
        ("John Milton", [
            ("John Milton", ["Paradise Lost", "Paradise Regained", "Samson Agonistes"]),
        ]),
        ("William Blake", [
            ("William Blake", ["Songs of Innocence", "Songs of Experience", "The Marriage of Heaven and Hell",
                               "The Book of Thel"]),
        ]),
        ("The Reformation", [
            ("Martin Luther", [
                "Ninety-Five Theses", "An Open Letter to the Christian Nobility", "The Babylonian Captivity of the Church",
                "A Treatise on Christian Liberty", "Treatise on Good Works", "The Bondage of the Will",
                "The Eight Wittenberg Sermons", "Luther on Galatians", "Table Talk", "Sermons of Martin Luther",
            ]),
            ("John Calvin", ["Institutes of the Christian Religion", "Prefatory Address to Francis I", "A Treatise on Relics"]),
            ("John Knox", ["The History of the Reformation in Scotland", "The First Blast of the Trumpet", "A Treatise on Prayer"]),
            ("Hugh Latimer", ["Sermons of Hugh Latimer"]),
        ]),
        ("The Book of Concord", [
            ("The Lutheran confessions", [
                "Preface to the Book of Concord", "Augsburg Confession", "Apology of the Augsburg Confession",
                "Smalcald Articles", "Treatise on the Power and Primacy of the Pope", "Small Catechism",
                "Large Catechism", "Formula of Concord, Epitome", "Formula of Concord, Solid Declaration",
            ]),
        ]),
        ("Protestant Confessions", [
            ("Reformed", [
                "Heidelberg Catechism", "Second Helvetic Confession", "Belgic Confession", "Canons of Dort",
                "Scots Confession", "Westminster Confession of Faith", "Westminster Shorter Catechism",
                "Westminster Larger Catechism",
            ]),
            ("Anglican, Methodist, Baptist", [
                "Thirty-Nine Articles", "Methodist Articles of Religion", "Second London Baptist Confession",
            ]),
        ]),
        ("Anglican Divines & the Wesleys", [
            ("The Books of Homilies", ["The Book of Homilies, First Book", "The Book of Homilies, Second Book"]),
            ("Edmund Bonner (Marian, Catholic)", ["Bonner's Homilies"]),
            ("Richard Hooker", ["Laws of Ecclesiastical Polity"]),
            ("John Donne", ["Donne's LXXX Sermons", "Donne's Fifty Sermons", "Donne's XXVI Sermons", "Holy Sonnets"]),
            ("George Herbert", ["The Temple"]),
            ("Lancelot Andrewes", ["Private Devotions of Lancelot Andrewes"]),
            ("Jeremy Taylor", ["Holy Living", "Holy Dying"]),
            ("William Law", ["A Serious Call to a Devout and Holy Life"]),
            ("John Wesley", ["Sermons of John Wesley", "A Plain Account of Christian Perfection", "The Journal of John Wesley"]),
        ]),
        ("Pearse Collection", [
            ("Hermias", ["Derision of Gentile Philosophers"]),
            ("Eunomius of Cyzicus", ["The First Apology"]),
            ("Philostorgius", ["Ecclesiastical History (Epitome)"]),
            ("Pacian of Barcelona", [
                "Letters to Sympronian","Paraenesis on Penance","Discourse on Baptism",
            ]),
            ("Macarius Magnes", ["Apocriticus"]),
            ("Asterius of Amasea", ["Sermons"]),
            ("Epiphanius of Salamis", ["On Weights and Measures"]),
            ("Pseudo-Hegesippus", ["On the Ruin of Jerusalem"]),
            ("Optatus of Milevis", ["Against the Donatists"]),
            ("Possidius", ["Life of St. Augustine"]),
            ("Theodore of Mopsuestia", [
                "Commentary on the Nicene Creed",
                "Commentary on the Lord's Prayer and Sacraments",
            ]),
            ("Nestorius", ["The Bazaar of Heracleides"]),
            ("Palladius", [
                "The Lausiac History",
                "Dialogue on the Life of St. John Chrysostom",
            ]),
            ("Salvian", ["On the Government of God"]),
            ("Sidonius Apollinaris", ["Letters"]),
            ("Philoxenus of Hierapolis", ["13 Ascetic Discourses"]),
            ("Evagrius Scholasticus", ["Ecclesiastical History"]),
            ("Dioscorus of Alexandria", ["Letter to Shenouda"]),
            ("Gildas the Wise", ["The Ruin of Britain","Penitential"]),
            ("Leontius of Byzantium", ["Against the Frauds of the Apollinarists"]),
            ("Severus of Antioch", ["Letters"]),
            ("John of Ephesus", ["Ecclesiastical History (Third Part)"]),
            ("Cosmas Indicopleustes", ["The Christian Topography"]),
            ("Agapius of Hierapolis", ["Universal History"]),
            ("Photius of Constantinople", ["Bibliotheca (Codices 1-165)"]),
            ("Timothy I", ["Apology for Christianity to Caliph Al-Mahdi"]),
            ("Isidore of Seville", ["Chronicon"]),
            ("John bar Penkaye", ["Summary History of the World (Book 15: Rise of Islam)"]),
        ]),
    ]),
]

def _perseus_authors() -> list:
    """[(author, [book names])] of the Perseus library (scripts/build_perseus.py writes the index)."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "data" / "classical" / "perseus" / "index.json"
    try:
        return [(author, books) for author, books in json.loads(path.read_text(encoding="utf-8")).items()]
    except (OSError, ValueError):
        return []


dict(BOOKS_TREE)["🏛️ Classical"].append(("The Perseus Library: Greek & Latin authors", _perseus_authors()))

# Books the tree above shows another way: the Gilgamesh tablets and the Baal Cycle's episodes are
# listed as "Gilgamesh 1 — ..." / "Baal 1 — ...", which read them by number
_SHOWN_ELSEWHERE = ({f"Gilgamesh Tablet {n}" for n in range(1, 13)} | {"Baal and Yamm", "The Palace of Baal", "Baal and Mot"}
                    | {"Quran"})                                  # (listed surah by surah)


def _leaves(node):
    for item in node:
        if isinstance(item, tuple):
            yield from _leaves(item[1])
        else:
            yield item


def _author(fname: str) -> str:
    """The person (or collection) a data file holds: "clement_of_alexandria.json" -> "Clement of Alexandria"."""
    words = re.sub(r"_en$", "", fname.rsplit(".", 1)[0]).replace("_", " ").split()   # (muallaqat_en.json)
    small = {"of", "the", "and", "on", "to", "in", "de"}
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _complete_tree(tree, lookup) -> int:
    """Add every book in the library that the hand-kept tree leaves out, under the section that holds
    the rest of its collection, by author: the tree had drifted, missing ~200 of the Church Fathers'
    treatises. Returns how many were added."""
    import collections
    listed, home = set(), collections.defaultdict(collections.Counter)
    for section, contents in tree:
        for leaf in _leaves(contents):
            listed.add(leaf)
            corpus, book = lookup._resolve_exact(leaf)
            if book:
                listed.add(book)
                home[corpus][section] += 1
    missing = collections.defaultdict(lambda: collections.defaultdict(list))
    for corpus, books in lookup._data.items():
        for book, chapters in books.items():
            if book in listed or book in _SHOWN_ELSEWHERE or not home[corpus] or not any(chapters.values()):
                continue
            if lookup._resolve_exact(book) != (corpus, book):       # (a name another collection answers to)
                continue
            section = home[corpus].most_common(1)[0][0]
            missing[section][_author(lookup._book_file.get((corpus, book), corpus))].append(book)
    # an author the tree already has ("Augustine" -> "Augustine of Hippo") gets them in his own list
    authors = {}

    def index(node):
        for item in node:
            if isinstance(item, tuple):
                if item[1]:
                    authors.setdefault(item[0].lower(), item[1])
                index(item[1])
    index(tree)

    def own_list(author):
        a = author.lower()
        return authors.get(a) or next((books for label, books in authors.items()
                                       if label.startswith(a + " ") or a.startswith(label + " ") or label.endswith(" " + a)), None)
    sections = dict(tree)
    for section, by_author in missing.items():
        others = []
        for author, books in sorted(by_author.items()):
            books = sorted(books, key=str.lower)
            existing = own_list(author)
            if existing is not None:
                existing.extend(books)
            else:
                others.append((author, books))
        if others:
            sections[section].append(("📚 Also in the library", others))
    return sum(len(b) for by_author in missing.values() for b in by_author.values())


_ADDED_TO_TREE = _complete_tree(BOOKS_TREE, lookup)

# Top-level browsing groups two supergroups on top of BOOKS_TREE without
# reordering it: Abrahamic-descended scripture/commentary traditions (still
# living faiths with a canon + commentary literature) vs. mythological and
# classical-philosophical corpora. Reuses the same nested lists/tuples from
# BOOKS_TREE by reference, so drilling further down is unaffected.
_SUPERGROUP_ORDER = [
    ("📖 Abrahamic Scripture & Commentary", [
        "📖 The Bible", "👼 Apocrypha / Pseudepigrapha", "✡️ Rabbinic & Kabbalistic",
        "☪️ Islamic", "🧿 Gnostic", "📯 LDS", "🌍 Bahá'í", "🏺 Dead Sea Scrolls",
        "⛪ Patristics & Church History",
    ]),
    ("🪷 Eastern Traditions", [
        "☸️ Dharmic", "🪯 Sikh", "🤚 Jain", "☸️ Buddhist", "☯️ Chinese Classics", "⛩️ Shinto",
    ]),
    ("🌐 Mythology & Classical Traditions", [
        "🏛️ Classical", "🌲 Norse", "🦢 Finnish", "☘️ Celtic", "🌙 Ancient Near East",
        "🔥 Zoroastrian", "🌽 Mesoamerican",
    ]),
]
# ── a server sees only the sections of the traditions it chose ──────────────

# sections read from online libraries, whose books aren't stored here to tell
_ONLINE_SECTIONS = {"✡️ Rabbinic & Kabbalistic": "jewish", "☪️ Islamic": "islamic", "📖 The Bible": "bible"}


def _section_traditions() -> dict:
    """{section: the TRADITIONS key most of its books belong to}."""
    import collections
    from scripture_lookup import CORPUS_TRADITION
    out = dict(_ONLINE_SECTIONS)
    for section, contents in BOOKS_TREE:
        if section in out:
            continue
        found = collections.Counter(CORPUS_TRADITION.get(lookup._resolve_exact(leaf)[0]) for leaf in _leaves(contents))
        found.pop(None, None)
        out[section] = found.most_common(1)[0][0] if found else None
    return out


_SECTION_TRADITION = _section_traditions()


def tree_for(guild_id) -> tuple:
    """(the top-level browsing tree, the sections) this server sees."""
    allowed = guild_traditions(guild_id)
    sections = [(n, c) for n, c in BOOKS_TREE if _SECTION_TRADITION.get(n) in allowed | {None}]
    if len(sections) == len(BOOKS_TREE):
        return ROOT_BOOKS_TREE, BOOKS_TREE
    names = {n for n, _ in sections}
    root = [(group, [(n, c) for n, c in subs if n in names]) for group, subs in ROOT_BOOKS_TREE]
    return [(group, subs) for group, subs in root if subs], sections


def _hidden_book(guild_id, name) -> bool:
    """A book of a tradition this server turned off."""
    from scripture_lookup import CORPUS_TRADITION
    corpus = lookup._resolve_exact(name)[0]
    return corpus is not None and not tradition_enabled(guild_id, CORPUS_TRADITION.get(corpus))


_books_tree_by_name = {name: contents for name, contents in BOOKS_TREE}
ROOT_BOOKS_TREE = [
    (group_label, [(name, _books_tree_by_name[name]) for name in names])
    for group_label, names in _SUPERGROUP_ORDER
]


def _count_leaves(node) -> int:
    count = 0
    for item in node:
        if isinstance(item, tuple):
            count += _count_leaves(item[1])
        else:
            count += 1
    return count


# Stephanus page ranges derived from plato.json
_PLATO_STEPHANUS_RANGES: dict[str, tuple[str, str]] = {
    "Euthyphro": ("2a", "16a"),
    "Apology": ("17a", "42a"),
    "Crito": ("43a", "54e"),
    "Phaedo": ("57a", "118a"),
    "Cratylus": ("383a", "440e"),
    "Theaetetus": ("142a", "210d"),
    "Sophist": ("216a", "268d"),
    "Statesman": ("257a", "311c"),
    "Parmenides": ("126a", "166c"),
    "Philebus": ("11a", "67b"),
    "Symposium": ("172a", "223d"),
    "Phaedrus": ("227a", "279c"),
    "Alcibiades I": ("103a", "135e"),
    "Alcibiades II": ("138a", "151c"),
    "Hipparchus": ("225a", "232c"),
    "Rival Lovers": ("132a", "139a"),
    "Theages": ("121a", "131a"),
    "Charmides": ("153a", "176d"),
    "Laches": ("178a", "201c"),
    "Lysis": ("203a", "223b"),
    "Euthydemus": ("271a", "307c"),
    "Protagoras": ("309a", "362a"),
    "Gorgias": ("447a", "527e"),
    "Meno": ("70a", "100c"),
    "Greater Hippias": ("281a", "304e"),
    "Lesser Hippias": ("363a", "376c"),
    "Ion": ("530a", "542b"),
    "Menexenus": ("234a", "249e"),
    "Cleitophon": ("406a", "410e"),
    "Republic": ("327a", "621d"),
    "Timaeus": ("17a", "92c"),
    "Critias": ("106a", "121c"),
    "Minos": ("313a", "321d"),
    "Laws": ("624a", "969d"),
    "Epinomis": ("973a", "992e"),
    "Letters": ("309a", "363e"),
}

# ── Babylonian Talmud daf ranges (Vilna edition, starts at 2a) ───────────────
_BAVLI_RANGES: dict[str, tuple[str, str]] = {
    "Berakhot": ("2a", "64b"), "Shabbat": ("2a", "157b"), "Eruvin": ("2a", "105b"),
    "Pesachim": ("2a", "121b"), "Shekalim": ("2a", "22b"), "Yoma": ("2a", "88b"),
    "Sukkah": ("2a", "56b"), "Beitzah": ("2a", "40b"), "Rosh Hashanah": ("2a", "35b"),
    "Taanit": ("2a", "31b"), "Megillah": ("2a", "32b"), "Moed Katan": ("2a", "29b"),
    "Chagigah": ("2a", "27b"), "Yevamot": ("2a", "122b"), "Ketubot": ("2a", "112b"),
    "Nedarim": ("2a", "91b"), "Nazir": ("2a", "66b"), "Sotah": ("2a", "49b"),
    "Gittin": ("2a", "90b"), "Kiddushin": ("2a", "82b"), "Bava Kamma": ("2a", "119b"),
    "Bava Metzia": ("2a", "119b"), "Bava Batra": ("2a", "176b"), "Sanhedrin": ("2a", "113b"),
    "Makkot": ("2a", "24b"), "Shevuot": ("2a", "49b"), "Avodah Zarah": ("2a", "76b"),
    "Horayot": ("2a", "14b"), "Zevachim": ("2a", "120b"), "Menachot": ("2a", "110b"),
    "Chullin": ("2a", "142b"), "Bechorot": ("2a", "61b"), "Arachin": ("2a", "34b"),
    "Temurah": ("2a", "34b"), "Keritot": ("2a", "28b"), "Meilah": ("2a", "22b"),
    "Tamid": ("2a", "8b"), "Niddah": ("2a", "73b"),
}

# ── Mishnah chapter and mishnah counts ────────────────────────────────────────
_MISHNAH_RANGES: dict[str, tuple[int, int]] = {
    # (chapters, total mishnayot)
    "Berakhot": (9, 57), "Peah": (8, 69), "Demai": (7, 53), "Kilayim": (9, 77),
    "Sheviit": (10, 89), "Terumot": (11, 101), "Maasrot": (5, 40),
    "Maaser Sheni": (5, 57), "Challah": (4, 38), "Orlah": (3, 35), "Bikkurim": (4, 39),
    "Shabbat": (24, 139), "Eruvin": (10, 96), "Pesachim": (10, 89), "Shekalim": (8, 52),
    "Yoma": (8, 61), "Sukkah": (5, 53), "Beitzah": (5, 42), "Rosh Hashanah": (4, 35),
    "Taanit": (4, 34), "Megillah": (4, 33), "Moed Katan": (3, 24), "Chagigah": (3, 23),
    "Yevamot": (16, 128), "Ketubot": (13, 111), "Nedarim": (11, 90), "Nazir": (9, 60),
    "Sotah": (9, 67), "Gittin": (9, 75), "Kiddushin": (4, 47),
    "Bava Kamma": (10, 79), "Bava Metzia": (10, 101), "Bava Batra": (10, 86),
    "Sanhedrin": (11, 71), "Makkot": (3, 34), "Shevuot": (8, 62), "Eduyot": (8, 74),
    "Avodah Zarah": (5, 50), "Avot": (6, 108), "Horayot": (3, 20),
    "Zevachim": (14, 101), "Menachot": (13, 93), "Chullin": (12, 74), "Bechorot": (9, 73),
    "Arachin": (9, 50), "Temurah": (7, 35), "Keritot": (6, 43), "Meilah": (6, 38),
    "Tamid": (7, 34), "Middot": (5, 34), "Kinnim": (3, 15),
    "Keilim": (30, 254), "Ohalot": (18, 134), "Negaim": (14, 115), "Parah": (12, 96),
    "Taharot": (10, 92), "Mikvaot": (10, 71), "Niddah": (10, 79), "Machshirin": (6, 54),
    "Zavim": (5, 32), "Tevul Yom": (4, 26), "Yadayim": (4, 22), "Oktzin": (3, 28),
}

# ── Jerusalem Talmud chapter counts ──────────────────────────────────────────
_YERUSHALMI_RANGES: dict[str, int] = {
    # chapters (cite as: ch:halakhah, halakhah varies by chapter)
    "Berakhot": 9, "Peah": 8, "Demai": 7, "Kilayim": 9, "Sheviit": 10,
    "Terumot": 11, "Maaserot": 5, "Maaser Sheni": 5, "Challah": 4,
    "Orlah": 3, "Bikkurim": 4, "Shabbat": 24, "Eruvin": 10, "Pesachim": 10,
    "Shekalim": 8, "Yoma": 8, "Sukkah": 5, "Beitzah": 5, "Rosh Hashanah": 4,
    "Taanit": 4, "Megillah": 4, "Moed Katan": 3, "Chagigah": 3,
    "Yevamot": 16, "Ketubot": 13, "Nedarim": 11, "Nazir": 9, "Sotah": 9,
    "Gittin": 9, "Kiddushin": 4, "Bava Kamma": 10, "Bava Metzia": 10,
    "Bava Batra": 10, "Sanhedrin": 11, "Makkot": 3, "Shevuot": 8,
    "Avodah Zarah": 5, "Horayot": 3, "Niddah": 2,
}

# ── Zohar max segment counts per parasha ──────────────────────────────────────
_ZOHAR_SEGMENTS: dict[str, int] = {
    "Introduction": 34, "Bereshit": 200, "Noach": 150, "Lech Lecha": 120,
    "Vayera": 130, "Chayei Sarah": 80, "Toldot": 90, "Vayetze": 100,
    "Vayishlach": 90, "Vayeshev": 80, "Miketz": 80, "Vayigash": 60,
    "Vayechi": 100, "Shemot": 100, "Vaera": 80, "Bo": 80,
    "Beshalach": 80, "Yitro": 80, "Mishpatim": 100, "Terumah": 150,
    "Tetzaveh": 60, "Ki Tisa": 80, "Vayakhel": 80, "Pekudei": 80,
    "Vayikra": 60, "Tzav": 50, "Shmini": 50, "Tazria": 50,
    "Metzora": 40, "Acharei Mot": 80, "Kedoshim": 50, "Emor": 80,
    "Behar": 40, "Bechukotai": 40, "Bamidbar": 60, "Nasso": 80,
    "Behaalotcha": 60, "Shelach Lecha": 60, "Korach": 50, "Chukat": 50,
    "Balak": 80, "Pinchas": 120, "Matot": 40, "Vaetchanan": 60,
    "Eikev": 50, "Re'eh": 50, "Shoftim": 50, "Ki Teitzei": 60,
    "Ki Tavo": 50, "Vayeilech": 30, "Haazinu": 50, "Vezot Haberachah": 30,
}

# ── Midrash Rabbah section counts ─────────────────────────────────────────────
_MIDRASH_SECTIONS: dict[str, int] = {
    "Bereshit Rabbah": 100, "Shemot Rabbah": 52, "Vayikra Rabbah": 37,
    "Bamidbar Rabbah": 23, "Devarim Rabbah": 11, "Ruth Rabbah": 8,
    "Esther Rabbah": 10, "Eichah Rabbah": 5, "Shir HaShirim Rabbah": 8,
    "Kohelet Rabbah": 12, "Mechilta": 9, "Sifra": 15,
    "Sifre Bamidbar": 161, "Sifre Devarim": 357,
    "Pirkei DeRabbi Eliezer": 54, "Midrash Tanchuma": 54,
}

# ── Targum book chapter counts (mirrors Bible) ─────────────────────────────────
_TARGUM_CHAPTERS: dict[str, int] = {
    "Targum Onkelos Genesis": 50, "Targum Onkelos Exodus": 40,
    "Targum Onkelos Leviticus": 27, "Targum Onkelos Numbers": 36,
    "Targum Onkelos Deuteronomy": 34,
    "Targum Pseudo-Jonathan Genesis": 50, "Targum Pseudo-Jonathan Exodus": 40,
    "Targum Neofiti Genesis": 50, "Targum Neofiti Exodus": 40,
    "Targum Jonathan Isaiah": 66, "Targum Jonathan Jeremiah": 52,
    "Targum Jonathan Ezekiel": 48, "Targum Jonathan Hosea": 14,
    "Targum Jonathan Psalms": 150, "Targum Jonathan Proverbs": 31,
    "Targum Jonathan Job": 42,
}

# ── Mishneh Torah: 84 sections with chapter counts ────────────────────────────
# Cite as: !verse Mishneh Torah, Repentance 1:1  (section, chapter:halacha)
_MISHNEH_TORAH_SECTIONS: dict[str, int] = {
    # Book 1: HaMadda
    "Mishneh Torah, Foundations of the Torah": 10,
    "Mishneh Torah, Human Dispositions": 7,
    "Mishneh Torah, Torah Study": 7,
    "Mishneh Torah, Foreign Worship and Customs of the Nations": 11,
    "Mishneh Torah, Repentance": 10,
    # Book 2: Ahavah
    "Mishneh Torah, Reading the Shema": 4,
    "Mishneh Torah, Prayer and the Priestly Blessing": 15,
    "Mishneh Torah, Tefillin, Mezuzah and the Torah Scroll": 10,
    "Mishneh Torah, Fringes": 3,
    "Mishneh Torah, Blessings": 11,
    "Mishneh Torah, Circumcision": 3,
    "Mishneh Torah, The Order of Prayer": 5,
    # Book 3: Zemanim
    "Mishneh Torah, Sabbath": 30,
    "Mishneh Torah, Eruvin": 8,
    "Mishneh Torah, Rest on the Tenth of Tishrei": 3,
    "Mishneh Torah, Rest on a Holiday": 8,
    "Mishneh Torah, Leavened and Unleavened Bread": 8,
    "Mishneh Torah, Shofar, Sukkah and Lulav": 8,
    "Mishneh Torah, Sheqel Dues": 4,
    "Mishneh Torah, Sanctification of the New Month": 19,
    "Mishneh Torah, Fasts": 5,
    "Mishneh Torah, Megillah and Hanukkah": 4,
    # Book 4: Nashim
    "Mishneh Torah, Marriage": 25,
    "Mishneh Torah, Divorce": 13,
    "Mishneh Torah, Levirate Marriage and Release": 8,
    "Mishneh Torah, Virgin Maiden": 3,
    "Mishneh Torah, Sotah": 4,
    # Book 5: Kedushah
    "Mishneh Torah, Forbidden Intercourse": 22,
    "Mishneh Torah, Forbidden Foods": 17,
    "Mishneh Torah, Slaughter": 14,
    # Book 6: Haflaah
    "Mishneh Torah, Oaths": 12,
    "Mishneh Torah, Vows": 13,
    "Mishneh Torah, Naziriteship": 10,
    "Mishneh Torah, Appraisals and Devoted Property": 8,
    # Book 7: Zeraim
    "Mishneh Torah, Diverse Species": 10,
    "Mishneh Torah, Gifts to the Poor": 10,
    "Mishneh Torah, Heave Offerings": 15,
    "Mishneh Torah, Tithes": 14,
    "Mishneh Torah, Second Tithe and Fourth Year Produce": 11,
    "Mishneh Torah, First Fruits and other Gifts to Priests Outside the Temple": 12,
    "Mishneh Torah, Sabbatical Year and the Jubilee": 13,
    # Book 8: Avodah
    "Mishneh Torah, The Chosen Temple": 8,
    "Mishneh Torah, Vessels of the Sanctuary and Those who Serve Therein": 10,
    "Mishneh Torah, Admission into the Sanctuary": 9,
    "Mishneh Torah, Things Forbidden on the Altar": 7,
    "Mishneh Torah, Sacrificial Procedure": 19,
    "Mishneh Torah, Daily Offerings and Additional Offerings": 10,
    "Mishneh Torah, Sacrifices Rendered Unfit": 19,
    "Mishneh Torah, The Yom Kippur Service": 5,
    "Mishneh Torah, Trespass": 8,
    # Book 9: Korbanot
    "Mishneh Torah, Paschal Offering": 10,
    "Mishneh Torah, Festival Offering": 3,
    "Mishneh Torah, Firstborn": 8,
    "Mishneh Torah, Offerings for Unintentional Transgressions": 15,
    "Mishneh Torah, Offerings for Those with Incomplete Atonement": 5,
    "Mishneh Torah, Substitution": 4,
    # Book 10: Taharah
    "Mishneh Torah, Corpse Impurity": 25,
    "Mishneh Torah, Red Heifer": 16,
    "Mishneh Torah, Leprosy": 16,
    "Mishneh Torah, Those who Defile Bed or Seat": 8,
    "Mishneh Torah, Other Sources of Defilement": 20,
    "Mishneh Torah, Defilement of Foods": 16,
    "Mishneh Torah, Vessels": 28,
    "Mishneh Torah, Immersion Pools": 11,
    # Book 11: Nezikin
    "Mishneh Torah, Property Damage": 14,
    "Mishneh Torah, Theft": 9,
    "Mishneh Torah, Robbery and Lost Property": 18,
    "Mishneh Torah, One Who Injures a Person or Property": 8,
    "Mishneh Torah, Murderers and the Preservation of Life": 13,
    # Book 12: Kinyan
    "Mishneh Torah, Sales": 30,
    "Mishneh Torah, Ownerless Property and Gifts": 12,
    "Mishneh Torah, Neighbors": 14,
    "Mishneh Torah, Agents and Partners": 10,
    "Mishneh Torah, Slaves": 9,
    # Book 13: Mishpatim
    "Mishneh Torah, Hiring": 13,
    "Mishneh Torah, Borrowing and Deposit": 8,
    "Mishneh Torah, Creditor and Debtor": 27,
    "Mishneh Torah, Plaintiff and Defendant": 16,
    "Mishneh Torah, Inheritance": 11,
    # Book 14: Shoftim
    "Mishneh Torah, Courts": 26,
    "Mishneh Torah, Testimony": 22,
    "Mishneh Torah, Rebels": 3,
    "Mishneh Torah, Mourning": 14,
    "Mishneh Torah, Kings and Wars": 12,
}
_MISHNEH_TORAH_BOOKS = set(_MISHNEH_TORAH_SECTIONS.keys())

# Guide for the Perplexed: 3 parts, varying chapters
_GUIDE_PERPLEXED_CHAPTERS = {
    "Guide for the Perplexed": (3, 179),  # 3 parts, 179 chapters total
}

# ── Other Kabbalah chapter counts ─────────────────────────────────────────────
_KABBALAH_CHAPTERS: dict[str, int] = {
    "Sefer Yetzirah": 6,     # 6 chapters
    "Sefer HaBahir": 1,      # 200 sections in 1 "chapter"
    "Tikkunei Zohar": 70,    # 70 tikkuns
    "Zohar Chadash": 10,     # ~10 sections
    "Tanya": 5,              # 5 parts (Part I: 53 ch., II: 12, III: 12, IV: 32, V: 9)
}

# Tanya part details for display
_TANYA_PARTS: dict[int, tuple[str, int]] = {
    1: ("Likkutei Amarim",          53),
    2: ("Shaar HaYichud VehaEmunah", 12),
    3: ("Iggeret HaTeshuvah",        12),
    4: ("Iggeret HaKodesh",          32),
    5: ("Kuntres Acharon",            9),
}

# Citation format hints per book/corpus
_CITATION_HINTS: dict[str, str] = {
    # Mishnah tractates
    "Berakhot": "!verse Berakhot 1:1  (tractate chapter:mishnah)",
    "Shabbat": "!verse Shabbat 1:1  (tractate chapter:mishnah)",
    "Avot": "!verse Avot 1:1  (tractate chapter:mishnah)",
    # Talmud — same tractate names but daf format
    # (handled via daf detection, so hint is on the Talmud section)
    # Quran
    "Quran": "!verse Quran 2:255  (surah:ayah)",
    # Zohar
    "Zohar": "!verse Zohar Bereshit 5  (parasha + segment number)",
}  # Plato works handled dynamically via _PLATO_STEPHANUS_RANGES below

# Hadith collections
_HADITH_BOOKS = {
    "Sahih al-Bukhari", "Sahih Muslim", "Sunan Abu Dawud",
    "Jami at-Tirmidhi", "Sunan an-Nasa'i", "Sunan Ibn Majah",
    "Muwatta Malik", "Forty Hadith of Nawawi", "Forty Hadith of Dehlawi", "Forty Hadith Qudsi",
}

# Total hadith counts and book counts per collection (one copy, kept in hadith_lookup)
from hadith_lookup import COLLECTION_BOOK_COUNTS as _HADITH_BOOK_COUNTS, COLLECTION_COUNTS as _HADITH_COUNTS

# Jerusalem Talmud tractates (chapter:halakhah citation)
_YERUSHALMI_BOOKS = {
    "Jerusalem Talmud Berakhot","Jerusalem Talmud Peah","Jerusalem Talmud Demai",
    "Jerusalem Talmud Kilayim","Jerusalem Talmud Sheviit","Jerusalem Talmud Terumot",
    "Jerusalem Talmud Maaserot","Jerusalem Talmud Maaser Sheni","Jerusalem Talmud Challah",
    "Jerusalem Talmud Orlah","Jerusalem Talmud Bikkurim","Jerusalem Talmud Shabbat",
    "Jerusalem Talmud Eruvin","Jerusalem Talmud Pesachim","Jerusalem Talmud Shekalim",
    "Jerusalem Talmud Yoma","Jerusalem Talmud Sukkah","Jerusalem Talmud Beitzah",
    "Jerusalem Talmud Rosh Hashanah","Jerusalem Talmud Taanit","Jerusalem Talmud Megillah",
    "Jerusalem Talmud Moed Katan","Jerusalem Talmud Chagigah","Jerusalem Talmud Yevamot",
    "Jerusalem Talmud Ketubot","Jerusalem Talmud Nedarim","Jerusalem Talmud Nazir",
    "Jerusalem Talmud Sotah","Jerusalem Talmud Gittin","Jerusalem Talmud Kiddushin",
    "Jerusalem Talmud Bava Kamma","Jerusalem Talmud Bava Metzia","Jerusalem Talmud Bava Batra",
    "Jerusalem Talmud Sanhedrin","Jerusalem Talmud Makkot","Jerusalem Talmud Shevuot",
    "Jerusalem Talmud Avodah Zarah","Jerusalem Talmud Horayot","Jerusalem Talmud Niddah",
}

# Tosefta books (chapter:halakhah citation)
_TOSEFTA_BOOKS = {name for name in [
    "Tosefta Berakhot","Tosefta Peah","Tosefta Demai","Tosefta Kilayim",
    "Tosefta Sheviit","Tosefta Terumot","Tosefta Maasrot","Tosefta Maaser Sheni",
    "Tosefta Challah","Tosefta Orlah","Tosefta Bikkurim","Tosefta Shabbat",
    "Tosefta Eruvin","Tosefta Pesachim","Tosefta Shekalim","Tosefta Yoma",
    "Tosefta Sukkah","Tosefta Beitzah","Tosefta Rosh Hashanah","Tosefta Taanit",
    "Tosefta Megillah","Tosefta Moed Katan","Tosefta Chagigah","Tosefta Yevamot",
    "Tosefta Ketubot","Tosefta Nedarim","Tosefta Nazir","Tosefta Sotah",
    "Tosefta Gittin","Tosefta Kiddushin","Tosefta Bava Kamma","Tosefta Bava Metzia",
    "Tosefta Bava Batra","Tosefta Sanhedrin","Tosefta Makkot","Tosefta Shevuot",
    "Tosefta Eduyot","Tosefta Avodah Zarah","Tosefta Horayot",
]}

# Targum books (book-level, cite as: Targum Onkelos Genesis 1:1)
_TARGUM_BOOKS = {
    "Targum Onkelos Genesis","Targum Onkelos Exodus","Targum Onkelos Leviticus",
    "Targum Onkelos Numbers","Targum Onkelos Deuteronomy",
    "Targum Pseudo-Jonathan Genesis","Targum Pseudo-Jonathan Exodus",
    "Targum Neofiti Genesis","Targum Neofiti Exodus",
    "Targum Jonathan Isaiah","Targum Jonathan Jeremiah","Targum Jonathan Ezekiel",
    "Targum Jonathan Hosea","Targum Jonathan Psalms","Targum Jonathan Proverbs",
    "Targum Jonathan Job",
}

# Midrash Rabbah books (section:subsection citation)
_MIDRASH_BOOKS = {
    "Bereshit Rabbah","Shemot Rabbah","Vayikra Rabbah","Bamidbar Rabbah",
    "Devarim Rabbah","Ruth Rabbah","Esther Rabbah","Eichah Rabbah",
    "Shir HaShirim Rabbah","Kohelet Rabbah","Mechilta","Sifra",
    "Sifre Bamidbar","Sifre Devarim","Pirkei DeRabbi Eliezer","Midrash Tanchuma",
}

# Zohar parashot (cited as: Zohar Bereshit 5)
_ZOHAR_BOOKS = {f"Zohar {p}" for p, _ in [
    ("Introduction", 34),("Bereshit", 200),("Noach", 150),("Lech Lecha", 120),
    ("Vayera", 130),("Chayei Sarah", 80),("Toldot", 90),("Vayetze", 100),
    ("Vayishlach", 90),("Vayeshev", 80),("Miketz", 80),("Vayigash", 60),
    ("Vayechi", 100),("Shemot", 100),("Vaera", 80),("Bo", 80),
    ("Beshalach", 80),("Yitro", 80),("Mishpatim", 100),("Terumah", 150),
    ("Tetzaveh", 60),("Ki Tisa", 80),("Vayakhel", 80),("Pekudei", 80),
    ("Vayikra", 60),("Tzav", 50),("Shmini", 50),("Tazria", 50),
    ("Metzora", 40),("Acharei Mot", 80),("Kedoshim", 50),("Emor", 80),
    ("Behar", 40),("Bechukotai", 40),("Bamidbar", 60),("Nasso", 80),
    ("Behaalotcha", 60),("Shelach Lecha", 60),("Korach", 50),("Chukat", 50),
    ("Balak", 80),("Pinchas", 120),("Matot", 40),("Vaetchanan", 60),
    ("Eikev", 50),("Re'eh", 50),("Shoftim", 50),("Ki Teitzei", 60),
    ("Ki Tavo", 50),("Vayeilech", 30),("Haazinu", 50),("Vezot Haberachah", 30),
]}

# Other Kabbalah
_OTHER_KABBALAH_BOOKS = {"Sefer Yetzirah","Sefer HaBahir","Tikkunei Zohar","Zohar Chadash","Tanya"}

# Ancient Near East single-book texts (section counts for display)
_ANE_SINGLE_BOOKS: dict[str, tuple[int, str]] = {
    "The Great Hymn to the Aten":    (13, "section"),
    "Book of the Dead":              (52, "chapter"),
    "The Leiden Hymns":              (22, "stanza"),
    "The Instruction of Amenemope":  (36, "chapter"),
    "The Book of Two Ways":          (19, "spell"),
    "The Story of Ahikar":           (5,  "section"),
}

# Talmud tractates (same names as Mishnah but daf-style citation)
_TALMUD_BOOKS = {
    "Berakhot","Shabbat","Eruvin","Pesachim","Yoma","Sukkah","Beitzah",
    "Rosh Hashanah","Taanit","Megillah","Moed Katan","Chagigah","Yevamot",
    "Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin","Bava Kamma",
    "Bava Metzia","Bava Batra","Sanhedrin","Makkot","Shevuot","Avodah Zarah",
    "Horayot","Zevachim","Menachot","Chullin","Bechorot","Arachin","Temurah",
    "Keritot","Meilah","Tamid","Niddah",
}


_GUIDE_PARTS = {1: 75, 2: 48, 3: 54}  # Guide for the Perplexed


def _daf_range(first: str, last: str) -> list[str]:
    """Expand a Bavli daf range like ("2a", "5b") into ["2a","2b","3a",...]."""
    m1, m2 = re.match(r"(\d+)([ab])", first), re.match(r"(\d+)([ab])", last)
    n, side = int(m1.group(1)), m1.group(2)
    n2, side2 = int(m2.group(1)), m2.group(2)
    out = []
    while (n, side) <= (n2, side2):
        out.append(f"{n}{side}")
        if side == "a":
            side = "b"
        else:
            side = "a"
            n += 1
    return out


def chapter_options_for_book(lookup: "ScriptureLookup", book_name: str) -> tuple[list[str], str] | None:
    """
    Return (labels, mode) for the chapter-picker buttons under a book, or
    None if this book isn't chapter-browsable (e.g. one continuous work).
    mode "verse" -> fetch via lookup.get_verse(f"{book_name} {label}")
    mode "hadith" -> fetch via a hadith section lookup

    Dependency-injected (not a closure over the module-level `lookup`) so
    this function -- and fetch_chapter_result() below -- can be lifted
    verbatim into a standalone module reused outside this bot.
    """
    keys = lookup.chapter_keys(book_name)
    if keys:
        return keys, "verse"
    if book_name == "Epistle of Jeremiah":                 # Baruch 6 in the KJV (see ScriptureLookup.get_verse)
        return ["1"], "verse"
    if book_name in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[book_name]
        return _daf_range(first, last), "verse"
    if book_name in _MISHNAH_RANGES:
        chaps, _ = _MISHNAH_RANGES[book_name]
        return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _YERUSHALMI_BOOKS:
        tractate = book_name.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _TOSEFTA_BOOKS:
        tractate = book_name.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        if base:
            return [str(i) for i in range(1, base[0] + 1)], "verse"
    if book_name in _TARGUM_BOOKS:
        chaps = _TARGUM_CHAPTERS.get(book_name)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _MIDRASH_BOOKS:
        secs = _MIDRASH_SECTIONS.get(book_name)
        if secs:
            return [str(i) for i in range(1, secs + 1)], "verse"
    if book_name in _MISHNEH_TORAH_BOOKS:
        chaps = _MISHNEH_TORAH_SECTIONS.get(book_name)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name == "Guide for the Perplexed":
        return [f"{p}:{c}" for p, n in _GUIDE_PARTS.items() for c in range(1, n + 1)], "verse"
    if book_name == "Tanya":
        return [f"{p}:{c}" for p, (_, n) in _TANYA_PARTS.items() for c in range(1, n + 1)], "verse"
    if book_name in _OTHER_KABBALAH_BOOKS:
        chaps = _KABBALAH_CHAPTERS.get(book_name)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _ANE_SINGLE_BOOKS:
        count, _ = _ANE_SINGLE_BOOKS[book_name]
        return [str(i) for i in range(1, count + 1)], "verse"
    if book_name in _ZOHAR_BOOKS:
        parasha = book_name.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha)
        if max_seg:
            return [str(i) for i in range(1, max_seg + 1)], "verse"
    if book_name in _HADITH_BOOKS:
        key = _HADITH_DISPLAY_TO_KEY.get(book_name)
        books = _HADITH_BOOK_COUNTS.get(key) if key else None
        if books:
            return [f"Book {i}" for i in range(1, books + 1)], "hadith"
    return None


def _book_detail_embed(book_name: str) -> discord.Embed:
    """Show chapter-by-chapter verse counts for a single book."""
    counts = lookup.chapter_verse_summary(book_name)
    n_chaps = lookup.chapter_count(book_name)
    embed = discord.Embed(
        title=f"📖 {book_name}",
        color=discord.Color.dark_gold()
    )
    # Show range info from our compiled dicts for non-local texts
    # Baal Cycle: "Baal 1 — Baal and Yamm (9 sections)"
    if book_name.startswith("Baal ") and " — " in book_name:
        import re as _re
        m = _re.match(r"Baal (\d+) — (.+?) \((\d+) sections\)", book_name)
        if m:
            ep_num, ep_title, sec_count = m.group(1), m.group(2), m.group(3)
            embed.title = f"🌙 The Baal Cycle — Episode {ep_num}"
            embed.description = (
                f"**{ep_title}**\n"
                f"**{sec_count} sections** · Cite as: `!verse Baal {ep_num}:1` through `!verse Baal {ep_num}:{sec_count}`\n"
                f"Or: `!parallel Baal {ep_num}.1` for English + Ugaritic"
            )
            return embed
    # Mu'allaqat: "Muallaqat 1 — Imru' al-Qais (61 stanzas)"
    if book_name.startswith("Muallaqat ") and " — " in book_name:
        import re as _re
        m = _re.match(r"Muallaqat (\d+) — (.+?) \((\d+) stanzas\)", book_name)
        if m:
            ode_num, poet, stanza_count = m.group(1), m.group(2), m.group(3)
            roman = ["I","II","III","IV","V","VI","VII"][int(ode_num)-1]
            embed.title = f"🌙 The Mu\'allaqat — Ode {roman}"
            embed.description = (
                f"**{poet}**\n"
                f"**{stanza_count} stanzas** · Cite as: `!verse Muallaqat {ode_num}:1` through `!verse Muallaqat {ode_num}:{stanza_count}`\n"
                f"Or: `!parallel Muallaqat {ode_num}.1` for English + Arabic"
            )
            return embed
    # Quran surah detail: "Quran 2 — Al-Baqara (The Cow, 286v)"
    if book_name.startswith("Quran ") and " — " in book_name:
        m = re.match(r"Quran (\d+) — ([^(]+) \(([^,]+), (\d+)v\)", book_name)
        if m:
            num, arabic, english, verses = m.group(1), m.group(2).strip(), m.group(3).strip(), int(m.group(4))
            embed.title = f"☪️ Quran — Surah {num}: {arabic}"
            embed.description = (
                f"**{arabic}** (*{english}*) · {verses} verses\n"
                f"Cite as: `!verse Quran {num}:1` through `!verse Quran {num}:{verses}`\n"
                f"Or: `!verse Quran {num}` for a random verse from this surah"
            )
            return embed
    if book_name in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[book_name]
        embed.description = f"**Babylonian Talmud · Daf {first}–{last}**\nCite as: `{book_name} 2a` (whole daf) or `{book_name} 2a:3` (section 3 of daf 2a)"
    elif book_name in _MISHNAH_RANGES and not counts:
        chaps, total = _MISHNAH_RANGES[book_name]
        embed.description = f"**{chaps} chapters · {total} mishnayot**\nCite as: `{book_name} 1:1` (chapter 1, mishnah 1)"
    elif book_name in _YERUSHALMI_BOOKS and not counts:
        tractate = book_name.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate, "?")
        embed.description = f"**Jerusalem Talmud · {chaps} chapters**\nCite as: `Jerusalem Talmud {tractate} 1:1` (chapter:halakhah)"
    elif book_name in _ZOHAR_BOOKS and not counts:
        parasha = book_name.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha, "?")
        embed.description = f"**Zohar · {parasha} · Segments 1–{max_seg}**\nCite as: `Zohar {parasha} 5` (segment number)"
    elif book_name in _MIDRASH_BOOKS and not counts:
        secs = _MIDRASH_SECTIONS.get(book_name, "?")
        embed.description = f"**{secs} sections**\nCite as: `{book_name} 1:1` (section:subsection)"
    elif book_name in _TARGUM_BOOKS and not counts:
        chaps = _TARGUM_CHAPTERS.get(book_name, "?")
        embed.description = f"**{chaps} chapters** (mirrors biblical book)\nCite as: `{book_name} 1:1` (chapter:verse)"
    elif book_name in _TOSEFTA_BOOKS and not counts:
        tractate = book_name.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        chaps = base[0] if base else "?"
        embed.description = f"**{chaps} chapters**\nCite as: `Tosefta {tractate} 1:1` (chapter:halakhah)"
    elif book_name in _MISHNEH_TORAH_BOOKS and not counts:
        chaps = _MISHNEH_TORAH_SECTIONS[book_name]
        section = book_name.replace("Mishneh Torah, ", "")
        embed.description = (
            f"**{chaps} chapters**\n"
            f"Cite as: `Mishneh Torah, {section} 1:1` (chapter:halacha)\n"
            f"e.g. `!verse Mishneh Torah, {section} 1:1`"
        )
    elif book_name == "Guide for the Perplexed" and not counts:
        embed.description = (
            "**3 parts · 179 chapters**\n"
            "Cite as: `Guide for the Perplexed 1:1` (part:chapter)\n"
            "Parts: 1 (75 ch.), 2 (48 ch.), 3 (54 ch.)"
        )
    elif book_name == "Tanya" and not counts:
        parts_desc = "\n".join(
            f"  Part {n}: {name} ({chaps} ch.) — `!verse Tanya {n}:1`"
            for n, (name, chaps) in _TANYA_PARTS.items()
        )
        embed.description = f"**5 parts · 118 total chapters**\n{parts_desc}"
    elif book_name in _OTHER_KABBALAH_BOOKS and not counts:
        chaps = _KABBALAH_CHAPTERS.get(book_name, "?")
        embed.description = f"**{chaps} chapters**\nCite as: `{book_name} 1:1`"
    elif book_name in _ANE_SINGLE_BOOKS and not counts:
        count, unit = _ANE_SINGLE_BOOKS[book_name]
        _ane_keywords = {
            "The Great Hymn to the Aten": "Aten",
            "Book of the Dead":           "Book of the Dead",
            "The Leiden Hymns":           "Leiden Hymns",
            "The Instruction of Amenemope": "Amenemope",
            "The Book of Two Ways":       "Two Ways",
            "The Story of Ahikar":        "Ahikar",
        }
        kw = _ane_keywords.get(book_name, book_name)
        embed.description = (
            f"**{count} {unit}s**\n"
            f"Cite as: `!verse {kw} 1` through `!verse {kw} {count}`\n"
            f"Or: `!verse {kw}` for the full text"
        )
    elif book_name in _HADITH_BOOKS and not counts:
        key = _HADITH_DISPLAY_TO_KEY.get(book_name)
        if key:
            total = _HADITH_COUNTS.get(key, "?")
            books = _HADITH_BOOK_COUNTS.get(key, 1)
            embed.description = (
                f"**{total:,} hadiths · {books} books**\n"
                f"Cite by sequential number: `!verse {book_name} 1`\n"
                f"Range: 1–{total:,}"
            )
    elif counts:
        total_verses = sum(counts)
        col_lines = []
        row = []
        for i, vc in enumerate(counts, 1):
            row.append(f"{i}:{vc}")
            if len(row) == 6:
                col_lines.append("  ".join(row))
                row = []
        if row:
            col_lines.append("  ".join(row))
        embed.description = f"**{len(counts)} chapters · {total_verses} verses**\n```\n" + "\n".join(col_lines) + "\n```"
    elif n_chaps:
        embed.description = f"{n_chaps} chapters (verse detail not available locally)"
    else:
        embed.description = "Details not available for this book."

    # Citation hint with actual ranges
    if book_name.startswith("Quran ") and " — " in book_name:
        m = re.match(r"Quran (\d+) — ([^(]+) \(([^,]+), (\d+)v\)", book_name)
        if m:
            num, arabic, verses = m.group(1), m.group(2).strip(), m.group(4)
            hint = f"Verses 1–{verses} · !verse Quran {num}:1  (surah:ayah)"
        else:
            hint = f"!verse Quran <surah>:<ayah>"
    elif book_name in _PLATO_STEPHANUS_RANGES:
        first, last = _PLATO_STEPHANUS_RANGES[book_name]
        hint = f"Stephanus {first}–{last} · e.g. !verse {book_name} {first}"
    elif book_name in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[book_name]
        hint = f"Daf {first}–{last} · e.g. !verse {book_name} 2a  or  {book_name} 2a:3"
    elif book_name in _MISHNAH_RANGES:
        chaps, total = _MISHNAH_RANGES[book_name]
        hint = f"Chapters 1–{chaps} · {total} mishnayot · e.g. !verse {book_name} 1:1"
    elif book_name in _CITATION_HINTS:
        hint = _CITATION_HINTS[book_name]
    elif book_name in _ANE_SINGLE_BOOKS:
        count, unit = _ANE_SINGLE_BOOKS[book_name]
        # derive the short command keyword
        _ane_keywords = {
            "The Great Hymn to the Aten": "Aten",
            "Book of the Dead":           "Book of the Dead",
            "The Leiden Hymns":           "Leiden Hymns",
            "The Instruction of Amenemope": "Amenemope",
            "The Book of Two Ways":       "Two Ways",
            "The Story of Ahikar":        "Ahikar",
        }
        kw = _ane_keywords.get(book_name, book_name)
        hint = f"{count} {unit}s · !verse {kw} 1 through !verse {kw} {count}"
    elif book_name in _HADITH_BOOKS:
        key = _HADITH_DISPLAY_TO_KEY.get(book_name)
        if key:
            total = _HADITH_COUNTS.get(key, "?")
            books = _HADITH_BOOK_COUNTS.get(key, 1)
            books_str = f" across {books} books" if books > 1 else ""
            hint = f"Hadiths 1–{total:,}{books_str} · !verse {book_name} 1"
        else:
            hint = f"!verse {book_name} 1  (hadith number)"
    elif book_name in _YERUSHALMI_BOOKS:
        tractate = book_name.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate, "?")
        hint = f"Chapters 1–{chaps} · !verse Jerusalem Talmud {tractate} 1:1  (ch:halakhah)"
    elif book_name in _TOSEFTA_BOOKS:
        tractate = book_name.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        chaps = base[0] if base else "?"
        hint = f"Chapters 1–{chaps} · !verse Tosefta {tractate} 1:1  (ch:halakhah)"
    elif book_name in _TARGUM_BOOKS:
        chaps = _TARGUM_CHAPTERS.get(book_name, "?")
        hint = f"Chapters 1–{chaps} · !verse {book_name} 1:1  (chapter:verse)"
    elif book_name in _MIDRASH_BOOKS:
        secs = _MIDRASH_SECTIONS.get(book_name, "?")
        hint = f"Sections 1–{secs} · !verse {book_name} 1:1  (section:subsection)"
    elif book_name in _ZOHAR_BOOKS:
        parasha = book_name.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha, "?")
        hint = f"Segments 1–{max_seg} · !verse Zohar {parasha} 1  (segment number)"
    elif book_name in _MISHNEH_TORAH_BOOKS:
        chaps = _MISHNEH_TORAH_SECTIONS[book_name]
        hint = f"Chapters 1–{chaps} · !verse {book_name} 1:1  (chapter:halacha)"
    elif book_name == "Guide for the Perplexed":
        hint = "3 parts · !verse Guide for the Perplexed 1:1  (part:chapter)"
    elif book_name == "Tanya":
        hint = (
            "5 parts · cite as `!verse Tanya <part>:<chapter>`\n"
            "e.g. `!verse Tanya 1:5` (Likkutei Amarim ch. 5) · "
            "`!verse Tanya 2:1` (Shaar HaYichud ch. 1)"
        )
    elif book_name in _OTHER_KABBALAH_BOOKS:
        chaps = _KABBALAH_CHAPTERS.get(book_name, "?")
        hint = f"Chapters 1–{chaps} · !verse {book_name} 1:1  (chapter:verse)"
    elif book_name == "Zohar":
        hint = "!verse Zohar Bereshit 5  (parasha + segment number)"
    else:
        hint = f"!verse {book_name} <ch>:<v> · !verse {book_name} for a random verse"

    embed.set_footer(text=hint)
    return embed


def _book_label(item: str) -> str:
    """Return the display label for a book in the list view."""
    # Baal Cycle and Mu'allaqat entries from BOOKS_TREE
    if item.startswith("Baal ") and " — " in item:
        # "Baal 1 — Baal and Yamm (9 sections)" → show the title part
        parts = item.split(" — ", 1)
        return parts[1] if len(parts) > 1 else item
    if item.startswith("Muallaqat ") and " — " in item:
        parts = item.split(" — ", 1)
        return parts[1] if len(parts) > 1 else item
    # Quran surah entries: "Quran N — Name (English, Mv)"
    if item.startswith("Quran ") and " — " in item:
        # Show as "N. Name (English) — Mv" in the list
        m = re.match(r"Quran (\d+) — ([^(]+) \(([^,]+), (\d+)v\)", item)
        if m:
            num, arabic, english, verses = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
            return f"{num}. {arabic} · {english} · {verses}v"
        return item
    if item in _PLATO_STEPHANUS_RANGES:
        first, last = _PLATO_STEPHANUS_RANGES[item]
        return f"{item} ({first}–{last})"
    if item in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[item]
        return f"{item} ({first}–{last})"
    if item in _MISHNAH_RANGES:
        chaps, total = _MISHNAH_RANGES[item]
        return f"{item} ({chaps} ch., {total} m.)"
    if item in _YERUSHALMI_BOOKS:
        tractate = item.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate, "?")
        return f"{tractate} ({chaps} ch.)"
    if item in _TOSEFTA_BOOKS:
        tractate = item.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        return f"Tosefta {tractate} ({base[0]} ch.)" if base else f"Tosefta {tractate}"
    if item in _TARGUM_BOOKS:
        chaps = _TARGUM_CHAPTERS.get(item)
        return f"{item} ({chaps} ch.)" if chaps else item
    if item in _MIDRASH_BOOKS:
        secs = _MIDRASH_SECTIONS.get(item)
        return f"{item} ({secs} sec.)" if secs else f"{item}"
    if item in _ZOHAR_BOOKS:
        parasha = item.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha, "?")
        return f"{parasha} (1–{max_seg})"
    if item in _MISHNEH_TORAH_BOOKS:
        chaps = _MISHNEH_TORAH_SECTIONS[item]
        section = item.replace("Mishneh Torah, ", "")
        return f"{section} ({chaps} ch.)"
    if item == "Guide for the Perplexed":
        return "Guide for the Perplexed (3 parts, 179 ch.)"
    if item == "Tanya":
        return "Tanya (5 parts: 53+12+12+32+9 ch.)"
    if item in _OTHER_KABBALAH_BOOKS:
        chaps = _KABBALAH_CHAPTERS.get(item)
        return f"{item} ({chaps} ch.)" if chaps else f"{item}"
    if item in _ANE_SINGLE_BOOKS:
        count, unit = _ANE_SINGLE_BOOKS[item]
        return f"{item} ({count} {unit}s)"
    if item in _HADITH_BOOKS:
        key = _HADITH_DISPLAY_TO_KEY.get(item)
        if key:
            total = _HADITH_COUNTS.get(key, "?")
            books = _HADITH_BOOK_COUNTS.get(key, 1)
            books_str = f", {books} books" if books > 1 else ""
            return f"{item} (1–{total:,}{books_str})"
        return f"{item} (hadith)"
    n = lookup.chapter_count(item)
    if n:
        return f"{item} ({n} ch.)"
    return item


def _chapter_picker_embed(book_name: str, total: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"📖 {book_name}",
        description=f"{total} chapter{'s' if total != 1 else ''} — click one to read it here.",
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text=f"!verse {book_name} <ch> also works directly")
    return embed


def _books_embed(node, title: str, page: int = 0) -> discord.Embed:
    subcats = [item for item in node if isinstance(item, tuple)]
    strings = [item for item in node if isinstance(item, str)]
    # If node is all strings (e.g. list of saint names), paginate those
    if strings and not subcats:
        total_pages = max(1, (len(strings) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        page_items = strings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        lines = [_book_label(item) for item in page_items]
    else:
        total_pages = max(1, (len(subcats) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        page_items = subcats[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        lines = []
        for item in page_items:
            if isinstance(item, tuple):
                sub_name, sub_contents = item
                count = _count_leaves(sub_contents)
                lines.append(f"**{sub_name}** ({count})" if count > 1 else sub_name)
            else:
                lines.append(f"  {_book_label(item)}")

    footer = "!verse <book> for a random verse"
    if total_pages > 1:
        footer = f"Page {page+1}/{total_pages} · " + footer
    else:
        footer = "Click a category to expand it · " + footer

    embed = discord.Embed(
        title=f"📚 {title}",
        description="\n".join(lines) or "Nothing loaded yet.",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text=footer)
    return embed


def _find_node(tree, label: str):
    for item in tree:
        if isinstance(item, tuple):
            name, contents = item
            if name == label:
                return (name, contents)
            found = _find_node(contents, label)
            if found:
                return found
    return None


PAGE_SIZE = 16  # buttons per page (leaves 1 row for nav/back)

class BooksView(discord.ui.View):
    def __init__(self, stack: list, page: int = 0):
        super().__init__(timeout=120)
        self.stack = stack
        self.page = page
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        label, node, mode = self.stack[-1]

        # Chapter/section picker — leaf buttons fetch a chapter or hadith book
        if mode in ("verse", "hadith"):
            total_pages = max(1, (len(node) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(self.page, total_pages - 1))
            page_items = node[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            for i, chap_label in enumerate(page_items):
                btn = discord.ui.Button(
                    label=chap_label[:80],
                    style=discord.ButtonStyle.primary,
                    row=i // 4
                )
                btn.callback = self._make_chapter_fetch(label, node, page * PAGE_SIZE + i, mode)
                self.add_item(btn)
            self._add_nav(total_pages, page)
            if total_pages > 1:
                jump_btn = discord.ui.Button(label="🔢 Jump to chapter", style=discord.ButtonStyle.secondary, row=4)
                jump_btn.callback = self._make_jump_open(label, node, mode)
                self.add_item(jump_btn)
            return

        subcats = [item for item in node if isinstance(item, tuple)]
        strings = [item for item in node if isinstance(item, str)]

        # Pure string list — paginate; each one opens a chapter picker
        if strings and not subcats:
            total_pages = max(1, (len(strings) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(self.page, total_pages - 1))
            page_items = strings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            for i, book_name in enumerate(page_items):
                btn = discord.ui.Button(
                    label=book_name[:80],
                    style=discord.ButtonStyle.primary,
                    row=i // 4
                )
                btn.callback = self._make_book_open(book_name)
                self.add_item(btn)
        else:
            total_pages = max(1, (len(subcats) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(self.page, total_pages - 1))
            page_items = subcats[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

            # Content buttons (rows 0-3, 4 per row)
            for i, (sub_name, sub_contents) in enumerate(page_items):
                btn_label = sub_name
                for emoji in ("📖 ","👼 ","✡️ ","☪️ ","🏛️ ","📯 ","🌍 ","🔥 ","🧿 ","⛪ "):
                    btn_label = btn_label.replace(emoji, "")
                btn_label = btn_label[:80]
                btn = discord.ui.Button(
                    label=btn_label,
                    style=discord.ButtonStyle.primary,
                    row=i // 4
                )
                btn.callback = self._make_drill(sub_name, sub_contents)
                self.add_item(btn)

        self._add_nav(total_pages, page)

    def _add_nav(self, total_pages, page):
        # Nav row (row 4): Prev, page indicator, Next, Back
        if total_pages > 1:
            prev_btn = discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.secondary,
                row=4,
                disabled=(page == 0)
            )
            prev_btn.callback = self._go_prev
            self.add_item(prev_btn)

            page_btn = discord.ui.Button(
                label=f"{page + 1}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                row=4,
                disabled=True
            )
            self.add_item(page_btn)

            next_btn = discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.secondary,
                row=4,
                disabled=(page >= total_pages - 1)
            )
            next_btn.callback = self._go_next
            self.add_item(next_btn)

        if len(self.stack) > 1:
            back_btn = discord.ui.Button(
                label="◀ Back",
                style=discord.ButtonStyle.secondary,
                row=4
            )
            back_btn.callback = self._go_back
            self.add_item(back_btn)

    async def _open_book(self, interaction: discord.Interaction, book_name: str):
        """Push a chapter/section picker for this book, or fall back to the
        plain detail embed if it isn't chapter-browsable (one continuous work)."""
        options = chapter_options_for_book(lookup, book_name)
        if options is None:
            await interaction.response.edit_message(
                embed=_book_detail_embed(book_name), view=self
            )
            return
        labels, mode = options
        self.stack.append((book_name, labels, mode))
        self.page = 0
        self._rebuild()
        await interaction.response.edit_message(
            embed=_chapter_picker_embed(book_name, len(labels)), view=self
        )

    def _make_book_open(self, book_name: str):
        async def callback(interaction: discord.Interaction):
            await self._open_book(interaction, book_name)
        return callback

    def _make_chapter_fetch(self, book_name: str, chapter_labels: list[str], index: int, mode: str):
        chap_label = chapter_labels[index]

        async def callback(interaction: discord.Interaction):
            if mode == "hadith":
                await interaction.response.defer()
            result = fetch_chapter_result(lookup, get_hadith_section, book_name, chap_label, mode)
            nav_btns = _make_chapter_nav_buttons(book_name, chapter_labels, index, mode)
            await _send_result(interaction, result, extra_buttons=nav_btns)
        return callback

    def _make_jump_open(self, book_name: str, chapter_labels: list[str], mode: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_modal(_ChapterJumpModal(book_name, chapter_labels, mode))
        return callback

    def _make_drill(self, name, contents):
        async def callback(interaction: discord.Interaction):
            actual_contents = contents
            only_strings = all(isinstance(x, str) for x in contents)
            if only_strings:
                # If this is a single book name, open its chapter picker directly
                if len(contents) == 1:
                    await self._open_book(interaction, contents[0])
                    return
                # Look up works directly from loaded corpus data, bypassing tree
                from collections import defaultdict
                source_books = defaultdict(list)
                for corpus_data in lookup._data.values():
                    for book_name in corpus_data:
                        src = lookup._book_sources.get(book_name, "")
                        if src:
                            source_books[src].append(book_name)
                # Try exact match, then case-insensitive
                works = source_books.get(name) or source_books.get(name.lower())
                if not works:
                    for src_name, src_works in source_books.items():
                        if src_name.lower() == name.lower():
                            works = src_works
                            break
                if works and len(works) > len(contents):
                    actual_contents = sorted(works)
                # If the contents are a list of book names, add detail buttons
                if actual_contents and all(isinstance(x, str) for x in actual_contents):
                    self.stack.append((name, actual_contents, "tree"))
                    self.page = 0
                    self._rebuild()
                    await interaction.response.edit_message(
                        embed=_books_embed(actual_contents, name, page=0), view=self
                    )
                    return
            self.stack.append((name, actual_contents, "tree"))
            self.page = 0
            self._rebuild()
            await interaction.response.edit_message(embed=_books_embed(actual_contents, name, page=0), view=self)
        return callback

    def _current_embed(self) -> discord.Embed:
        label, node, mode = self.stack[-1]
        if mode in ("verse", "hadith"):
            return _chapter_picker_embed(label, len(node))
        return _books_embed(node, label, page=self.page)

    async def _go_prev(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction):
        self.page += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _go_back(self, interaction: discord.Interaction):
        self.stack.pop()
        self.page = 0
        self._rebuild()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass


class _ChapterJumpModal(discord.ui.Modal, title="Jump to chapter"):
    def __init__(self, book_name: str, chapter_labels: list[str], mode: str):
        super().__init__()
        self.book_name = book_name
        self.chapter_labels = chapter_labels
        self.mode = mode
        self.chapter_input = discord.ui.TextInput(
            label="Chapter",
            placeholder=f"e.g. {chapter_labels[0]}" if chapter_labels else "1",
            max_length=20,
        )
        self.add_item(self.chapter_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.chapter_input.value.strip()
        match = next((l for l in self.chapter_labels if l.lower() == raw.lower()), None)
        if match is None and self.mode == "hadith" and raw.isdigit():
            candidate = f"Book {raw}"
            match = candidate if candidate in self.chapter_labels else None
        if match is None:
            await interaction.response.send_message(
                f"⚠️ `{raw}` isn't a valid chapter for **{self.book_name}**. "
                f"Range: {self.chapter_labels[0]}–{self.chapter_labels[-1]}.",
                ephemeral=True,
            )
            return
        index = self.chapter_labels.index(match)
        if self.mode == "hadith":
            await interaction.response.defer()
        result = fetch_chapter_result(lookup, get_hadith_section, self.book_name, match, self.mode)
        nav_btns = _make_chapter_nav_buttons(self.book_name, self.chapter_labels, index, self.mode)
        await _send_result(interaction, result, extra_buttons=nav_btns)


def _author_works_node(author_name: str, fuzzy: bool = True) -> tuple | None:
    """
    Search loaded patristics data for an author by name (fuzzy).
    Returns (display_name, works_list) or None.
    """
    from difflib import get_close_matches
    from collections import defaultdict

    # Group patristics books by their source (author name)
    # Search all loaded corpora for author→works mapping
    source_books = defaultdict(list)
    for corpus_data in lookup._data.values():
        for book_name in corpus_data:
            src = lookup._book_sources.get(book_name, "")
            if src:
                source_books[src].append(book_name)

    # Collect tree author nodes (tuples with string-only children)
    def collect_tree_authors(tree):
        authors = {}
        for item in tree:
            if isinstance(item, tuple):
                name, contents = item
                has_strings = any(isinstance(x, str) for x in contents)
                has_tuples  = any(isinstance(x, tuple) for x in contents)
                if has_strings and not has_tuples:
                    authors[name] = contents
                else:
                    authors.update(collect_tree_authors(contents))
        return authors

    tree_authors = collect_tree_authors(BOOKS_TREE)
    all_names = list(tree_authors.keys()) + list(source_books.keys())
    query = author_name.strip()

    # Exact match (case-insensitive)
    for name in all_names:
        if name.lower() == query.lower():
            works = tree_authors.get(name) or source_books.get(name, [])
            return (name, works)

    # Fuzzy match
    if not fuzzy:
        return None
    matches = get_close_matches(query, all_names, n=1, cutoff=0.55)
    if matches:
        name = matches[0]
        works = tree_authors.get(name) or source_books.get(name, [])
        return (name, works)

    return None


def _book_by_name(query: str) -> "tuple[str, tuple | None] | None":
    """(book name, its chapter options -- None if it isn't chapter-browsable)
    for a book name or abbreviation, or None if it isn't one."""
    _, canon = lookup._resolve_book(query)
    options = chapter_options_for_book(lookup, canon or query)
    if canon is None and options is None:
        return None
    return (canon or query, options)


@bot.command(name="books")
async def list_books(ctx, *, section: str = ""):
    """Browse available scripture collections. Use !books <author> to list their works."""
    top_label = "Available Scripture"
    guild_id = getattr(getattr(ctx, "guild", None), "id", None)
    top_node, sections = tree_for(guild_id)

    if section.strip():
        # 1. Try BOOKS_TREE section match first
        found = _find_node(sections, section.strip())
        if found:
            label, node = found
            stack = [(top_label, top_node, "tree"), (label, node, "tree")]
            label, node, _mode = stack[-1]
            view = BooksView(stack)
            view.message = await ctx.send(embed=_books_embed(node, label), view=view)
        else:
            # 2. An author by name; a book by name before a merely similar author
            #    ("Genesis" is a book, not something like "Gellius")
            from scripture_lookup import ALIASES
            q = section.strip()
            exact_book = (lookup._resolve_book(q)[1] or "").lower() == q.lower() or q.lower() in ALIASES
            author_result = _author_works_node(q, fuzzy=False)
            if author_result is None and not exact_book:
                author_result = _author_works_node(q)
            if author_result and any(_hidden_book(guild_id, w) for w in _leaves(author_result[1])):
                author_result = None                         # (an author of a tradition the server hasn't)
            if author_result:
                author_name, works = author_result
                embed = discord.Embed(
                    title=f"📚 {author_name}",
                    color=discord.Color.dark_gold()
                )
                lines = []
                for work in works:
                    if isinstance(work, str):
                        lines.append(f"• **{_book_label(work)}**")
                    elif isinstance(work, tuple):
                        sub_name, sub_works = work
                        lines.append(f"**{sub_name}**")
                        for sw in sub_works:
                            if isinstance(sw, str):
                                lines.append(f"  · {_book_label(sw)}")
                embed.description = "\n".join(lines) or "No works found."
                embed.set_footer(text="!verse <work> <ch>:<v> to look up a passage")
                await ctx.send(embed=embed)
            elif (book := _book_by_name(section.strip())) is not None and not _hidden_book(guild_id, book[0]):
                # 3. A single book ("Genesis", "Jn", "Confessions"): straight to its chapters
                book_name, options = book
                if options is None:
                    await ctx.send(embed=_book_detail_embed(book_name))
                    return
                labels, mode = options
                view = BooksView([(top_label, top_node, "tree"), (book_name, labels, mode)])
                view.message = await ctx.send(embed=_chapter_picker_embed(book_name, len(labels)), view=view)
            else:
                await ctx.send(
                    f"**{section}** not found.\n"
                    f"Try `!books` for the full list, or `!books Augustine` to list an author's works."
                )
    else:
        stack = [(top_label, top_node, "tree")]
        label, node, _mode = stack[-1]
        view = BooksView(stack)
        view.message = await ctx.send(embed=_books_embed(node, label), view=view)


# ── !export — bundle a book/chapter range into a downloadable text file ─────────

def _export_chapters(book_name: str, labels: list[str]) -> tuple[str, str]:
    """Fetch and concatenate every mode string in `labels` for book_name into
    one text blob. Returns (text, mode). Runs off the event loop."""
    options = chapter_options_for_book(lookup, book_name)
    mode = options[1] if options else "verse"
    parts = []
    for label in labels:
        result = fetch_chapter_result(lookup, get_hadith_section, book_name, label, mode)
        if not result.get("found"):
            continue
        text = result.get("text", "")
        text = re.sub(r"\*\*\[(.+?)\]\*\*\s*", r"[\1] ", text)
        parts.append(f"{result.get('reference', f'{book_name} {label}')}\n\n{text}")
    return "\n\n\n".join(parts), mode


@bot.command(name="export")
async def cmd_export(ctx, *, arg: str = ""):
    """Bundle a book (or chapter range) into a downloadable text file.
    Usage: !export John          — whole book
           !export John 1-5      — chapters 1 through 5
           !export John 3        — single chapter"""
    arg = arg.strip()
    if not arg:
        await ctx.send("Usage: `!export <book>` or `!export <book> <start>-<end>` (e.g. `!export John 1-5`).")
        return

    m_range = re.match(r"^(.*?)\s+(\S+)-(\S+)$", arg)
    if m_range:
        book_raw, start, end = m_range.group(1), m_range.group(2), m_range.group(3)
    else:
        m_single = re.match(r"^(.*?)\s+(\S+)$", arg)
        if m_single:
            book_raw, start, end = m_single.group(1), m_single.group(2), m_single.group(2)
        else:
            book_raw, start, end = arg, None, None

    _, canon = lookup._resolve_book(book_raw)
    book_name = canon or book_raw

    options = chapter_options_for_book(lookup, book_name)
    if options is None:
        await ctx.send(
            f"⚠️ **{book_name}** isn't chapter-browsable, so there's nothing to bundle. "
            f"Try `!verse {book_name}` instead."
        )
        return
    labels, mode = options

    if start is not None:
        try:
            i1 = labels.index(start)
            i2 = labels.index(end)
        except ValueError:
            await ctx.send(
                f"⚠️ Couldn't find chapter **{start}** or **{end}** in **{book_name}**. "
                f"Range: {labels[0]}–{labels[-1]}."
            )
            return
        if i1 > i2:
            i1, i2 = i2, i1
        chosen = labels[i1:i2 + 1]
    else:
        chosen = labels

    limit = 20 if mode == "hadith" else 200
    if len(chosen) > limit:
        await ctx.send(
            f"That's {len(chosen)} {'hadith books' if mode == 'hadith' else 'chapters'} — "
            f"please narrow the range to {limit} or fewer at a time."
        )
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        text, _mode = await loop.run_in_executor(None, _export_chapters, book_name, chosen)

    if not text.strip():
        await ctx.send(f"⚠️ Couldn't fetch any content for **{book_name}**.")
        return

    buf = io.BytesIO(text.encode("utf-8"))
    filename = re.sub(r"[^\w\-]+", "_", book_name).strip("_") + ".txt"
    await ctx.send(
        f"📄 **{book_name}** — {len(chosen)} chapter(s) exported.",
        file=discord.File(buf, filename=filename)
    )
