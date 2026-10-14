"""!catena reads catenabible.com's JSON API (the live check is in test_live.py)."""
import json


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_catena_text_keeps_references():
    from bot_commands.church import _catena_text
    assert _catena_text('<verseRef>John 3:16</verseRef> "God," He saith, &quot;so loved') == \
        '(John 3:16) "God," He saith, "so loved'


def test_catena_sections_from_the_api(bot_module, monkeypatch):
    from bot_commands import church
    index = {"fathers": [
        {"fatherName": "John Chrysostom", "yearReposed": 407,
         "entries": [{"paragraphId": "p1", "workTitle": "Homilies on John."}]},
        {"fatherName": "Augustine of Hippo", "yearReposed": 430,
         "entries": [{"paragraphId": "p2", "workTitle": "Tractates on John"}]}]}
    bodies = {"p1": {"commentary": {"text": "<verseRef>John 3:16</verseRef> God so loved the world, He saith."},
                     "continuation": [{"text": "What He saith is of this kind: marvel not."}]},
              "p2": {"commentary": {"text": "Love was the reason, and nothing else at all."}, "continuation": []}}
    asked = []

    def fake_urlopen(request, timeout=0):
        asked.append(request.full_url)
        if "tab=index" in request.full_url:
            return _Response(index)
        return _Response(bodies[request.full_url.rsplit("/", 1)[1]])

    monkeypatch.setattr(church.urllib.request, "urlopen", fake_urlopen)
    r = church._fetch_catena_sections("John 3:16")
    assert asked[0] == "https://catenabible.com/api/verse/jn/3/16?tab=index"
    assert [name for name, _ in r["sections"]] == ["John Chrysostom AD 407", "Augustine of Hippo AD 430"]
    first = r["sections"][0][1]
    assert first.startswith("(John 3:16) God so loved") and "marvel not." in first
    assert first.endswith("— *Homilies on John*")
    assert len(church._fetch_catena_sections("John 3:16", limit=1)["sections"]) == 1     # what the VOTD uses
