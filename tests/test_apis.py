"""What the MongoDB plugin attaches to (plugin API 2.2): its card is sound, every address one of MongoDB's own pages;
it names the commands the plugin itself sends; what it knows of MongoDB here asks no server and loads no driver; and
the card's pages answer (LIMINAL_VENDOR_PAGES=1 only, the one test that reaches the network)."""
from __future__ import annotations

import inspect
import os
import sys

import pytest

import plugin_platform_mongodb as module
from liminal_libs.sources.apis import dead_links, problems, urls
from plugin_platform_mongodb import DATABASE
from plugin_platform_mongodb import apis as cards


def test_the_card_is_sound_and_links_the_makers_own_pages():
    assert problems(DATABASE.apis) == [] and DATABASE.apis == cards.APIS == (cards.MONGODB,)
    api = cards.MONGODB
    assert (api.name, api.kind, api.verified, api.costs) == ("MongoDB", "sdk", "2026-11-16", "") and api.docs == cards.MANUAL
    assert all(u.startswith("https://www.mongodb.com/") for u in urls(DATABASE.apis))
    assert len(urls(DATABASE.apis)) == 16 and {x.kind for x in api.links} == {"docs", "reference", "sdk", "guide", "changelog", "terms"}
    assert len(api.areas) > len(api.covered) >= 6 and len(api.calls) > len(api.used) >= 8
    assert {c.area for c in api.calls} <= {a.name for a in api.areas}
    # what it stands on is on the card: this machine alone unless told, off it only when asked twice and over TLS
    binding = next(a for a in api.areas if a.name == "IP binding")
    assert binding.docs == cards.BINDING and "asked twice" in binding.covered
    assert "over TLS alone" in next(a.covered for a in api.areas if a.name == "TLS")
    assert {c.name for c in api.calls if c.writes} >= {"createUser", "dropUser", "shutdown"}


def test_the_card_names_what_the_plugin_itself_sends():
    src = inspect.getsource(module)
    used = " ".join(c.name for c in cards.MONGODB.used)
    for sent, named in (('command("ping")', "ping"), ("server_info()", "buildInfo (MongoClient.server_info())"),
                        ("list_collection_names()", "listCollections"), ("list_database_names()", "listDatabases"),
                        ('command("createUser"', "createUser"), ('command("dropUser"', "dropUser"),
                        ("insert_one(", "insert into liminal_instance")):
        assert sent in src and named in used
    for never in ('command("shutdown")', "serverStatus", "dbStats", "mongo.start(", "mongo.ensure(", "mongo.attach("):
        assert never not in src  # it ends no server and starts none: those are the app's own (liminal-libs' mongo.py)
    assert "directConnection=True" in src and module.ROLE == "readWrite" and module.PORT_VAR == "LIMINAL_MONGO_PORT"


def test_what_it_knows_of_mongodb_here_asks_no_server_and_loads_no_driver(monkeypatch):
    was = {name: sys.modules.pop(name) for name in list(sys.modules) if name == "pymongo" or name.startswith("pymongo.")}
    monkeypatch.setattr(module, "mongo_client", lambda *a, **k: pytest.fail("a server was asked"))
    monkeypatch.delenv("LIMINAL_MONGO_PORT", raising=False)
    monkeypatch.delenv("MASSIVE_MONGO_PORT", raising=False)
    try:
        facts = module.MongodbPlugin().api_facts()
        assert list(facts) == ["MongoDB"] and facts["MongoDB"]["The server here"] == "127.0.0.1:27017"
        assert "pymongo" not in sys.modules
    finally:
        sys.modules.update(was)


@pytest.mark.skipif(os.environ.get("LIMINAL_VENDOR_PAGES") != "1", reason="reaches MongoDB's pages: LIMINAL_VENDOR_PAGES=1")
def test_the_cards_pages_answer():
    assert dead_links(DATABASE.apis) == []
