"""Games: Who Am I?"""
import asyncio
import random

import pytest


@pytest.fixture(scope="module")
def games(bot_module):
    from bot_commands import games
    return games


def _slug(name):
    from bot_commands import people
    return people.find("people", name)[0]


def test_clues_never_name_the_person(games):
    rng = random.Random(5)
    for name in ("David", "Ruth", "Moses", "Peter", "Mary"):
        slug = _slug(name)
        clues = games.make_clues(slug, rng)
        assert len(clues) >= 5, name
        for clue in clues[:-1]:                     # the last clue gives the first letter on purpose
            for n in games._names_of(games.people.data()["people"][slug]):
                assert not __import__("re").search(rf"\b{n}\b", clue), (name, n, clue)


def test_clues_get_easier(games):
    clues = games.make_clues(_slug("David"), random.Random(1))
    assert clues[0].startswith("I am a man named in")
    assert "My name means “Beloved”." in clues
    assert clues[-1] == "My name begins with **D** and has 5 letters."
    assert "Jesse" in clues[-2]                    # the family names come near the end


def test_name_meanings(games):
    assert games.name_meaning("Beloved, the eighth and youngest son of Jesse") == "Beloved"
    assert games.name_meaning("A friend, a Moabitess, the wife of Mahlon") == "A friend"
    assert games.name_meaning("The son and successor of Asa, king of Judah.") == ""
    assert games.name_meaning("Originally called Simon (=Simeon)") == ""


def test_guesses(games):
    david, peter, jacob = _slug("David"), _slug("Peter"), _slug("Jacob")
    assert games.is_right("david", david) and games.is_right("King David", david)
    assert games.is_right("Peter", peter) and games.is_right("Simon Peter", peter) and games.is_right("Cephas", peter)
    assert games.is_right("Israel", jacob)
    assert not games.is_right("Saul", david) and not games.is_right("", david)


def test_a_round(games, fake_ctx):
    class Response:
        def __init__(self):
            self.done, self.sent, self.edited = False, [], None

        def is_done(self):
            return self.done

        async def send_message(self, content=None, **kwargs):
            self.done = True
            self.sent.append(content)

        async def edit_message(self, **kwargs):
            self.done = True
            self.edited = kwargs

    class User:
        def __init__(self, uid, name):
            self.id, self.display_name = uid, name

    class Interaction:
        def __init__(self, uid, name="Ann"):
            self.user, self.response = User(uid, name), Response()

    async def run():
        view = games.WhoAmIView(_slug("Ruth"), ["clue one", "clue two", "clue three"])
        wrong = Interaction(1)
        await view.check(wrong, "Naomi")
        assert "Not Naomi" in wrong.response.sent[-1]
        again = Interaction(1)
        await view.check(again, "Ruth")                     # one guess per clue
        assert "wait for the next" in again.response.sent[-1]
        view.shown = 2
        right = Interaction(1, "Ann")
        await view.check(right, "ruth")
        assert view.over and view.winner == "Ann"
        embed = right.response.edited["embed"]
        assert embed.fields[0].name == "I am Ruth" and "clue 2" in embed.fields[0].value
        view.stop()

    asyncio.run(run())


def test_whoami_command(games, fake_ctx):
    asyncio.run(games.start_whoami(fake_ctx))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🕵️ Who am I?" and sent["embed"].description.startswith("**1.** I am a")
    sent["view"].stop()
