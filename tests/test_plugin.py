"""The MongoDB plugin against stand-in servers (no server is started, asked or needed; no process, no network): its own
instance is the server here, never started to be asked, its port its own; a database on another server is connected
only when it answers, signing in where the server wants it; one off this machine only when asked twice, over TLS and
signed in; a new database gets a role of its own on a server that signs in, the administrator not kept; every client
it makes is closed; a sign-in never reaches what is kept or shown."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import plugin_platform_mongodb as module
from liminal_libs import mongo, mounts
from liminal_libs.apps import EnvironmentLogin
from liminal_libs.apps.authorization import Unauthorized
from liminal_libs.storage import databases
from liminal_libs.storage.databases import Refusal
from plugin_platform_mongodb import DATABASE, MARKER, MongodbPlugin, __version__


class OperationFailure(Exception):
    """PyMongo's, as the plugin reads it: the server's word and its code."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


class FakeCollection:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def _docs(self) -> list:
        return self.db.client.server()["dbs"].setdefault(self.db.name, {}).setdefault(self.name, [])

    def insert_one(self, doc):
        self.db.client.may(self.db.name)
        if self.db.client.server().get("insert_fails"):
            self.db.client.server()["insert_fails"] -= 1
            raise ConnectionError("the server went away")
        self._docs().append(dict(doc))

    def find_one(self, query):
        self.db.client.may(self.db.name)
        return next((d for d in self._docs() if all(d.get(k) == v for k, v in query.items())), None)


class FakeDb:
    def __init__(self, client, name):
        self.client, self.name = client, name

    def command(self, name, value=None, **more):
        server = self.client.server()
        if name == "ping":
            self.client.signed()
            return {"ok": 1}
        if name == "createUser":
            self.client.may("admin")  # the server's keeper alone makes users
            if value in server["users"].get(self.name, {}):
                raise OperationFailure(f'User "{value}@{self.name}" already exists', 51003)
            server["users"].setdefault(self.name, {})[value] = more["pwd"]
            server["made"].append((self.name, value, more["roles"]))
            return {"ok": 1}
        if name == "updateUser":
            self.client.may("admin")
            if value not in server["users"].get(self.name, {}):
                raise OperationFailure(f"Could not find user \"{value}\" for db \"{self.name}\"", 11)
            server["users"][self.name][value] = more["pwd"]
            server["updated"].append((self.name, value, more["roles"]))
            return {"ok": 1}
        if name == "dropUser":
            if server.get("drop_fails"):
                raise ConnectionError("the server went away")
            self.client.may("admin")
            server["users"].get(self.name, {}).pop(value, None)
            server["dropped"].append((self.name, value))
            return {"ok": 1}
        raise OperationFailure(f"no such command: {name}", 59)

    def list_collection_names(self):
        self.client.may(self.name)
        return list(self.client.server()["dbs"].get(self.name, {}))

    def __getitem__(self, name):
        return FakeCollection(self, name)


class FakeClient:
    """A client of a stand-in server: what it was made with, whether it was closed, and the server's own refusals."""

    def __init__(self, servers, host, port, timeout_ms=None, **more):
        self.servers, self.host, self.port, self.more, self.closed = servers, host, port, more, False
        servers.clients.append(self)

    def server(self) -> dict:
        found = self.servers.at.get((self.host, self.port))
        if found is None:
            raise ConnectionError(f"no server answers at {self.host}:{self.port}")
        if found.get("tls") and not self.more.get("tls"):
            raise ConnectionError("the server wants TLS")
        return found

    def signed(self):
        users, user = self.server()["users"], self.more.get("username")
        if user is None:
            return None
        if users.get(self.more.get("authSource"), {}).get(user) != self.more.get("password"):
            raise OperationFailure("Authentication failed.", 18)
        return user

    def may(self, db: str) -> None:
        users, user = self.server()["users"], self.signed()
        if not users:
            return  # a server with no access control
        if user is None:
            raise OperationFailure("command requires authentication", 13)
        if self.more["authSource"] not in ("admin", db):
            raise OperationFailure(f"not authorized on {db}", 13)

    @property
    def admin(self):
        return FakeDb(self, "admin")

    def server_info(self):
        self.signed()
        return {"version": self.server()["version"]}

    def list_database_names(self):
        self.may("admin")
        return list(self.server()["dbs"])

    def __getitem__(self, name):
        return FakeDb(self, name)

    def close(self):
        self.closed = True


def server(**more) -> dict:
    return {"version": "9.0.4", "users": {}, "dbs": {}, "made": [], "updated": [], "dropped": [], **more}


@pytest.fixture
def mongos(tmp_path, monkeypatch):
    """The plugin attached to an app whose data folder is the test's; `servers.at` is what answers, by (host, port),
    and what listens on this machine; another machine is never asked whether it listens."""
    servers = SimpleNamespace(at={}, clients=[])
    monkeypatch.delenv("LIMINAL_MONGO_PORT", raising=False)
    monkeypatch.delenv("MASSIVE_MONGO_PORT", raising=False)
    monkeypatch.setattr(module, "mongo_client", lambda host, port, timeout_ms=2000, **more: FakeClient(servers, host, port, timeout_ms, **more))

    fresh_asks: list = []

    def listening(host, port, timeout=0.3, fresh=False):
        assert databases.is_local(host), f"{host} asked whether it listens without the user's test"
        if fresh:
            fresh_asks.append((host, port))
        return (host, port) in servers.at

    servers.fresh = fresh_asks

    monkeypatch.setattr(databases, "listening", listening)
    data = tmp_path / "data"
    data.mkdir()
    env: dict = {}
    plugin = MongodbPlugin()
    plugin.attach(SimpleNamespace(db_path=data / "liminal.db"), EnvironmentLogin(env=env))
    yield plugin, servers, env
    assert all(c.closed for c in servers.clients), "a client was left open"


def test_its_own_instance_is_the_server_here_never_started_to_be_asked(mongos, monkeypatch):
    plugin, servers, env = mongos
    assert DATABASE.name == "mongodb" and isinstance(DATABASE, MongodbPlugin) and plugin.default_port() == 27017
    (own,) = plugin.instances()
    assert (own.name, own.where, own.method, own.port, own.database, own.holds, own.builtin) == (
        "local", "127.0.0.1", "tcp", 27017, "liminal", ("documents",), True)
    state = plugin.state(own)
    assert state["state"] == "not running" and state["address"] == "127.0.0.1:27017/liminal" and state["local"] is True
    assert state["why"].startswith("not running: started when a plugin's documents are kept in MongoDB, never to be asked")
    assert isinstance(state["installed"], bool)
    tested = plugin.test("local")
    assert tested["ok"] is False and "nothing listens at 127.0.0.1:27017: the server here is started when" in tested["said"]
    assert servers.clients == []  # not running: no client is made to find that out
    assert servers.fresh == [("127.0.0.1", 27017)]  # a test asks now; the status before it took what was remembered
    servers.at[("127.0.0.1", 27017)] = server(dbs={"liminal": {"news": [], "gov_items": [], "system.views": []}})
    assert plugin.state(own)["state"] == "listening"
    tested = plugin.test("local")
    assert tested["ok"] and tested["lines"] == ["MongoDB 9.0.4 at 127.0.0.1:27017", "liminal: 2 collections (gov_items, news)"]
    assert servers.clients[-1].more == {} and len(servers.clients) == 1
    # opened as the app opens it: this process's own client of the server here
    handle = {"news": "the news collection"}
    monkeypatch.setattr(mongo, "database", lambda: handle)
    assert plugin.open(own) is handle and plugin.open(own, "news") == "the news collection"
    status = plugin.status()
    assert (status["engine"], status["server"], status["shares"], status["defaultPort"]) == ("mongodb", True, False, 27017)
    assert status["instances"][0]["sharedWords"].startswith("a server's own to decide") and status["can"]["share"] is False
    with pytest.raises(Refusal, match="a server's own to decide"):
        plugin.share("local", "linux::Ubuntu", "read")
    with pytest.raises(Refusal, match="local is MongoDB's own, on this machine alone: it takes no sign-in"):
        plugin.set_credentials("local", "u", "p")
    with pytest.raises(Refusal, match="local is MongoDB's own: it is not forgotten"):
        plugin.forget("local")
    facts = plugin.api_facts()["MongoDB"]
    assert facts["The server here"] == "127.0.0.1:27017" and facts["PyMongo in this Python"] and "mongod installed here" in facts
    assert env == {}
    # seen from another system the server is that system's, and said so: nothing is asked
    monkeypatch.setattr(mounts, "foreign", lambda path, mounts=None: True)
    assert plugin.state(own) == {"method": "tcp", "methodTitle": "TCP", "address": "127.0.0.1:27017/liminal", "local": False,
                                 "state": "elsewhere", "why": plugin.state(own)["why"]}
    assert "listens there alone" in plugin.state(own)["why"]


def test_the_server_heres_port_is_its_instances_own_and_changed_while_it_is_stopped(mongos, monkeypatch):
    plugin, servers, env = mongos
    servers.at[("127.0.0.1", 27017)] = server()
    with pytest.raises(Refusal, match="the server here is running on 27017: stop it first"):
        plugin.set_port("local", 27018)
    del servers.at[("127.0.0.1", 27017)]
    servers.at[("127.0.0.1", 27019)] = server()
    with pytest.raises(Refusal, match="something listens at 127.0.0.1:27019 already"):
        plugin.set_port("local", 27019)
    assert plugin.set_port("local", 27017)["said"] == "the server here is on 27017 already" and env == {}
    moved = plugin.set_port("local", "27018")
    assert moved["ok"] and moved["said"] == "the server here starts on 27018 from now on"
    assert servers.fresh[-2:] == [("127.0.0.1", 27017), ("127.0.0.1", 27018)]  # both asked now: the answers decide
    assert moved["lines"][0] == "kept in the login's variables (LIMINAL_MONGO_PORT)" and "restart the integrator" in moved["lines"][1]
    assert env == {"LIMINAL_MONGO_PORT": "27018"}
    # an app started after reads it: the instance, and what a new connection is offered, follow
    monkeypatch.setenv("LIMINAL_MONGO_PORT", "27018")
    assert plugin.instance("local").port == 27018 and plugin.default_port() == 27018 and plugin.status()["defaultPort"] == 27018
    assert plugin.state(plugin.instance("local"))["address"] == "127.0.0.1:27018/liminal"
    # back to the usual one: nothing is kept for it
    back = plugin.set_port("local", 27017)
    assert back["said"] == "the server here starts on 27017 from now on" and env == {}
    for bad in (0, 99999, "x"):
        with pytest.raises(Refusal, match="a port is a number"):
            plugin.set_port("local", bad)


def test_a_database_on_another_server_is_connected_only_when_it_answers(mongos):
    plugin, servers, env = mongos
    servers.at[("127.0.0.1", 27020)] = server(dbs={"research": {"papers": []}})
    got = plugin.connect_to("research", "127.0.0.1:27020", database="research", holds="documents")
    assert got["ok"] and got["said"] == "research connected: 127.0.0.1:27020/research"
    assert got["lines"][:2] == ["MongoDB 9.0.4 at 127.0.0.1:27020", "research: 1 collection (papers)"]
    inst = plugin.instance("research")
    assert (inst.port, inst.database, inst.auth, inst.remote, inst.tls) == (27020, "research", False, False, False)
    assert plugin.state(inst)["state"] == "listening" and plugin.test("research")["ok"]
    # the port left out: the one the server here is on
    servers.at[("127.0.0.1", 27017)] = server(dbs={"other": {}})
    assert plugin.connect_to("other", "127.0.0.1", database="other")["said"] == "other connected: 127.0.0.1:27017/other"
    for kw, why in (({"where": "127.0.0.1:27021", "database": "research"}, "nothing listens at 127.0.0.1:27021"),
                    ({"where": "127.0.0.1:27020", "database": ""}, "which database"),
                    ({"where": "/tmp/mongodb-27017.sock", "database": "research"}, "is reached by tcp: not 'socket'")):
        with pytest.raises(Refusal, match=why):
            plugin.connect_to("x", **kw)
    assert sorted(i.name for i in plugin.instances()) == ["local", "other", "research"]
    # moved to another port: kept only when it answers there
    servers.at[("127.0.0.1", 27030)] = servers.at[("127.0.0.1", 27020)]
    assert plugin.set_port("research", 27030)["said"] == "research's port is 27030 now"
    with pytest.raises(Refusal, match="so research's port stays 27030"):
        plugin.set_port("research", 27031)


def test_a_server_that_signs_in_is_asked_with_the_role_given_looked_for_in_its_database_then_in_admin(mongos):
    plugin, servers, env = mongos
    servers.at[("127.0.0.1", 27020)] = server(users={"docs": {"reader": "r-secret"}, "admin": {"keeper": "k-secret"}},
                                              dbs={"docs": {"filings": []}, "books": {"ledger": []}})
    with pytest.raises(Refusal, match="did not answer, so it is not kept: command requires authentication"):
        plugin.connect_to("docs", "127.0.0.1:27020", database="docs")
    with pytest.raises(Refusal, match="did not answer, so it is not kept: Authentication failed"):
        plugin.connect_to("docs", "127.0.0.1:27020", database="docs", user="reader", password="wrong")
    assert env == {}  # a sign-in that did not work is forgotten again
    got = plugin.connect_to("docs", "127.0.0.1:27020", database="docs", user="reader", password="r-secret")
    assert got["lines"][0] == "MongoDB 9.0.4 at 127.0.0.1:27020, signed in as reader"
    assert servers.clients[-1].more == {"username": "reader", "password": "r-secret", "authSource": "docs"}
    # a role the server's keeper holds in admin: refused in the database, found in admin
    before = len(servers.clients)
    assert plugin.connect_to("books", "127.0.0.1:27020", database="books", user="keeper", password="k-secret")["ok"]
    assert [c.more["authSource"] for c in servers.clients[before:]] == ["books", "admin"]
    kept = env["MONGODB_INSTANCES"]
    assert "secret" not in kept and "secret" not in json.dumps(plugin.status()) and "secret" not in json.dumps(got)
    assert env["MONGODB_DOCS_USER"] == "reader" and env["MONGODB_BOOKS_PASSWORD"] == "k-secret"
    assert [r["signsIn"] for r in plugin.status()["instances"][1:]] == [True, True]
    # opened with its sign-in; its client is the caller's to close
    db = plugin.open(plugin.instance("docs"))
    assert db.name == "docs" and db.client.more["username"] == "reader" and plugin.open(plugin.instance("docs"), "filings").name == "filings"
    for c in servers.clients:
        c.close()
    # its sign-in gone from the login: said, nothing asked
    del env["MONGODB_DOCS_PASSWORD"]
    assert "docs's sign-in is not in the login" in plugin.test("docs")["said"]
    with pytest.raises(PermissionError, match="sign-in is not in the login"):
        plugin.open(plugin.instance("docs"))


def test_a_server_off_this_machine_is_kept_only_when_asked_twice_over_tls_and_signed_in(mongos):
    plugin, servers, env = mongos
    servers.at[("db.example.net", 27017)] = server(tls=True, users={"docs": {"reader": "far-secret"}}, dbs={"docs": {"a": []}})
    with pytest.raises(Refusal, match="db.example.net is not this machine") as first:
        plugin.connect_to("far", "db.example.net", database="docs", tls=True, user="reader", password="far-secret")
    assert first.value.accept == "accept_remote" and env == {} and servers.clients == []
    with pytest.raises(Refusal, match="only with TLS and a sign-in"):
        plugin.connect_to("far", "db.example.net", database="docs", accept_remote=True, user="reader", password="far-secret")
    got = plugin.connect_to("far", "db.example.net", database="docs", tls=True, accept_remote=True, user="reader", password="far-secret")
    assert got["lines"][0] == "MongoDB 9.0.4 at db.example.net:27017, signed in as reader, over TLS"
    assert servers.clients[-1].more == {"tls": True, "username": "reader", "password": "far-secret", "authSource": "docs"}
    inst = plugin.instance("far")
    assert inst.remote and inst.tls and inst.auth and plugin.state(inst)["state"] == "not asked"  # a status never asks it
    assert plugin.test("far")["ok"]  # a test the user starts does
    with pytest.raises(Refusal, match="it is reached with a sign-in alone"):
        plugin.set_credentials("far", "", "")


def test_a_new_database_gets_a_role_of_its_own_where_the_server_signs_in(mongos):
    plugin, servers, env = mongos
    with pytest.raises(Refusal, match="nothing listens at 127.0.0.1:27017.*a database is made on a server that runs"):
        plugin.new_database("notes")
    # the server here, which takes no sign-in: the database alone, saying what it is
    here = servers.at[("127.0.0.1", 27017)] = server(dbs={"liminal": {"news": []}})
    made = plugin.new_database("notes", holds="documents")
    assert made["ok"] and made["said"] == "notes made: 127.0.0.1:27017/notes"
    assert made["lines"][0] == f"the database notes made on 127.0.0.1:27017 (its {MARKER} collection says what it is)"
    (doc,) = here["dbs"]["notes"][MARKER]
    assert doc == {"_id": "instance", "name": "notes", "made": plugin.instance("notes").at, "holds": ["documents"],
                   "by": f"plugin-platform-mongodb {__version__}"}
    assert plugin.instance("notes").auth is False and here["made"] == []
    assert plugin.test("notes")["lines"][2] == f"made here on {doc['made'][:10]} to hold documents"
    with pytest.raises(Refusal, match="there is a database liminal on 127.0.0.1:27017 already: Connect keeps one"):
        plugin.new_database("again", database="liminal")
    # a server that signs in: a role of its own, for that database alone; the administrator is not kept
    guarded = servers.at[("127.0.0.1", 27020)] = server(users={"admin": {"root": "admin-secret"}})
    made = plugin.new_database("filings-2026", "127.0.0.1:27020", database="filings", admin_user="root", admin_password="admin-secret")
    assert made["lines"][1].startswith("the role liminal_filings_2026 made for it (readWrite on filings alone)")
    assert guarded["made"] == [("filings", "liminal_filings_2026", [{"role": "readWrite", "db": "filings"}])]
    inst = plugin.instance("filings-2026")
    assert inst.made and inst.auth and (inst.role, inst.grants, inst.database) == ("liminal_filings_2026", ("readWrite",), "filings")
    password = env["MONGODB_FILINGS_2026_PASSWORD"]
    assert guarded["users"]["filings"] == {"liminal_filings_2026": password} and len(password) >= 24
    everything = json.dumps(env) + json.dumps(made) + json.dumps(plugin.status())
    assert "admin-secret" not in everything and password not in json.dumps(made) + json.dumps(plugin.status()) + env["MONGODB_INSTANCES"]
    assert plugin.test("filings-2026")["lines"][0] == "MongoDB 9.0.4 at 127.0.0.1:27020, signed in as liminal_filings_2026"
    with pytest.raises(Refusal, match="127.0.0.1:27020 refused the administrator's sign-in: nothing was made"):
        plugin.new_database("third", "127.0.0.1:27020", admin_user="root", admin_password="nope")
    assert "third" not in guarded["dbs"] and "third" not in env["MONGODB_INSTANCES"]
    assert [i.name for i in plugin.instances()] == ["local", "notes", "filings-2026"]


def test_a_make_whose_marker_was_not_written_is_undone_and_its_retry_finishes(mongos):
    """The review of 2026-11-21, item 26: the role was made, the marker's write failed, and every retry's createUser
    then failed for good with the server's "User already exists"."""
    plugin, servers, env = mongos
    guarded = servers.at[("127.0.0.1", 27020)] = server(users={"admin": {"root": "admin-secret"}}, insert_fails=1)
    given = {"admin_user": "root", "admin_password": "admin-secret"}
    with pytest.raises(ConnectionError):
        plugin.new_database("filings", "127.0.0.1:27020", **given)
    assert guarded["dropped"] == [("filings", "liminal_filings")] and not guarded["users"].get("filings")
    assert env == {} and [i.name for i in plugin.instances()] == ["local"]  # neither half a sign-in nor an instance
    made = plugin.new_database("filings", "127.0.0.1:27020", **given)
    assert made["ok"] and guarded["dbs"]["filings"][MARKER][0]["name"] == "filings"
    assert guarded["users"]["filings"] == {"liminal_filings": env["MONGODB_FILINGS_PASSWORD"]}
    # the undoing did not reach the server either: the retry finds the role and no database, and takes it over
    guarded["insert_fails"], guarded["drop_fails"] = 1, True
    with pytest.raises(ConnectionError):
        plugin.new_database("notes", "127.0.0.1:27020", **given)
    assert "liminal_notes" in guarded["users"]["notes"] and "MONGODB_NOTES_PASSWORD" not in env
    guarded["drop_fails"] = False
    made = plugin.new_database("notes", "127.0.0.1:27020", **given)
    assert made["ok"] and made["lines"][1].startswith("the role liminal_notes was there from a make that stopped half way")
    assert guarded["updated"] == [("notes", "liminal_notes", [{"role": "readWrite", "db": "notes"}])]
    assert guarded["users"]["notes"] == {"liminal_notes": env["MONGODB_NOTES_PASSWORD"]}
    assert plugin.test("notes")["lines"][0] == "MongoDB 9.0.4 at 127.0.0.1:27020, signed in as liminal_notes"


def test_a_role_whose_password_could_not_be_kept_is_taken_back(mongos):
    plugin, servers, env = mongos
    guarded = servers.at[("127.0.0.1", 27020)] = server(users={"admin": {"root": "admin-secret"}})

    class Full(EnvironmentLogin):
        def save(self, variable, value):
            if variable.endswith("_PASSWORD") and value:
                raise Unauthorized("no room for it", 500)
            return super().save(variable, value)

    plugin.attach(plugin.app, Full(env=env))
    with pytest.raises(Unauthorized, match="no room for it"):
        plugin.new_database("filings", "127.0.0.1:27020", admin_user="root", admin_password="admin-secret")
    assert guarded["dropped"] == [("filings", "liminal_filings")] and "filings" not in guarded["users"].get("filings", {})
    assert env == {} and [i.name for i in plugin.instances()] == ["local"]  # neither half a sign-in nor an instance
    assert MARKER not in guarded["dbs"].get("filings", {})
