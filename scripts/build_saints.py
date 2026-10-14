"""
Builds data/saints/saints.json: the saints of the traditional calendar, a day
at a time, for !saint.

    python scripts/build_saints.py

Butler: *Lives of the Saints*, abridged from Alban Butler (Benziger Brothers,
1894; sacred-texts.com calls it "Little Pictorial Lives of the Saints"), from
archive.sacred-texts.com/chr/lots. One or two saints for every day of the year,
each a short life and a "Reflection". The month comes from the order of the
index (its day numbers start again at 1 each month); the seven lives added at
the front of the book (American feasts and later canonisations) carry no date
there, so theirs are in ADDED_DATES, each checked against the life's own text
or the Catholic Encyclopedia.

The Golden Legend (already a corpus, data/medieval/golden_legend.json) adds the
traditional saints Butler's abridgement leaves out -- Christopher, Margaret...
-- and its medieval telling of those in both: GOLDEN_LEGEND maps its chapters
to their feast days.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_world_texts as W  # noqa: E402  (the cached archive.sacred-texts.com helpers)

OUT = ROOT / "data" / "saints" / "saints.json"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]

# lots002-008: no date in the index; each from its own text ("his feast is celebrated
# February 5th"). Teresa of the Infant Jesus and Joan of Arc don't give theirs, so they
# can be looked up by name but aren't on a day.
ADDED_DATES = {"chr/lots/lots002.htm": (2, 5), "chr/lots/lots003.htm": (4, 27), "chr/lots/lots004.htm": (7, 24),
               "chr/lots/lots007.htm": (5, 22), "chr/lots/lots008.htm": (2, 27)}

# The Golden Legend's chapters (by the start of their book name in golden_legend.json):
#   "B:<name>"   the same saint as Butler's on that day (month, day, words in Butler's name)
#   (m, d, why)  a saint Butler's abridgement hasn't: the day from the Catholic Encyclopedia
#                (1913) article ("CE"), or from the Legend's own text ("GL": "the thirteenth
#                kalends of August" = 20 July)
#   None         no day that could be checked: found by name, not on the calendar
# The Old Testament chapters, the history of the Lombards and the expositions are left out.
GOLDEN_LEGEND = [
    ("Andrew", "St. Andrew", "B", (11, 30, "Andrew, Apostle")),
    ("Nicholas the Bishop", "St. Nicholas", "B", (12, 6, "Nicholas of Bari")),
    ("Conception of Our Lady", "The Conception of Our Lady", "B", (12, 8, "Immaculate Conception")),
    ("Saints Gentian", "Sts. Fuscian, Victoricus and Gentian", None, None),
    ("Lucy", "St. Lucy", "B", (12, 13, "Lucy")),
    ("Nicasius", "St. Nicasius", "B", (12, 14, "Nicasius")),
    ("Thomas the Apostle", "St. Thomas the Apostle", "B", (12, 21, "Thomas, Apostle")),
    ("Anastasia", "St. Anastasia", "CE", (12, 25)),
    ("Eugenia", "St. Eugenia", None, None),
    ("Stephen Protomartyr", "St. Stephen", "B", (12, 26, "Stephen, First Martyr")),
    ("of S. John the Evangelist", "St. John the Evangelist", "B", (12, 27, "John, Evangelist")),
    ("Innocents", "The Holy Innocents", "B", (12, 28, "Innocents")),
    ("Thomas, martyr, of Canterbury", "St. Thomas of Canterbury", "B", (12, 29, "Thomas of Canterbury")),
    ("Silvester", "St. Sylvester", "B", (12, 31, "Sylvester")),
    ("Here followeth, the Life of S. Paul", "St. Paul the First Hermit", "B", (1, 15, "Paul, the First Hermit")),
    ("Remigius, and first", "St. Remigius", None, None),          # (his January feast; Butler has him on 1 October)
    ("the Invention of S. Firmin", "The Finding of St. Firmin", None, None),
    ("Macarias", "St. Macarius", None, None),
    ("Felix, said Inpincis", "St. Felix of Nola", "CE", (1, 14)),
    ("Marcel and", "St. Marcellus, Pope", "CE", (1, 16)),
    ("Anthony", "St. Antony", "B", (1, 17, "Antony, Patriarch")),
    ("Fabian", "St. Fabian, Pope", "CE", (1, 20)),
    ("Sebastian", "St. Sebastian", "B", (1, 20, "Sebastian")),
    ("of S. Agnes", "St. Agnes", "B", (1, 21, "Agnes")),
    ("life of S. Vincent", "St. Vincent", "B", (1, 22, "Vincent, Martyr")),
    ("Basil, Bishop", "St. Basil", "B", (6, 14, "Basil the Great")),
    ("John the Almoner", "St. John the Almoner", "B", (4, 9, "John the Almoner")),
    ("Conversion of S. Paul", "The Conversion of St. Paul", "B", (1, 25, "Conversion")),
    ("Pauline the Widow", "St. Paula", None, None),
    ("Julian, the bishop", "St. Julian of Le Mans", None, None),
    ("Ignatius bishop", "St. Ignatius of Antioch", "B", (2, 1, "Ignatius, Bishop")),
    ("Our Lady", "The Purification of Our Lady", "B", (2, 2, "Purification")),
    ("Blase", "St. Blaise", "B", (2, 3, "Blase")),
    ("Agatha", "St. Agatha", "B", (2, 5, "Agatha")),
    ("Amande", "St. Amand", "CE", (2, 6)),
    ("Vedaste", "St. Vedast", None, None),
    ("Valentine, and first", "St. Valentine", "B", (2, 14, "Valentine")),
    ("Valentine the Martyr", "St. Valentine the Martyr", "B", (2, 14, "Valentine")),
    ("Juliana", "St. Juliana", "GL", (2, 16)),                    # "the fourteenth calends of the month of March"
    ("Chairing of S. Peter", "The Chair of St. Peter", "B", (2, 22, "Chair at Antioch")),
    ("Matthias the Apostle", "St. Matthias", "B", (2, 24, "Matthias")),
    ("Longinus", "St. Longinus", None, None),
    ("Maur", "St. Maurus", "GL", (1, 15)),                        # "the eighteenth calends of February"
    ("Patrick", "St. Patrick", "B", (3, 17, "Patrick")),
    ("Benet the Abbot", "St. Benedict", "B", (3, 21, "Benedict, Abbot")),
    ("Cuthbert of Durham", "St. Cuthbert", None, None),
    ("The Annunciation", "The Annunciation", "B", (3, 25, "Annunciation")),
    ("Seconde, Knight", "St. Secundus", "GL", (3, 30)),           # "the third calends of April"
    ("life of Mary of Egypt", "St. Mary of Egypt", "B", (4, 9, "Mary of Egypt")),
    ("Ambrose", "St. Ambrose", "B", (12, 7, "Ambrose")),
    ("Alphage", "St. Alphege", "CE", (4, 19)),
    ("George, Martyr", "St. George", "B", (4, 23, "George")),
    ("Mark the Evangelist", "St. Mark", "B", (4, 25, "Mark, Evangelist")),
    ("Marcelin the Pope", "St. Marcellinus, Pope", "B", (4, 26, "Marcellinus")),
    ("Vital, Martyr", "St. Vitalis", "B", (4, 28, "Vitalis")),
    ("Peter of Milan", "St. Peter Martyr", "B", (4, 29, "Peter, Martyr")),
    ("Philip the Apostle", "St. Philip the Apostle", "B", (5, 1, "Philip and James")),
    ("James the Less", "St. James the Less", "B", (5, 1, "Philip and James")),
    ("invention of the Holy Cross", "The Finding of the Holy Cross", "B", (5, 3, "Discovery of the Holy Cross")),
    ("John Port Latin", "St. John before the Latin Gate", None, None),
    ("Gordian", "St. Gordian", "CE", (5, 10)),
    ("Nereus and Achilleus", "Sts. Nereus and Achilleus", "CE", (5, 12)),
    ("Pancrace", "St. Pancras", "CE", (5, 12)),
    ("Urban, and first", "St. Urban, Pope", "CE", (5, 25)),
    ("Pernelle", "St. Petronilla", "B", (5, 31, "Petronilla")),
    ("Dunstan", "St. Dunstan", "CE", (5, 19)),
    ("life of S. Aldhelm", "St. Aldhelm", "CE", (5, 25)),
    ("Austin that brought", "St. Augustine of Canterbury", "B", (5, 26, "Augustine, Apostle of England")),
    ("life of S. Germain", "St. Germanus of Paris", "B", (5, 28, "Germanus")),
    ("Peter the Exorcist", "St. Peter the Exorcist", None, None),
    ("Prime and Felician", "Sts. Primus and Felician", "B", (6, 9, "Primus and Felicianus")),
    ("Barnabas the Apostle", "St. Barnabas", "B", (6, 11, "Barnabas")),
    ("Vitus and Modestus", "Sts. Vitus and Modestus", "B", (6, 15, "Vitus")),
    ("Quirine and Juliet", "Sts. Quiricus and Julitta", "CE", (6, 16)),
    ("Life next of S. Marine", "St. Marina", "GL", (6, 18)),      # "the fourteenth kalends of July"
    ("lives of SS. Gervase", "Sts. Gervase and Protase", "CE", (6, 19)),
    ("life of S. Edward, King and Martyr", "St. Edward the Martyr", "CE", (3, 18)),
    ("Alban", "St. Alban", "CE", (6, 22)),
    ("John Baptist", "St. John the Baptist", "B", (6, 24, "John the Baptist")),
    ("Loye", "St. Eligius", "B", (12, 1, "Eligius")),
    ("William", "St. William of Bourges", "B", (1, 10, "William, Archbishop")),
    ("Eutrope", "St. Eutropius", "GL", (4, 30)),                  # "the day tofore the calends of May"
    ("Marcial", "St. Martial", "CE", (6, 30)),
    ("Genevieve", "St. Genevieve", "B", (1, 3, "Genevieve")),
    ("Maturin", "St. Mathurin", "GL", (11, 1)),                   # "the day of the calends of November"
    ("Victor, Martyr", "St. Victor", "B", (7, 21, "Victor")),
    ("John and S. Paul", "Sts. John and Paul", "B", (6, 26, "John and Paul")),
    ("Leo the Pope", "St. Leo the Great", "B", (4, 11, "Leo the Great")),
    ("Peter the Apostle", "St. Peter the Apostle", "B", (6, 29, "Peter, Apostle")),
    ("Paul the Apostle", "St. Paul the Apostle", "B", (6, 30, "Paul")),
    ("Seven Brethren", "The Seven Brothers", "B", (7, 10, "Seven Brothers")),
    ("Theodora", "St. Theodora", None, None),
    ("Swithin", "St. Swithin", "CE", (7, 15)),
    ("Kenelm", "St. Kenelm", None, None),
    ("glorious Life and passion", "St. Margaret", "B", (7, 20, "Margaret, Virgin and Martyr")),
    ("Praxede", "St. Praxedes", "CE", (7, 21)),
    ("life of S. Appollinaris", "St. Apollinaris", "B", (7, 23, "Apollinaris, Bishop and Martyr")),
    ("life of S. Christine", "St. Christina", None, None),
    ("James the More", "St. James the Greater", "B", (7, 25, "James, Apostle")),
    ("Christopher", "St. Christopher", "CE", (7, 25)),
    ("Lives Of the Seven Sleepers", "The Seven Sleepers", "CE", (7, 27)),
    ("Nazarien and Celsus", "Sts. Nazarius and Celsus", "B", (7, 28, "Nazarius")),
    ("Felix, and first", "St. Felix, Pope", "CE", (7, 29)),
    ("Martha", "St. Martha", "B", (7, 29, "Martha")),
    ("Abdon and Sennen", "Sts. Abdon and Sennen", "CE", (7, 30)),
    ("Germain, and first", "St. Germanus of Auxerre", "B", (7, 30, "Germanus")),
    ("Eusebius", "St. Eusebius of Vercelli", "B", (12, 16, "Eusebius, Bishop")),
    ("Seven Maccabees", "The Seven Maccabees", None, None),
    ("feast of S. Peter ad Vincula", "St. Peter in Chains", "GL", (8, 1)),   # "the first day of August"
    ("Stephen the Pope", "St. Stephen, Pope", "B", (8, 2, "Stephen, Pope")),
    ("Stephen, Promartyr", "The Finding of St. Stephen", "B", (8, 3, "Stephen's Relics")),
    ("Dominic", "St. Dominic", "B", (8, 4, "Dominic")),
    ("Sixtus", "St. Sixtus, Pope", "CE", (8, 6)),
    ("Donatus", "St. Donatus", None, None),
    ("Ciriacus", "St. Cyriacus", None, None),
    ("Laurence", "St. Laurence", "B", (8, 10, "Laurence, Martyr")),
    ("Hyppolitus", "St. Hippolytus", "CE", (8, 13)),
    ("Glorious Virgin our Lady", "The Assumption of Our Lady", "B", (8, 15, "Assumption")),
    ("Rocke", "St. Roch", "CE", (8, 16)),
    ("Bernard", "St. Bernard", "B", (8, 20, "Bernard")),
    ("Timothy", "St. Timothy", None, None),
    ("Symphorien", "St. Symphorian", "B", (8, 22, "Symphorian")),
    ("Bartholomew", "St. Bartholomew", "B", (8, 24, "Bartholomew")),
    ("Austin, or Augustine", "St. Augustine of Hippo", "B", (8, 28, "Augustine of Hippo")),
    ("Savien", "St. Savinian", None, None),
    ("Lowe", "St. Lupus", None, None),
    ("Mammertin", "St. Mamertinus", None, None),
    ("Giles", "St. Giles", "B", (9, 1, "Giles")),
    ("Blessed Lady", "The Nativity of Our Lady", "B", (9, 8, "Nativity of the Blessed Virgin")),
    ("Adrian, Martyr", "St. Adrian", None, None),
    ("Gorgone", "St. Gorgonius", "CE", (9, 9)),
    ("Prothus and Jacinctus", "Sts. Protus and Hyacinth", "CE", (9, 11)),
    ("Holy Cross", "The Exaltation of the Holy Cross", "B", (9, 14, "Exaltation")),
    ("John Chrysostom", "St. John Chrysostom", "B", (1, 27, "John Chrysostom")),
    ("Cornelius the Pope", "St. Cornelius, Pope", None, None),
    ("Eufemia", "St. Euphemia", None, None),
    ("Lambert", "St. Lambert", "B", (9, 17, "Lambert")),
    ("Matthew", "St. Matthew", "B", (9, 21, "Matthew")),
    ("Maurice", "St. Maurice", None, None),
    ("Justina", "St. Justina", "B", (9, 26, "Cyprian and Justina")),
    ("Cosmo and Damian", "Sts. Cosmas and Damian", "CE", (9, 27)),
    ("Forsey", "St. Fursey", None, None),
    ("feast of S. Michael", "St. Michael the Archangel", "B", (9, 29, "Michael, Archangel")),
    ("Jerome", "St. Jerome", "B", (9, 30, "Jerome, Doctor")),
    ("Remigius", "St. Remigius", "B", (10, 1, "Remigius")),
    ("Logier", "St. Leger", None, None),
    ("Francis, first beginner", "St. Francis of Assisi", "B", (10, 4, "Francis of Assisi")),
    ("Pelagienne", "St. Pelagia", "GL", (10, 8)),                 # "the eighth day of October"
    ("Margaret, said Pelagien", "St. Margaret called Pelagius", None, None),
    ("Thais", "St. Thais", "CE", (10, 8)),
    ("Denis", "St. Denis", "B", (10, 9, "Dionysius")),
    ("Calixtus", "St. Callistus, Pope", None, None),
    ("Edward, King and Confessor", "St. Edward the Confessor", "B", (10, 13, "Edward the Confessor")),
    ("Luke the Evangelist", "St. Luke", "B", (10, 18, "Luke")),
    ("Crisaunt", "Sts. Chrysanthus and Daria", "CE", (10, 25)),
    ("Eleven Thousand Virgins", "St. Ursula and the Eleven Thousand Virgins", None, None),
    ("of the SS. Crispin", "Sts. Crispin and Crispinian", "B", (10, 25, "Crispin")),
    ("of the Holy Apostles Simon", "Sts. Simon and Jude", "B", (10, 28, "Simon and Jude")),
    ("Quintin", "St. Quentin", "B", (10, 31, "Quintin")),
    ("Eustace", "St. Eustace", None, None),
    ("All Hallows", "All Saints", "B", (11, 1, "All-Saints")),
    ("All Souls", "All Souls", "B", (11, 2, "All-Souls")),
    ("life of S. Winifred", "St. Winifred", "CE", (11, 3)),
    ("Leonard", "St. Leonard", "B", (11, 6, "Leonard")),
    ("of the Four Crowned Martyrs", "The Four Crowned Martyrs", "CE", (11, 8)),
    ("Theodore", "St. Theodore", "B", (11, 9, "Theodore")),
    ("Martin", "St. Martin of Tours", "B", (11, 11, "Martin of Tours")),
    ("Brice", "St. Brice", None, None),
    ("life of the Holy Virgin S. Clare", "St. Clare", "B", (8, 12, "Clare")),
    ("Barbara", "St. Barbara", "B", (12, 4, "Barbara")),
    ("Alexis", "St. Alexis", "B", (7, 17, "Alexius")),
    ("Elizabeth", "St. Elizabeth of Hungary", "B", (11, 19, "Elizabeth of Hungary")),
    ("Edmund, Confessor", "St. Edmund of Canterbury", "B", (11, 16, "Edmund of Canterbury")),
    ("Hugh, Bishop", "St. Hugh of Lincoln", "CE", (11, 17)),
    ("Edmund, King and Martyr", "St. Edmund the Martyr", "CE", (11, 20)),
    ("Cecilia", "St. Cecilia", "B", (11, 22, "Cecilia")),
    ("Clement, Pope", "St. Clement", "B", (11, 23, "Clement")),
    ("Grysogone", "St. Chrysogonus", "CE", (11, 24)),
    ("Katherine", "St. Katherine of Alexandria", "B", (11, 25, "Catherine of Alexandria")),
    ("Saturnine", "St. Saturninus", "B", (11, 29, "Saturninus")),
    ("James the Martyr", "St. James the Martyr", "GL", (11, 27)),  # "the fifth kalends of December"
    ("holy and venerable priest Bede", "The Venerable Bede", "B", (5, 27, "Bede")),
    ("Dorothy", "St. Dorothy", "B", (2, 6, "Dorothy")),
    ("Brandon", "St. Brendan", "CE", (5, 16)),
    ("Erkenwold", "St. Erkenwald", "CE", (11, 14)),
    ("of the holy Abbot Pastor", "The Abbot Pastor", None, None),
    ("of the Abbot John", "The Abbot John", None, None),
    ("of the Abbot Moses", "The Abbot Moses", None, None),
    ("Arsenius", "St. Arsenius", "CE", (7, 19)),
    ("of the Abbot Agathon", "The Abbot Agathon", None, None),
    ("of Barlaam the Hermit", "Sts. Barlaam and Josaphat", "CE", (11, 27)),
    ("Simeon", "St. Simeon", None, None),
    ("Polycarp", "St. Polycarp", "B", (1, 26, "Polycarp")),
    ("Quiriacus", "St. Quiriacus", "GL", (5, 4)),                 # "the fourth nones of May"
    ("life of S. Thomas Aquinas", "St. Thomas Aquinas", "B", (3, 7, "Thomas Aquinas")),
    ("life of S. Gaius", "St. Gaius", None, None),
    ("Arnold", "St. Arnold", "GL", (7, 16)),                      # "is celebrated the seventeenth day of the kalends of August"
    ("life of S. Tuien", "St. Tuien", None, None),
    ("Fiacre", "St. Fiacre", "CE", (8, 30)),
    ("Justin", "St. Justin", None, None),
    ("Demetrius", "St. Demetrius", "GL", (10, 8)),                # "is celebrated the eighth ides of the month of October"
    ("Rigobert", "St. Rigobert", None, None),
    ("Landry", "St. Landry", None, None),
    ("Mellonin", "St. Mellon", "GL", (10, 22)),                   # "the eleventh day of the kalends of the month of November"
    ("Ives", "St. Ives", "GL", (5, 19)),                          # "the nineteenth day of May"
    ("Morant", "St. Morant", None, None),
    ("Louis, King of France", "St. Louis, King of France", "B", (8, 25, "Louis, King")),
    ("Louis of Marseilles", "St. Louis of Toulouse", "B", (8, 19, "Louis, Bishop")),
    ("Aldegonde", "St. Aldegund", "CE", (1, 30)),
    ("Albine", "St. Albinus", "B", (3, 1, "Albinus")),
]


def page_text(path: str) -> str:
    """A page's text. Not W.st_page: its footnote-marker cleanup takes the day out of
    dates ("his feast is February 27" -> "February"), and these pages have no footnotes."""
    text = W._html_text(W.sacred_text(path))
    nav = list(re.finditer(r"(?m)^\s*Next\s*$", text[:3000]))
    text = text[nav[0].end() if nav else 0:]
    text = re.split(r"(?m)^\s*(?:Next: .*|Sacred Texts \|.*)\s*$", text)[0]
    text = re.sub(r"(?m)^\s*p\. [\divxlc]+\s*$|\[paragraph continues\]", "", text)
    text = re.sub(r"(?m)^[^\n]*?\bat sacred-texts\.com\s*", "", text)
    text = re.sub(r"\s+p\. \d+(?=\s|$)", "", text).replace("\xa0", " ")
    return re.sub(r"\n[ \t]*\n(?=[ \t]*[a-z])", "\n", text).strip()


def butler() -> list:
    entries = []
    month, last_day = 0, 99
    for path, label in W.st_index("chr/lots/index.htm"):
        m = re.match(r"^(\d+)[.:]\s+(.*)$", label)          # ("10: St. Andrew Avellino")
        n = int(re.search(r"lots(\d+)\.htm", path).group(1)) if re.search(r"lots(\d+)\.htm", path) else 0
        if m:
            day = int(m.group(1))
            if day < last_day:
                month += 1                             # the day numbers start again: a new month
            last_day = day
            date = (month, day)
            name = m.group(2)
        elif 2 <= n <= 8:
            date, name = ADDED_DATES.get(path), label
        else:
            continue
        text = page_text(path)
        head, _, body = text.partition("\n")
        parts = re.split(r"\s*Reflection\.\s*(?:—|--|-)\s*", body, maxsplit=1)    # (some have "--")
        life, reflection = parts[0], parts[1] if len(parts) > 1 else ""
        entries.append({"month": date[0] if date else None, "day": date[1] if date else None,
                        "name": name.strip(), "heading": re.sub(r"\s+", " ", head).strip(),
                        "life": re.sub(r"[ \t]+", " ", life).strip(),
                        "reflection": re.sub(r"[ \t]+", " ", reflection).strip(),
                        "source": "butler", "page": path.rsplit("/", 1)[1]})
    return entries


def golden_legend(saints: list) -> None:
    """Add the Golden Legend's saints: to Butler's entry when it's the same saint, else their own."""
    keys = list(json.loads((ROOT / "data" / "medieval" / "golden_legend.json").read_text(encoding="utf-8"))["books"])
    at = 0
    for prefix, name, kind, date in GOLDEN_LEGEND:
        # the table follows the book's order, so each prefix is looked for after the last match
        found = next((i for i in range(at, len(keys)) if keys[i] == prefix), None)
        if found is None:
            found = next(i for i in range(at, len(keys)) if keys[i].startswith(prefix))
        key, at = keys[found], found + 1
        if kind == "B":
            month, day, words = date
            match = [s for s in saints if (s["month"], s["day"]) == (month, day) and words in s["name"]]
            if len(match) != 1:
                raise SystemExit(f"Butler has {len(match)} for {words!r} on {month}/{day}")
            match[0].setdefault("golden_legend", []).append(key)
            if name not in match[0].setdefault("also", []):
                match[0]["also"].append(name)              # (so "!saint Katherine" finds Butler's Catherine)
        else:
            saints.append({"month": date[0] if date else None, "day": date[1] if date else None, "name": name,
                           "golden_legend": [key], "source": "golden_legend", "date_from": kind})


def main():
    saints = butler()
    golden_legend(saints)
    undated = [s["name"] for s in saints if s["month"] is None]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    saints.sort(key=lambda s: (s["month"] or 13, s["day"] or 0, s["source"] != "butler"))
    OUT.write_text(json.dumps({"source": "Alban Butler, Lives of the Saints (abridged; Benziger Brothers, 1894); "
                                         "the Golden Legend (Caxton's translation)",
                               "saints": saints}, ensure_ascii=False, indent=1), encoding="utf-8")
    gl = sum(1 for s in saints if s.get("golden_legend"))
    print(f"{len(saints)} saints ({gl} with a Golden Legend life); not on a day: {len(undated)}")


if __name__ == "__main__":
    main()
