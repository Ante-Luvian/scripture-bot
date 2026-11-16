"""The Glossa Ordinaria in English (scripts/build_glossa.py, data/patristics/glossa_ordinaria.json)."""
import json
import re

from core import ROOT

DATA = json.loads((ROOT / "data" / "patristics" / "glossa_ordinaria.json").read_text(encoding="utf-8"))
ENGLISH = ROOT / "scripts" / "glossa" / "english"


def test_jonah_on_the_kjvs_numbering():
    """The Vulgate's Jonah 2:1 (the fish) is the KJV's 1:17; its 2:2-11 the KJV's 2:1-10."""
    jonah = DATA["books"]["Glossa Ordinaria on Jonah"]
    assert jonah["1"]["17"].startswith("**“Now the Lord prepared a great fish")
    assert "2" in jonah and "11" not in jonah["2"] and "10" in jonah["2"]
    assert jonah["1"]["1"].startswith("**“And it came to pass”**\n• The conjunction “and” joins this")


def test_each_phrase_once_short_notes_first():
    """Every note on the same words goes under one heading, the interlinear ones before the margin's."""
    for book in DATA["books"].values():
        for ch, verses in book.items():
            for v, text in verses.items():
                heads = re.findall(r"^\*\*“(.+?)”\*\*", text, re.M)
                assert len(heads) == len(set(heads)), (ch, v)
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert "**“Because Israel was a child”**\n• he sets out the benefits" in hosea["11"]["1"]


def test_hosea_notes_follow_their_words_across_a_split_verse():
    """The Vulgate's Hosea 11:1 begins with the end of KJV 10:15, its 6:1 with the end of KJV 5:15."""
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert "As the morning" not in hosea["11"]["1"] and "**“As the morning”**" in hosea["10"]["15"]
    assert "Matthew uses this testimony" in hosea["11"]["1"]
    assert "In their affliction" not in hosea["6"]["1"] and "**“In their affliction”**" in hosea["5"]["15"]
    assert "salvation is promised on the third day" in hosea["6"]["2"]


def test_hosea_on_the_kjvs_numbering():
    """The Vulgate's Hosea 14:1 (Samaria perishes) is the KJV's 13:16, its 14:2-10 the KJV's 14:1-9; its 6:2-3 the KJV's
    6:1-2; its 2:24 the end of the KJV's 2:23."""
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert len(hosea) == 14 and "10" not in hosea["14"] and "24" not in hosea["2"]
    assert hosea["13"]["16"].count("Let Samaria perish") >= 1
    assert "Return, O Israel" in hosea["14"]["1"] and "Who is wise" in hosea["14"]["9"]
    assert "he hath taken us" in hosea["6"]["1"] and "He will revive us" in hosea["6"]["2"]
    assert "Thou art my people" in hosea["2"]["23"]


STOP = set("the and that this with from them they their shall will have hath unto upon thee thou thy your you which into "
           "were what when there for not but his her him all are was".split())
# Phrases checked by hand that do belong where they are, though their words look more like a neighbouring verse's
# (the Douay-Rheims and the KJV word it differently, or the edition files a note introducing the next verse there)
CHECKED = {("Hosea", "7", "7", "They were all heated like an oven"), ("Hosea", "13", "11", "I will give thee a king"),
           ("Hosea", "11", "10", "because I am God, and not man: the holy one in the midst of thee, and I will not "
                                 "enter into the city"),
           ("Joel", "1", "17", "The beasts have rotted in their dung"), ("Joel", "2", "8", "yea, and … through the windows"),
           ("Joel", "3", "9", "rouse up the strong"), ("Jonah", "1", "6", "and said to him: Why art thou fast asleep?"),
           ("Jonah", "4", "9", "And the Lord said"),
           ("Amos", "1", "5", "and … shall be carried away"), ("Amos", "3", "11", "and … shall be taken away from thee"),
           ("Amos", "6", "1", "ye great men, heads of the people"), ("Obadiah", "1", "13", "Neither shalt thou enter"),
           ("Micah", "7", "14", "according to the days of old"),
           ("Habakkuk", "2", "6", "and it shall be said: Woe to him that heapeth together that which is not his own"),
           ("Habakkuk", "2", "19", "there is no … in the bowels thereof"),
           ("Zephaniah", "3", "19", "and I will get them praise, and a name"),
           ("Zechariah", "11", "11", "And it was made void in that day"),
           ("Zechariah", "13", "1", "and of the unclean woman"),
           ("Zechariah", "13", "8", "shall be scattered, and shall perish"),
           ("Zechariah", "14", "8", "And it shall come to pass in that day"),
           ("Malachi", "2", "12", "The Lord will cut off the man that hath done this"),
           ("Ruth", "2", "2", "that escape the hands of the reapers"),
           # the Song: the DR's words differ from the KJV's where its verses split differently
           ("Song of Solomon", "1", "4", "to the odour of thy ointments"),
           ("Song of Solomon", "1", "11", "chains of gold"),
           ("Song of Solomon", "2", "10", "Behold my beloved"),
           ("Song of Solomon", "3", "4", "and I will not let him go, till I bring"),
           ("Song of Solomon", "5", "1", "with my aromatical spices"),
           ("Song of Solomon", "6", "1", "thy beloved, O thou most beautiful"),
           ("Song of Solomon", "7", "8", "and the odour of thy mouth"),
           # speaker labels for the next verse, hung on the last words of the one before
           ("Song of Solomon", "3", "6", "till she please"),
           ("Song of Solomon", "8", "14", "make me hear thy voice"),
           # Lamentations: the DR's wording differs from the KJV's ("Vide Domine" is one lemma for 1:9's "behold, O
           # Lord" and 1:11's "see, O Lord")
           ("Lamentations", "1", "7", "the enemies have seen her"), ("Lamentations", "1", "11", "behold, O Lord"),
           ("Lamentations", "1", "12", "for he hath made a vintage of me"),
           ("Lamentations", "2", "19", "give praise in the night"),
           ("Lamentations", "3", "31", "he shall be filled with reproaches"),
           ("Lamentations", "3", "32", "Caph. For if he hath cast off"),
           ("Lamentations", "4", "4", "the little ones have asked"),
           # Esther: the DR's wording differs from the KJV's
           ("Esther", "8", "1", "king Assuerus gave"),
           ("Esther", "9", "1", "and to revenge themselves"),
           # Ecclesiastes: the DR's wording differs from the KJV's
           ("Ecclesiastes", "1", "10", "Nothing under the sun is new"),
           ("Ecclesiastes", "1", "10", "neither is any man able to say"),
           ("Ecclesiastes", "2", "11", "And when I turned myself"),
           ("Ecclesiastes", "2", "15", "And speaking with my own mind, I perceived that this"),
           ("Ecclesiastes", "3", "20", "and into earth they return together"),
           ("Ecclesiastes", "7", "14", "enjoy good things"), ("Ecclesiastes", "10", "1", "than a small"),
           # Proverbs: the DR's wording differs from the KJV's ...
           ("Proverbs", "1", "3", "To understand the words of prudence"),
           ("Proverbs", "2", "4", "If thou shalt seek her as money"),
           ("Proverbs", "2", "4", "and shalt dig for her as for a treasure"),
           ("Proverbs", "6", "10", "Thou wilt sleep"),
           ("Proverbs", "9", "4", "let him come to me. And to the unwise she said"),
           ("Proverbs", "12", "13", "draweth nigh to the evil man"),
           ("Proverbs", "12", "16", "but he that dissembleth injuries is wise"),
           ("Proverbs", "13", "21", "and to the just … shall be repaid"),
           ("Proverbs", "14", "17", "folly: and the crafty man"),
           ("Proverbs", "30", "2", "I am the most foolish of men, and the wisdom of men is not with me"),
           # ... and the Vulgate adds lines the KJV lacks (4:27 "he will bring forward thy ways in peace"; 15:5 "In
           # abundant justice there is the greatest strength")
           ("Proverbs", "4", "27", "thy ways in peace"),
           ("Proverbs", "15", "5", "of the wicked shall be rooted out"),
           # Isaiah: the DR's wording differs from the KJV's (each phrase checked to be in the Douay-Rheims's own
           # verse of that number, where the KJV divides the verses alike)
           ("Isaiah", "1", "15", "I will turn away my eyes"), ("Isaiah", "3", "22", "Fine linen"),
           ("Isaiah", "5", "14", "and their strong ones shall go down"),
           ("Isaiah", "5", "14", "and their people, and their high"),
           ("Isaiah", "7", "23", "shall become thorns and briers"),
           ("Isaiah", "10", "9", "Are not my princes as so many kings? is not Calano as Charcamis"),
           ("Isaiah", "10", "29", "They have passed in haste"),
           ("Isaiah", "11", "3", "And he shall be filled with the spirit of the fear"),
           ("Isaiah", "12", "2", "and my praise, the Lord God"),
           ("Isaiah", "13", "22", "And owls shall answer one another"), ("Isaiah", "14", "11", "is fallen down"),
           ("Isaiah", "14", "31", "is thrown down"), ("Isaiah", "16", "9", "the voice of the treaders"),
           ("Isaiah", "17", "10", "thy strong helper"), ("Isaiah", "17", "13", "shall make a noise"),
           ("Isaiah", "19", "4", "I will deliver Egypt"), ("Isaiah", "20", "4", "the captivity of Ethiopia"),
           ("Isaiah", "25", "8", "He shall cast down headlong"),
           ("Isaiah", "29", "2", "And I will make a trench about"),
           ("Isaiah", "29", "6", "And it shall be at an instant suddenly"),
           ("Isaiah", "32", "18", "in the beauty of peace"),
           ("Isaiah", "40", "18", "or what image will you make for him?"),
           ("Isaiah", "41", "18", "I will turn the desert"), ("Isaiah", "42", "11", "give praise"),
           ("Isaiah", "43", "22", "neither hast thou laboured"), ("Isaiah", "43", "22", "Neither hast thou laboured"),
           ("Isaiah", "43", "25", "I am he that blot out thy iniquities"),
           ("Isaiah", "44", "20", "Part thereof is ashes"), ("Isaiah", "47", "8", "now hear these things"),
           ("Isaiah", "48", "12", "Whom I call"), ("Isaiah", "49", "17", "Thy builders are come"),
           ("Isaiah", "51", "5", "the islands shall look for me"),
           ("Isaiah", "52", "14", "As many have been astonished"),
           ("Isaiah", "52", "14", "As many have been astonished at thee"), ("Isaiah", "57", "9", "Thou hast sent"),
           ("Isaiah", "57", "9", "wast debased"), ("Isaiah", "58", "1", "their wicked doings"),
           ("Isaiah", "58", "10", "When thou shalt pour out"), ("Isaiah", "58", "10", "shalt satisfy"),
           ("Isaiah", "59", "5", "and the webs of spiders"), ("Isaiah", "60", "19", "Thou shalt no more have"),
           ("Isaiah", "63", "3", "I have stained all my apparel"),
           ("Isaiah", "65", "14", "Behold my servants shall rejoice"), ("Isaiah", "66", "3", "All these things"),
           ("Isaiah", "66", "4", "and have chosen the things that displease me"),
           ("Isaiah", "66", "12", "you shall be carried at the breasts"),
           ("Isaiah", "66", "12", "You shall be carried at the breasts"),
           # Jeremiah, Ezekiel, Daniel: each under the verse whose Douay words it has; the KJV words it differently
           ("Jeremiah", "3", "9", "And played the harlot"),
           ("Ezekiel", "3", "19", "But if thou give warning"),
           ("Jeremiah", "4", "6", "Strengthen yourselves"),
           ("Jeremiah", "8", "5", "is turned away"),
           ("Jeremiah", "10", "12", "He that maketh the earth"),
           ("Jeremiah", "10", "15", "They are vain things"),
           ("Jeremiah", "12", "13", "they have received an inheritance"),
           ("Jeremiah", "14", "4", "the husbandmen were confounded"),
           ("Jeremiah", "15", "19", "and if thou wilt separate"),
           ("Jeremiah", "17", "22", "And do not bring burdens"),
           ("Jeremiah", "22", "16", "was it not therefore because he knew me"),
           ("Jeremiah", "25", "38", "the fierce anger of the Lord"),
           ("Jeremiah", "31", "9", "and I will bring them back in mercy"),
           ("Jeremiah", "32", "40", "and will not cease to do them good: and I will give my fear in their heart"),
           ("Jeremiah", "32", "40", "and I will give my fear"),
           ("Jeremiah", "50", "27", "Destroy all her valiant men"),
           ("Ezekiel", "1", "14", "like flashes of lightning"),
           ("Ezekiel", "1", "18", "The wheels had also a size"),
           ("Ezekiel", "1", "25", "from above the firmament"),
           ("Ezekiel", "3", "7", "of a hard forehead"),
           ("Ezekiel", "3", "8", "harder than their foreheads"),
           ("Ezekiel", "3", "9", "I have made thy face"),
           ("Ezekiel", "13", "21", "And I will tear your pillows"),
           ("Ezekiel", "14", "3", "shall I answer when they inquire of me"),
           ("Ezekiel", "16", "16", "thou hast made thee"),
           ("Ezekiel", "16", "17", "And thou tookest thy beautiful vessels"),
           ("Ezekiel", "16", "36", "whom thou gavest them"),
           ("Ezekiel", "16", "55", "And thy sister Sodom"),
           ("Ezekiel", "17", "20", "and will judge him there for the transgression by which he hath despised me"),
           ("Ezekiel", "18", "7", "hath taken nothing away"),
           ("Ezekiel", "18", "11", "Though he doth not all these things"),
           ("Ezekiel", "19", "5", "of her young lions"),
           ("Ezekiel", "20", "27", "Moreover in this also"),
           ("Ezekiel", "20", "32", "come to pass, by which you say"),
           ("Ezekiel", "22", "20", "and in my wrath, and will take my rest"),
           ("Ezekiel", "24", "5", "the seething thereof is boiling hot"),
           ("Ezekiel", "24", "12", "thereof, not even"),
           ("Ezekiel", "26", "18", "the ships in the day of thy terror"),
           ("Ezekiel", "26", "21", "I will bring thee to nothing"),
           ("Ezekiel", "27", "4", "and situate in the heart of the sea, thy neighbours"),
           ("Ezekiel", "27", "7", "were made thy covering"),
           ("Ezekiel", "27", "17", "they set forth in thy fairs"),
           ("Ezekiel", "28", "12", "Thou wast the seal of resemblance"),
           ("Ezekiel", "28", "12", "Thou wast the seal"),
           ("Ezekiel", "30", "14", "the land of Phatures"),
           ("Ezekiel", "32", "6", "upon the mountains and the valleys shall be filled with thee"),
           ("Ezekiel", "32", "23", "in the lowest parts"),
           ("Ezekiel", "34", "5", "And my sheep were scattered"),
           ("Ezekiel", "36", "34", "which before was waste"),
           ("Ezekiel", "38", "22", "and upon his army, and upon the many nations that are with him"),
           ("Ezekiel", "40", "17", "on every side"),
           ("Ezekiel", "40", "19", "to the east, and to the north"),
           ("Ezekiel", "41", "26", "and the breadth of the walls"),
           ("Ezekiel", "42", "6", "fifty cubits from the ground"),
           ("Ezekiel", "45", "2", "it shall be holy on every side"),
           ("Ezekiel", "47", "10", "a very great multitude"),
           ("Ezekiel", "48", "11", "The sanctuary shall be for the priests"),
           ("Ezekiel", "48", "18", "ten thousand toward the east, and ten thousand"),
           ("Song of the Three Children", "1", "9", "thou hast delivered us"),
           ("Daniel", "2", "4", "And the Chaldeans answered"),
           ("Daniel", "2", "6", "But if you tell the dream and its interpretation"),
           ("Daniel", "2", "15", "why so cruel a sentence was gone forth from the face of the king"),
           ("Daniel", "2", "28", "what is to come to pass"),
           ("Daniel", "2", "38", "and hath put all things under thy power"),
           ("Daniel", "6", "4", "With regard to the king"),
           ("Daniel", "7", "24", "bring down."),
           ("Daniel", "9", "7", "but to us confusion of face"),
           ("Daniel", "9", "7", "for their iniquities by which they have sinned"),
           ("Daniel", "10", "3", "the days of three weeks"),
           ("Daniel", "11", "5", "And the king of the south shall be strengthened"),
           ("Daniel", "11", "8", "shall prevail against the king of the north."),
           ("Daniel", "11", "20", "And there shall stand up in his place, one most vile, and unworthy of kingly honour"),
           ("Daniel", "11", "37", "for he shall rise up against all things"),
           # Wisdom: the DR's wording differs from the KJV's
           ("Wisdom of Solomon", "3", "5", "because God hath tried them"),
           ("Wisdom of Solomon", "8", "6", "who … of those things"),
           ("Wisdom of Solomon", "10", "6", "from the wicked that were perishing"),
           ("Wisdom of Solomon", "11", "6", "thou gavest … to the unjust"),
           ("Wisdom of Solomon", "15", "18", "things without sense"),
           # Sirach: the DR's wording differs from the KJV's (each compared with both verses by hand)
           *{("Sirach", c, v, head) for c, v, head in (
               ("1", "22", "For he that is without fear"), ("4", "5", "Turn not away … from the poor"),
               ("4", "11", "inspireth life"), ("4", "26", "but submit not thyself to every man for sin"),
               ("6", "5", "and appeaseth enemies"),
               ("8", "16", "Quarrel not … and go not into the desert with a bold man"),
               ("8", "18", "do no matter of counsel"), ("9", "3", "a woman that hath a mind for many"),
               ("11", "14", "Good things"), ("12", "9", "a friend is known"), ("16", "4", "the tribe of the ungodly"),
               ("18", "15", "add not grief by an evil word"), ("18", "15", "by an evil word"),
               ("19", "17", "and therein is to fear God"),
               ("19", "17", "and the disposition of the law is in all wisdom"),
               ("20", "5", "There is one that holdeth his peace"), ("20", "17", "are of a false tongue"),
               ("24", "3", "before all creatures"), ("24", "31", "and my river came near to a sea"),
               ("24", "33", "and will behold all that sleep"), ("25", "9", "findeth a true friend"),
               ("25", "18", "and hearing he sighed a little"), ("26", "1", "Happy is the husband"),
               ("27", "18", "his friend, so also is he that destroyeth"),
               ("27", "23", "In the sight of thy eyes he will sweeten"), ("30", "18", "Good things that are hidden"),
               ("32", "19", "My son, … without counsel"), ("33", "8", "the sun being made, and"),
               ("34", "10", "he that hath been experienced in many things"),
               ("34", "19", "to the oblations of the unjust"), ("34", "22", "He that sheddeth blood"),
               ("35", "6", "The oblation of the just"), ("39", "12", "as with a holy transport"),
               ("39", "15", "and give glory to him"), ("41", "12", "Take care of a good"),
               ("46", "12", "That their memory might be"),
               ("49", "2", "He was directed by God unto the repentance of the nation"),
               ("51", "13", "before I wandered about"), ("51", "17", "I found much … in myself"))},
           # Job: the DR's wording of the verse differs from the KJV's (each read against the DR verse by hand)
           *{("Job", c, v, head) for c, v, head in (
               ("3", "14", "should have rest … with kings"), ("5", "23", "and the beasts of the earth"),
               ("6", "19", "Consider the paths"), ("8", "7", "that … thy former things"),
               ("9", "2", "and that man cannot be justified"), ("11", "19", "Thou shalt rest"),
               ("15", "9", "what dost thou understand"), ("16", "3", "or is it any trouble to thee to speak?"),
               ("16", "3", "or is it any trouble to thee to speak"), ("16", "4", "I would comfort"),
               ("16", "9", "He hath gathered together his fury against me, and threatening me he hath gnashed"),
               ("16", "9", "He hath gathered together his fury"), ("19", "6", "that God hath not … with an equal judgment"),
               ("19", "29", "Flee then"), ("20", "14", "His bread in his belly"), ("28", "11", "The depths also of rivers"),
               ("30", "13", "They have destroyed my ways"), ("31", "2", "For what part should God … have"),
               ("31", "2", "For what part should … have in me"), ("35", "15", "For he doth not now bring on his fury,"),
               ("36", "30", "he shall cover also the ends of the sea"), ("40", "4", "who hath spoken inconsiderately"),
               ("40", "5", "which I wish I had not said:"), ("41", "11", "Who hath given me before"),
               ("41", "16", "One is joined to another,"))},
           # Genesis: the DR's wording of the verse differs from the KJV's (each read against the DR verse by hand)
           *{("Genesis", c, v, head) for c, v, head in (
               ("1", "6", "Let there be a firmament made"), ("2", "7", "man of the slime of the earth:"),
               ("2", "20", "And Adam called"), ("3", "24", "And he cast out Adam;"), ("3", "24", "And he cast out Adam"),
               ("4", "8", "And Cain said"), ("7", "11", "the flood gates"), ("10", "14", "Ludim, Anamim, Phetrusim, Capthorim"),
               ("14", "7", "the same is Cades:"),
               ("16", "2", "go in unto my handmaid, it may be I may have children of her at least."),
               ("17", "11", "that it may be for a sign of the covenant between me and you."),
               ("21", "33", "And Abimelech, and Phicol the general of"), ("24", "63", "the day being now well spent:"),
               ("25", "25", "and therefore he was called Jacob."), ("26", "20", "But there also … strove"),
               ("27", "41", "I will kill my brother Jacob."), ("31", "47", "And Laban called it The witness heap:"),
               ("37", "3", "above all his sons,"), ("38", "12", "to the shearers of his sheep"),
               ("38", "27", "whereon the midwife tied a scarlet thread, saying:"),
               ("40", "4", "But the keeper of the prison delivered them"))},
           # Exodus to Judith: the Douay-Rheims words the verse differently from the KJV, or Jerome splits it differently
           # and the phrase is in both (each read against the Douay-Rheims and the KJV verse by hand)
           *{("Exodus", c, v, head) for c, v, head in (
               ("1", "16", "keep it alive."), ("7", "15", "behold he will go out to the waters:"),
               ("7", "20", "he struck the water of the river"), ("12", "48", "be willing to dwell among you,"),
               ("12", "49", "The same law shall be to him that is born in the land, and to the proselyte"),
               ("15", "27", "And the children of Israel came into Elim,"),
               ("16", "8", "for he hath heard your murmurings"), ("16", "26", "therefore it shall not be found."),
               ("17", "11", "And when Moses lifted up his hands"), ("19", "16", "And now the third day was come,"),
               ("21", "14", "and by lying in wait for him:"),
               ("21", "26", "of his manservant or maidservant, and leave them but one eye, he shall let them go free"),
               ("21", "29", "then the ox shall be stoned, and his owner"),
               ("22", "11", "and he shall not be compelled to make restitution."),
               ("22", "13", "that which was slain, and he shall not make restitution."),
               ("23", "1", "neither shalt thou join"), ("23", "7", "Thou shalt fly lying."),
               ("24", "5", "to the Lord, twelve calves."), ("25", "25", "four inches"),
               ("25", "26", "of the same table"), ("25", "26", "over each foot."),
               ("27", "21", "among the children of Israel."),
               ("28", "26", "of the rational, in the borders that are over against the ephod,"),
               ("29", "8", "and gird them with a girdle:"), ("32", "19", "AND BEING VERY ANGRY"),
               ("34", "29", "from the conversation of the Lord."), ("35", "23", "If any man had gold, violet,"),
               ("37", "9", "and looking one towards the other, and towards it."),)},
           *{("Leviticus", c, v, head) for c, v, head in (
               ("1", "2", "among you a sacrifice"), ("1", "15", "and breaking the place of the wound,"),
               ("2", "11", "EVERY OBLATION THAT IS OFFERED"), ("4", "23", "to the Lord, a buck goat"),
               ("4", "23", "A BUCK GOAT"), ("5", "2", "his uncleanness, he is guilty, and hath offended:"),
               ("6", "3", "or shall find a thing lost,"), ("6", "11", "shall cause them to be consumed to dust."),
               ("7", "9", "And every sacrifice of flour"), ("10", "12", "because it is holy of holies."),
               ("11", "4", "But whatsoever cheweth the cud"), ("11", "10", "BUT WHATSOEVER HATH NOT FINS"),
               ("11", "20", "Of things that fly, whatsoever goeth upon four feet, shall be abominable to you."),
               ("13", "45", "and he shall cry out that he is defiled and unclean."),
               ("14", "5", "over living waters:"), ("15", "17", "that he weareth, he shall wash with water,"),
               ("15", "22", "any vessel on which she sitteth,"),
               ("15", "29", "SHE SHALL OFFER FOR HERSELF TO THE PRIEST"), ("19", "20", "with copulation of seed"),
               ("19", "29", "Make not a common strumpet"), ("19", "33", "and abide among you,"),
               ("20", "4", "that hath given of his seed to Moloch,"), ("20", "6", "and shall commit fornication"),
               ("20", "15", "let him die, the beast also ye shall kill."),
               ("21", "1", "at the death of his citizens:"), ("21", "13", "HE SHALL TAKE A VIRGIN UNTO HIS WIFE"),
               ("21", "19", "IF HIS FOOT BE BROKEN"), ("22", "14", "He that eateth of the sanctified things"),
               ("25", "14", "When thou shalt sell"), ("25", "31", "But if the house be in a village,"),
               ("26", "20", "the ground shall not bring forth"), ("26", "35", "In the enemy's land,"),
               ("26", "40", "their iniquities and the iniquities of their ancestors,"),)},
           *{("Numbers", c, v, head) for c, v, head in (
               ("5", "14", "stir up the husband"), ("6", "15", "without leaven"),
               ("13", "25", "THEY THAT WENT TO SPY OUT THE LAND"),
               ("19", "12", "Shall be sprinkled with this water on the third day,"),
               ("24", "6", "watered, as tabernacles"), ("24", "14", "I WILL GIVE THEE COUNSEL"),
               ("25", "15", "a most noble prince among the Madianites."), ("26", "54", "To the greater number"),
               ("26", "54", "TO THE GREATER NUMBER A GREATER"), ("28", "3", "THESE ARE THE SACRIFICES"),
               ("33", "15", "IN THE DESERT OF SINAI"), ("33", "15", "they camped in the desert of Sinai."),
               ("35", "33", "DEFILE NOT THE LAND"),)},
           *{("Deuteronomy", c, v, head) for c, v, head in (
               ("4", "17", "The similitude of any beasts,"), ("7", "8", "and hath kept his covenant,"),
               ("16", "11", "And thou shalt feast"), ("21", "8", "And the guilt of blood shall be taken from them:"),
               ("24", "7", "shall take a price,"), ("25", "7", "and call upon the ancients,"),
               ("26", "3", "this day before the Lord thy God,"), ("26", "12", "thou shalt give it to the Levite,"),
               ("27", "13", "And over against them these"), ("28", "8", "that thou shalt receive."),
               ("32", "34", "Are not these things stored up"), ("32", "42", "of the bare, of the enemies"),)},
           *{("Joshua", c, v, head) for c, v, head in (
               ("16", "10", "And the children of Ephraim slew not"),)},
           *{("Judges", c, v, head) for c, v, head in (
               ("3", "8", "DELIVERED THEM INTO THE HANDS"),
               ("15", "19", "Then the Lord opened a great tooth in the jaw of the ass, and waters issued out of it."),)},
           *{("1 Samuel", c, v, head) for c, v, head in (
               ("20", "22", "If I shall say to the boy: Behold the arrows are on this side of thee, take them up: come thou to me, because, there is peace to thee, and there is no evil, as the Lord liveth."),)},
           *{("2 Samuel", c, v, head) for c, v, head in (
               ("10", "15", "Then the Syrians seeing"), ("11", "2", "IN THE MEAN TIME IT HAPPENED"),
               ("11", "2", "from his bed after noon"), ("14", "13", "and [why] hath the king spoken this word"),
               ("16", "10", "Let him alone and let him curse."),
               ("23", "19", "And the noblest of three, and was their chief, but to the three"),)},
           # (a reading at the edition's 1 Kings 6:32 that "most copies" lack, the note says: kept where it stands)
           ("1 Kings", "6", "32", "and posts of corners."),
           *{("1 Kings", c, v, head) for c, v, head in (
               ("7", "26", "was three inches"), ("7", "31", "and in the corners of the pillars"),
               ("10", "16", "TWO HUNDRED SHIELDS"), ("10", "21", "NOR WAS ANY ACCOUNT MADE OF IT"),
               ("19", "3", "Then Elias was afraid,"),)},
           *{("1 Chronicles", c, v, head) for c, v, head in (
               ("4", "23", "AND THEY ABODE THERE. THE SONS OF SIMEON"), ("5", "10", "AGAINST THE AGARENS"),
               ("7", "30", "The children of Aser were Jemna,"),
               ("9", "28", "OF THEIR STOCK SOME ALSO WERE OVER THE VESSELS OF THE MINISTRY"),
               ("17", "25", "For thou, O Lord my God, hast revealed to the ear"),
               ("18", "12", "of Edom in the Vale of the saltpits"),
               ("23", "30", "and in like manner in the evening,"),)},
           *{("2 Chronicles", c, v, head) for c, v, head in (
               ("3", "6", "HE PAVED ALSO THE FLOOR"), ("3", "13", "toward the outward house."),
               ("3", "14", "HE MADE ALSO A VEIL"), ("4", "3", "AND SOME ON THE OUTSIDE OF TEN CUBITS"),
               ("4", "12", "and a kind of net work"), ("8", "6", "Balaath also,"),
               ("8", "9", "to serve in the king's works:"), ("9", "19", "THERE WAS NOT SUCH A THRONE"),
               ("24", "26", "BUT THEY LAID WAIT FOR HIM"), ("26", "16", "BUT WHEN HE WAS MADE STRONG"),)},
           *{("Nehemiah", c, v, head) for c, v, head in (
               ("3", "16", "NEHEMIAS BUILT"), ("9", "6", "AND ESDRAS SAID"),)},
           *{("2 Esdras", c, v, head) for c, v, head in (
               ("3", "14", "And thou didst love him and didst show"),)},
           *{("Tobit", c, v, head) for c, v, head in (
               ("1", "5", "Moreover when all went"), ("1", "5", "king of Israel had made, he"),
               ("1", "10", "and his son was come to the city of Ninive"), ("1", "13", "He therefore went to all"),
               ("1", "14", "he gave him the aforesaid sum of money"),
               ("2", "5", "And when he had hid the body, he ate bread with mourning"),
               ("3", "6", "And now, O Lord, according to thy will"), ("4", "4", "For thou must be mindful"),
               ("4", "13", "all perdition took its beginning"), ("4", "21", "but we shall have many good things"),
               ("6", "7", "Then the angel answering said to him: A little piece of its heart,"),
               ("6", "16", "And the second night"), ("7", "10", "Which word when Raguel heard"),
               ("10", "6", "And Tobias said to her:"), ("11", "10", "THE BLIND [FATHER] RISING UP"),
               ("12", "22", "they blessed God; and rising up they told"), ("14", "2", "And the rest of his life"),
               ("14", "13", "and all the inheritance of Raguel's house"),)},
           *{("Judith", c, v, head) for c, v, head in (
               ("2", "3", "that his thoughts were to bring all the earth"), ("4", "13", "high of the Lord"),
               ("4", "13", "went about all Israel"),
               ("5", "9", "from thence, and to dwell in Charan. And when a famine had covered all the land,"),
               ("6", "21", "will make this return, that rather their"),
               ("7", "30", "And when they were wearied with these cries"),
               ("8", "27", "for these things which we suffer,"), ("10", "4", "gave her more beauty,"),
               ("12", "6", "And she asked as she went in that she might have leave at night"),
               ("13", "19", "because he hath so magnified thy name this day,"),
               ("16", "1", "Judith this canticle to the Lord"), ("16", "21", "And after those days"),)},
           }


def _words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3 and w not in STOP}


def test_every_note_under_the_kjv_verse_it_explains():
    """Each phrase's words are compared with the KJV verse it's shown under and that verse's neighbours: a phrase that
    fits a neighbour much better means the Latin Bible's numbering (or a verse it splits differently) has put the notes
    under the wrong verse. Check a new book with this before building on it (VERSIFICATION, MOVES)."""
    kjv = {}
    for part in ("kjv_canon.json", "kjv_apocrypha.json"):      # (Wisdom and Sirach are in the KJV's Apocrypha)
        books = json.loads((ROOT / "data" / "kjv" / part).read_text(encoding="utf-8"))
        kjv.update(books.get("books", books))
    wrong = []
    for title, chapters in DATA["books"].items():
        name = title.removeprefix("Glossa Ordinaria on ")
        order = [(c, v) for c in kjv[name] for v in kjv[name][c]]
        for c, verses in chapters.items():
            for v, text in verses.items():
                assert (c, v) in order, (name, c, v)
                i = order.index((c, v))
                for head in re.findall(r"^\*\*“(.+?)”\*\*", text, re.M):
                    w = _words(head)
                    if len(w) < 2 or (name, c, v, head) in CHECKED:
                        continue
                    fit = {o: len(w & _words(kjv[name][o[0]][o[1]])) / len(w) for o in order[max(0, i - 1):i + 2]}
                    best = max(fit, key=fit.get)
                    if fit[best] > fit[(c, v)] + 0.25:
                        wrong.append(f"{name} {c}:{v} “{head}” fits {best[0]}:{best[1]}")
    assert not wrong, wrong


def test_joel_whole():
    """Joel's three chapters number alike in the Vulgate and the KJV; Pentecost's verse (2:28) is there."""
    joel = DATA["books"]["Glossa Ordinaria on Joel"]
    assert sorted(joel, key=int) == ["1", "2", "3"] and "21" in joel["3"]
    assert joel["2"]["28"].startswith("**“And it shall come to pass after this, that I will pour out my spirit")


def test_amos_on_the_kjvs_numbering():
    """The Vulgate's Amos 6:10-11 are the KJV's 6:10, its 6:12-15 the KJV's 6:11-14; its 5:1 ends with the start of the
    KJV's 5:2 ("is fallen, and it shall rise no more")."""
    amos = DATA["books"]["Glossa Ordinaria on Amos"]
    assert sorted(amos, key=int) == [str(c) for c in range(1, 10)] and "15" not in amos["6"]
    assert "Is there yet any with thee?" in amos["6"]["10"] and "There is an end" in amos["6"]["10"]
    assert "Can horses run upon the rocks" in amos["6"]["12"] and "from the entrance of Emath" in amos["6"]["14"]
    assert "**“is fallen”**" in amos["5"]["2"] and "**“is fallen”**" not in amos["5"]["1"]
    assert "And I will plant them" in amos["9"]["15"]


def test_obadiah_whole():
    """Obadiah's one chapter numbers alike in the Vulgate and the KJV (21 verses)."""
    obadiah = DATA["books"]["Glossa Ordinaria on Obadiah"]
    assert list(obadiah) == ["1"] and sorted(obadiah["1"], key=int)[-1] == "21"
    assert "the kingdom shall be for the Lord" not in obadiah["1"]["1"]
    assert "**“saviours”**" in obadiah["1"]["21"]


def test_micah_on_the_kjvs_numbering():
    """The Vulgate's Micah 5:11 is the KJV's 5:11-12 (its sorceries are the KJV's 5:12), its 5:12-14 the KJV's
    5:13-15; the card's Douay-Rheims verse follows."""
    micah = DATA["books"]["Glossa Ordinaria on Micah"]
    assert sorted(micah, key=int) == [str(c) for c in range(1, 8)] and "21" not in micah["7"]
    assert "deceived by others" in micah["5"]["12"] and "deceived by others" not in micah["5"]["11"]
    assert "graven things" in micah["5"]["13"] and "execute vengeance" in micah["5"]["15"]
    assert "**“AND THOU, BETHLEHEM Ephrata”**" in micah["5"]["2"]
    verses = DATA["douay"]["Micah"]["verses"]["5"]
    assert verses["12"]["ref"] == "5:11" and verses["15"]["ref"] == "5:14"
    assert "swords into ploughshares" in micah["4"]["3"]


def test_nahum_whole():
    """Nahum numbers alike in the Vulgate and the KJV; the gloss on 3:10's "eius" reads "her" (Alexandria's) there,
    though the book's lemma for it is 1:13's "his", and stays in its place among that verse's notes."""
    nahum = DATA["books"]["Glossa Ordinaria on Nahum"]
    assert {c: len(v) for c, v in nahum.items()} == {"1": 15, "2": 13, "3": 19}
    assert "**“her”** — Alexandria's" in nahum["3"]["10"]
    assert nahum["3"]["10"].index("Alexandria's") < nahum["3"]["10"].index("by the enemy")
    assert "**“his”** — of the Assyrian" in nahum["1"]["13"]


def test_habakkuk_doublet_glosses_under_1_13_and_14():
    """The edition's 1:3 repeats 1:13-14's words; their glosses go to 1:13-14 (after 1:13's own first half), and the
    KJV's 1:14 has notes."""
    hab = DATA["books"]["Glossa Ordinaria on Habakkuk"]
    assert {c: len(v) for c, v in hab.items()} == {"1": 17, "2": 20, "3": 19}
    assert "despisers" not in hab["1"]["3"] and "fishes of the sea" not in hab["1"]["3"]
    assert hab["1"]["13"].index("Thy eyes are too pure") < hab["1"]["13"].index("Why lookest thou upon the despisers")
    assert "Boethius" in hab["1"]["14"]
    assert "**“Let rottenness enter into my bones”**\n• but" in hab["3"]["16"]


def test_zephaniah_whole():
    """Zephaniah numbers alike in the Vulgate and the KJV; the gloss that opens 3:3 (filed under 3:2's last words)
    heads 3:3's notes."""
    zeph = DATA["books"]["Glossa Ordinaria on Zephaniah"]
    assert sorted(zeph, key=int) == ["1", "2", "3"] and "20" in zeph["3"]
    assert zeph["3"]["3"].startswith("**“Her princes are in the midst of her”**\n• After the general rebuke")
    assert "drew not near" not in zeph["3"]["3"]
    assert "Chusi" in zeph["1"]["1"]


def test_haggai_on_the_kjvs_numbering(bot_module):
    """The Vulgate's Haggai 2:1 (the work begun on the 24th day) is the KJV's 1:15, its 2:2-24 the KJV's 2:1-23; the
    signet gloss filed under the Vulgate's 2:23 goes with its words to the KJV's 2:23."""
    hag = DATA["books"]["Glossa Ordinaria on Haggai"]
    assert sorted(hag, key=int) == ["1", "2"] and "24" not in hag["2"]
    assert "twenty-two days between" in hag["1"]["15"]
    assert "**“And in the seventh month" in hag["2"]["1"] and "signet" in hag["2"]["23"]
    assert "signet" not in hag["2"]["22"]
    from bot_commands import bible_commentary as B
    assert "— Douay-Rheims, Aggeus 2:1" in B.reply("Haggai", 1, 15)["embed"].description

def test_zechariah_whole():
    """Zechariah numbers alike in the Vulgate and the KJV; the notes on the angel going forth and on the vessel, which
    the edition files under 5:7-8, go to 5:5-6, where those words are."""
    zech = DATA["books"]["Glossa Ordinaria on Zechariah"]
    assert sorted(zech, key=int) == [str(c) for c in range(1, 15)]
    assert zech["5"]["5"].startswith("**“And the angel went forth”**")
    assert "This is a vessel" in zech["5"]["6"]
    assert "And the angel went forth" not in zech["5"].get("7", "")
    assert "bridle of the horse" in zech["14"]["20"]

def test_malachi_whole():
    """Malachi has four chapters in the Vulgate as in the KJV; "What have we spoken against thee?", the Douay-Rheims's
    3:14, ends the KJV's 3:13, and its notes go with it."""
    mal = DATA["books"]["Glossa Ordinaria on Malachi"]
    assert sorted(mal, key=int) == ["1", "2", "3", "4"]
    assert "What have we spoken against thee?" in mal["3"]["13"]
    assert "What have we spoken against thee?" not in mal["3"].get("14", "")
    assert "Elias" in mal["4"]["6"] and "Sun of justice" in mal["4"]["2"]

def test_ruth_whole():
    """Ruth numbers alike in the Vulgate and the KJV; the genealogy's note closes the book."""
    ruth = DATA["books"]["Glossa Ordinaria on Ruth"]
    assert sorted(ruth, key=int) == ["1", "2", "3", "4"]
    assert "Rabanus" in ruth["1"]["1"] and "whither" not in ruth["1"]["1"]
    assert "whithersoever thou shalt go, I will go" in ruth["1"]["16"]
    assert "ten generations" in ruth["4"]["22"]


def test_proverbs_on_the_kjvs_numbering():
    """Proverbs numbers alike in the Vulgate and the KJV but for the Vulgate's 4:28, the end of the KJV's 4:27."""
    proverbs = DATA["books"]["Glossa Ordinaria on Proverbs"]
    assert sorted(proverbs, key=int) == [str(c) for c in range(1, 32)] and "28" not in proverbs["4"]
    assert "thy ways in peace" in proverbs["4"]["27"]
    assert "a valiant woman" in proverbs["31"]["10"]
    assert "no need of spoils" in proverbs["31"]["11"]


def test_wisdom_on_the_kjvs_numbering():
    """The Vulgate's Wisdom has lines the KJV lacks (5:14, 6:1, 6:23) and splits 11:5-6, 17:9 and 19:12 differently, so
    its notes are renumbered to the KJV's (Wisdom of Solomon, in its Apocrypha), every chapter within the KJV's."""
    wisdom = DATA["books"]["Glossa Ordinaria on Wisdom of Solomon"]
    kjv = json.loads((ROOT / "data" / "kjv" / "kjv_apocrypha.json").read_text(encoding="utf-8"))
    kjv = kjv.get("books", kjv)["Wisdom of Solomon"]
    assert sorted(wisdom, key=int) == [str(c) for c in range(1, 20)]
    for c, verses in wisdom.items():
        assert max(map(int, verses)) <= max(map(int, kjv[c])), c
    assert "Wisdom is better" in wisdom["6"]["1"]
    assert "But thy wrath endured not for ever" in wisdom["16"]["5"]
    assert "For in all things thou didst magnify" in wisdom["19"]["22"]


def test_sirach_on_the_kjvs_numbering():
    """The Vulgate's Ecclesiasticus numbers most verses differently from the KJV's Sirach (scripts/glossa/versification/
    32.json), so its notes are renumbered, every chapter within the KJV's; the card quotes the Douay-Rheims verse."""
    sirach = DATA["books"]["Glossa Ordinaria on Sirach"]
    kjv = json.loads((ROOT / "data" / "kjv" / "kjv_apocrypha.json").read_text(encoding="utf-8"))
    kjv = kjv.get("books", kjv)["Sirach"]
    assert sorted(sirach, key=int) == [str(c) for c in range(1, 52)]
    for c, verses in sirach.items():
        assert max(map(int, verses)) <= max(map(int, kjv[c])), c
    assert "In the treasures of wisdom" in sirach["1"]["25"]          # the Vulgate's 1:26
    assert "and then give place to the physician" in sirach["38"]["12"]   # the end of the Vulgate's 38:11
    assert "He played with lions" in sirach["47"]["3"]
    # the edition's 29:18-35 are the Douay-Rheims's 29:16-34 (it has two lines of its own at 29:16-17)
    douay = DATA["douay"]["Sirach"]
    assert douay["book"] == "Ecclesiasticus" and douay["verses"]["29"]["14"]["ref"] == "29:18"
    assert "than the shield" in sirach["29"]["13"] and "the kindness of thy surety" in sirach["29"]["15"]


def test_job_on_the_kjvs_numbering(bot_module):
    """The Vulgate's Job 16:5 is the end of the KJV's 16:4; its 39:31-35 are the KJV's 40:1-5, its 40:1-19 the KJV's
    40:6-24, its 40:20-28 the KJV's 41:1-9 and its 41 the KJV's 41:10-34; the Commentary button on Job opens it first,
    before Gregory's Morals."""
    job = DATA["books"]["Glossa Ordinaria on Job"]
    assert sorted(job, key=int) == [str(c) for c in range(1, 43)]
    assert "23" not in job["16"] and "31" not in job["39"] and "25" not in job["40"]
    assert "**“Canst thou draw out the leviathan with a hook" in job["41"]["1"]
    assert "**“who hath spoken inconsiderately”**" in job["40"]["4"]
    assert "neither shall his place know him" in job["7"]["10"] and "days of affliction" in job["30"]["16"]
    assert "*Morally:*" in "".join(v for c in job.values() for v in c.values())   # a heading, not a quoted phrase
    from bot_commands import bible_commentary as B
    assert [label for label, _, _ in B.groups("Job", 1, 1)][0] == "The Glossa Ordinaria"
    assert "a man in the land of Hus" in B.reply("Job", 1, 1)["embed"].description


def test_genesis_on_the_kjvs_numbering(bot_module):
    """The Vulgate's Genesis 49:32 is the KJV's 49:33 and its 50:23-25 the KJV's 50:24-26; the Commentary button on
    Genesis opens the Glossa first."""
    gen = DATA["books"]["Glossa Ordinaria on Genesis"]
    assert sorted(gen, key=int) == [str(c) for c in range(1, 51)]
    assert "when he had ended the commandments" in gen["49"]["33"] and "32" not in gen["49"]
    assert "a hundred and ten years old" in gen["50"]["26"]
    assert "begot Sem, Cham, and Japheth" in gen["5"]["32"]
    from bot_commands import bible_commentary as B
    assert [label for label, _, _ in B.groups("Genesis", 1, 1)][0] == "The Glossa Ordinaria"


def test_exodus_to_judith_on_the_kjvs_numbering(bot_module):
    """Exodus to Judith (2026-11-15): the Latin Bible's verses put under the KJV's (scripts/glossa/versification/),
    the Prayer of Manasses taken out of 2 Paralipomenon 37, and 3-4 Esdras under the KJV's 1-2 Esdras."""
    books = DATA["books"]
    for name in ("Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "1 Samuel", "2 Samuel",
                 "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Prayer of Manasseh", "Ezra", "Nehemiah",
                 "1 Esdras", "2 Esdras", "Tobit", "Judith"):
        assert f"Glossa Ordinaria on {name}" in books, name
    assert "37" not in books["Glossa Ordinaria on 2 Chronicles"]
    assert "I HAVE SINNED, O LORD, I HAVE SINNED" in books["Glossa Ordinaria on Prayer of Manasseh"]["1"]["12"]
    # the Vulgate's Numbers 13:1 ("the people marched from Haseroth") is the KJV's 12:16
    assert "the people from Haseroth" in books["Glossa Ordinaria on Numbers"]["12"]["16"]
    douay = DATA["douay"]
    assert douay["Numbers"]["verses"]["12"]["16"]["ref"] == "13:1"
    assert douay["Exodus"]["verses"]["40"]["38"]["ref"] == "40:36"     # the Vulgate's Exodus 40 is two verses short
    assert "Prayer of Manasseh" not in douay and "1 Esdras" not in douay   # (not in the Douay-Rheims)
    # the edition's 3 Esdras 8:33 ("Zacharias, and with him ... a hundred and fifty men") is the KJV's 1 Esdras 8:30
    assert "a hundred and fifty men" in books["Glossa Ordinaria on 1 Esdras"]["8"]["30"]
    assert "above Naasson" in books["Glossa Ordinaria on Tobit"]["1"]["2"]
    from bot_commands import bible_commentary as B
    assert [label for label, _, _ in B.groups("Tobit", 1, 2)][0] == "The Glossa Ordinaria"
    assert "Douay-Rheims" in B.reply("Exodus", 20, 3)["embed"].description
    import scripture_lookup
    assert scripture_lookup.ALIASES["glossa 3 kings"] == "Glossa Ordinaria on 1 Kings"
    assert scripture_lookup.ALIASES["glossa 4 esdras"] == "Glossa Ordinaria on 2 Esdras"


def test_esther_stops_before_the_additions():
    """The Glossa's Esther ends at 10:3, so it needs no renumbering; the Vulgate's additions (10:4-16:24) have no notes."""
    esther = DATA["books"]["Glossa Ordinaria on Esther"]
    assert sorted(esther, key=int) == [str(c) for c in range(1, 11)]
    assert max(esther["10"], key=int) == "3"
    assert "golden sceptre" in esther["5"]["2"]


def test_song_on_the_kjvs_numbering():
    """The KJV's Song 1:1 is the title, so the Vulgate's chapter 1 and 6 are one verse behind; its 5:17 is the KJV's
    6:1, and its 5:1 and 7:1 begin with the ends of the KJV's 4:16 and 6:13."""
    song = DATA["books"]["Glossa Ordinaria on Song of Solomon"]
    assert sorted(song, key=int) == [str(c) for c in range(1, 9)] and "1" not in song["1"] and "17" not in song["5"]
    assert "**“Let him kiss me”**" in song["1"]["2"]
    assert "**“Let my beloved come”**" in song["4"]["16"] and "Let my beloved come" not in song["5"]["1"]
    assert "**“Whither is … gone”**" in song["6"]["1"] and "13" in song["6"]
    assert "Flee away, O my beloved" in song["8"]["14"]


def test_ecclesiastes_on_the_kjvs_numbering():
    """The Vulgate's Ecclesiastes 4:17 is the KJV's 5:1 and its 5:1-19 the KJV's 5:2-20; its 7:1 is the KJV's 6:12 and
    its 7:2-30 the KJV's 7:1-29. Chapter 1 is there (the edition numbers it differently: tests the fetcher's fix)."""
    ecc = DATA["books"]["Glossa Ordinaria on Ecclesiastes"]
    assert [len(ecc[str(c)]) for c in (1, 4, 5, 6, 7)] == [17, 10, 20, 12, 29]
    assert "**“Vanity of vanities, said Ecclesiastes”**" in ecc["1"]["2"]
    assert "**“Keep”**" in ecc["5"]["1"] and "**“Speak not any thing rashly”**" in ecc["5"]["2"]
    assert "**“What needeth a man to seek things that are above him”**" in ecc["6"]["12"]
    assert "**“A good name is better”**" in ecc["7"]["1"] and "30" not in ecc["7"]
    assert "The Laodicean says" in ecc["4"]["13"] and "From here to the end of the chapter" in ecc["12"]["1"]


def test_lamentations():
    """Lamentations numbers its verses as the KJV does; the introduction to the third alphabet, which the edition files
    under 3:66, is shown at 3:1, and Gilbert's sign-off at 5:22."""
    lam = DATA["books"]["Glossa Ordinaria on Lamentations"]
    assert [len(lam[str(c)]) for c in range(1, 6)] == [22, 22, 66, 22, 22]
    assert "**“Aleph. I am”**" in lam["3"]["1"] and "*Gilbert:*" in lam["3"]["1"] and "Gilbert" not in lam["3"]["66"]
    assert "deacon of the church of Auxerre" in lam["5"]["22"]


def test_every_gloss_in_english_and_clean():
    for f in ENGLISH.glob("*.json"):
        for gid, text in json.loads(f.read_text(encoding="utf-8")).items():
            assert text.strip() and not re.search(r"\{t\.|[<>]", text), (f.name, gid)
    for book in DATA["books"].values():
        for ch, verses in book.items():
            for v, text in verses.items():
                assert text.count("**") % 2 == 0 and "{t." not in text, (ch, v)


def test_glossa_card_shows_the_douay_rheims(bot_module):
    """The Glossa's notes quote the Douay-Rheims, so its card shows the verse in those words, and by the Latin Bible's
    number where it differs; other commentaries keep the KJV."""
    from bot_commands import bible_commentary as B
    desc = B.reply("Jonah", 1, 3)["embed"].description
    assert desc.startswith("*And Jonas rose up to flee into Tharsis") and "— Douay-Rheims\n" in desc
    assert "Tarshish" not in desc.split("— Douay-Rheims")[0]
    fish = B.reply("Jonah", 1, 17)["embed"].description
    assert fish.startswith("*Now the Lord prepared a great fish") and "— Douay-Rheims, Jonas 2:1" in fish
    assert "Amos 6:10, 6:11" in B.reply("Amos", 6, 10)["embed"].description
    gospel = B.reply("John", 3, 16)["embed"].description
    assert "Douay-Rheims" not in gospel


def test_in_the_commentary_menu(bot_module):
    from bot_commands import bible_commentary as B
    labels = [label for label, _, _ in B.groups("Jonah", 1, 3)]
    assert labels[0] == "The Glossa Ordinaria"
    assert "to flee into Tharsis" in B.reply("Jonah", 1, 3)["embed"].description
