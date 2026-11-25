"""MongoDB for Liminal: the server the app runs on this machine as an instance of its own, its port its own setting,
databases on other servers beside it (a database plugin, plugin API 2.3: liminal_libs.storage.databases;
the platform's, drawn in its Databases section, since 0.2.0: it was plugin-integrator-mongodb).

The user, 2026-11-15: "for the integrator i need plugins for each type of database and in each plugin can setup either
new databases or connections to existing databases using many different types of IP or IPC methods. each instance in
the plugin has it's own configuration how it's shared, ports, permissions etc".

Its own instance, `local`, is the server the app keeps documents in when a plugin's documents are kept in MongoDB
(liminal-libs' mongo.py): mongod on 127.0.0.1 alone, started by the app when a store uses it and stopped when nothing
does, its data in the data folder's mongo/, its database `liminal`. With nothing set, nothing changes. Its port is the
instance's own (27017 unless you change it, here, while the server is stopped; kept where the app's own module reads
it, LIMINAL_MONGO_PORT, through the login).

Beside it you may connect a database on another server (one on this machine at another port; one off this machine
only when you say so twice, and then with TLS and a sign-in alone), or make a new one on a server you name: on a
server that signs in, with a role of its own that may read and write that database and no other (the administrator's
name and password are asked once and not kept; the role's password is made here, kept through the login and never
shown). A sign-in is two pairs through the login, never in a file.

One method, `tcp`: an address and a port. A Unix socket is not offered yet. The plugin keeps no shares: who reaches a
server is the server's to decide (the one here listens on this machine alone), and it says so. It never starts a
server to ask it anything, and a status asks this machine alone; another machine is asked only by a test you start."""
from __future__ import annotations

from importlib import metadata
from pathlib import Path

from liminal_libs import mongo, mounts
from liminal_libs.storage import databases
from liminal_libs.storage.databases import DatabasePlugin, Instance, Made, Refusal, new_password, now_iso, variable_of

from .apis import APIS, MONGODB

__version__ = "0.2.0"
LOCAL = "local"  # its own instance: the server here
MARKER = "liminal_instance"  # the collection a database made here says what it is in
PORT_VAR = "LIMINAL_MONGO_PORT"  # where the server here's port is kept: what liminal-libs' mongo.py reads
ROLE = "readWrite"  # what the role made with a new database may do, on that database alone
TIMEOUT_MS = 2000
REFUSED_SIGN_IN = 18  # the server's code for a sign-in it refuses (AuthenticationFailed)
USER_EXISTS = 51003  # the server's code for a createUser whose user is there already ("User ... already exists")


def mongo_client(host: str, port: int, timeout_ms: int = TIMEOUT_MS, **more):
    """A client of one server, for one question; closed by whoever asked. (A module name, so a test stands one in.)"""
    from pymongo import MongoClient

    return MongoClient(host, port, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms, socketTimeoutMS=5000,
                       directConnection=True, appname="liminal", **more)


def driver() -> str:
    """The PyMongo this Python carries, by its package's word (nothing is loaded to say it); "" when it has none."""
    try:
        return metadata.version("pymongo")
    except metadata.PackageNotFoundError:
        return ""


def _refused(e: BaseException) -> bool:
    return getattr(e, "code", None) == REFUSED_SIGN_IN


class MongodbPlugin(DatabasePlugin):
    name = "mongodb"
    title = "MongoDB"
    about = ("The MongoDB server the app runs on this machine as an instance of its own, its port its own setting, with "
             "databases on other servers beside it")
    api = "2.3"
    order = 702
    options = (variable_of("mongodb"), PORT_VAR)  # MONGODB_INSTANCES: what you add; the server here's port
    apis = APIS
    ENGINE = "mongodb"
    METHODS = ("tcp",)
    HOLDS = ("documents",)
    SERVER = True
    DRIVER = "pymongo"
    DRIVER_HINT = "pymongo is not installed in the app's Python (the app's own dependency: pip install pymongo)"
    SHARES = False
    SHARED = ("a server's own to decide: the one here listens on this machine alone (127.0.0.1) and takes no sign-in; "
              "another is reached with the role you give it")

    # -- the hooks ---------------------------------------------------------------------------------------------------
    def builtin(self, data_dir: Path) -> tuple[Instance, ...]:
        return (Instance(LOCAL, "The server here", where=mongo.HOST, method="tcp", port=mongo.port(), database=mongo.DATABASE,
                         holds=self.HOLDS,
                         note="started by the app when a plugin's documents are kept in MongoDB, stopped when nothing uses "
                              "it; its data in the data folder's mongo/, on 127.0.0.1 alone"),)

    def default_port(self) -> int:
        return mongo.port()  # the server here's, which is its instance's own and may have been changed

    def state(self, instance: Instance, data_dir: Path | None = None) -> dict:
        folder = Path(data_dir) if data_dir is not None else self.data_dir()
        if instance.builtin and mounts.foreign(folder):
            return {"method": "tcp", "methodTitle": "TCP", "address": f"{instance.where}:{instance.port}/{instance.database}",
                    "local": False, "state": "elsewhere",
                    "why": "it runs on the system that holds the data and listens there alone: not reached from here"}
        out = super().state(instance, folder)
        if instance.builtin:
            out["installed"] = mongo.binary() is not None
            if out["state"] == "not running":
                out["why"] = ("not running: started when a plugin's documents are kept in MongoDB, never to be asked"
                              + ("" if out["installed"] else "; mongod is not installed here"))
        return out

    def _client(self, instance: Instance, user: str | None = None, password: str | None = None, source: str | None = None):
        more: dict = {}
        if instance.tls:
            more["tls"] = True
        if user:
            more.update(username=user, password=password, authSource=source or instance.database)
        return mongo_client(instance.where, instance.port or mongo.PORT, **more)

    def _signed_in(self, instance: Instance, ask):
        """`ask(client)` answered by a client that signs in as the instance says: its role looked for in its own
        database first, then in the server's `admin` (where a role made by the server's keeper usually is)."""
        got = self.credentials(instance) if instance.auth else None
        if instance.auth and got is None:
            raise PermissionError(f"{instance.name}'s sign-in is not in the login: set its name and password again")
        sources = (instance.database, "admin") if got else (None,)
        for i, source in enumerate(sources):
            client = self._client(instance, *(got or (None, None)), source)
            try:
                return ask(client)
            except Exception as e:  # noqa: BLE001 - a refused sign-in is tried once more, against admin
                if not (_refused(e) and i + 1 < len(sources)):
                    raise
            finally:
                client.close()

    def _listens(self, instance: Instance) -> None:
        """ConnectionError when nothing listens at a server of this machine (asked now, not as a status remembered
        it: no server selection to wait out). Another machine is not asked here: its client says."""
        port = instance.port or mongo.PORT
        if databases.is_local(instance.where) and not databases.listening(instance.where, port, fresh=True):
            here = (instance.where, port) == (mongo.HOST, mongo.port())
            raise ConnectionError(f"nothing listens at {instance.where}:{port}"
                                  + (": the server here is started when a plugin's documents are kept in MongoDB, never "
                                     "to be asked" if here else ""))

    def open(self, instance: Instance, part: str = "", read_only: bool = True, data_dir: Path | None = None):
        """The instance's database (`part`: one of its collections), as PyMongo gives it; its client is closed by whoever
        asked (`.client.close()`), but for the server here, whose client is this process's own (mongo.client). A
        handle reads and writes as its role may: `read_only` is the caller's word, not the server's."""
        if instance.builtin:
            db = mongo.database()
        else:
            got = self.credentials(instance) if instance.auth else None
            if instance.auth and got is None:
                raise PermissionError(f"{instance.name}'s sign-in is not in the login: set its name and password again")
            db = self._client(instance, *(got or (None, None)))[instance.database]
        return db[part] if part else db

    def probe(self, instance: Instance, data_dir: Path) -> list[str]:
        self._listens(instance)

        def ask(client):
            client.admin.command("ping")
            try:
                version = str(client.server_info().get("version") or "?")
            except Exception as e:  # noqa: BLE001 - a role that may not ask the version still answers the rest
                if _refused(e):
                    raise
                version = "?"
            db = client[instance.database]
            names = sorted(n for n in db.list_collection_names() if not n.startswith("system."))
            made = db[MARKER].find_one({"_id": "instance"}) if MARKER in names else None
            return version, names, made

        version, names, made = self._signed_in(instance, ask)
        port = instance.port or mongo.PORT
        lines = [f"MongoDB {version} at {instance.where}:{port}" + (f", signed in as {instance.role}" if instance.auth else "")
                 + (", over TLS" if instance.tls else ""),
                 f"{instance.database}: {len(names)} collection{'' if len(names) == 1 else 's'}"
                 + (f" ({', '.join(names[:6])}{', ...' if len(names) > 6 else ''})" if names else "")]
        if made:
            lines.append(f"made here on {str(made.get('made') or '?')[:10]} to hold "
                         f"{', '.join(made.get('holds') or ()) or 'nothing yet'}")
        return lines

    def make(self, instance: Instance, data_dir: Path, admin_user: str = "", admin_password: str = "", **given) -> Made:
        host, port, name = instance.where, instance.port or mongo.PORT, instance.database
        try:
            self._listens(instance)
        except ConnectionError as e:
            raise Refusal(f"{e}: a database is made on a server that runs") from None
        admin = self._client(instance, admin_user or None, admin_password or None, "admin")
        lines, role = [], ""
        try:
            try:
                admin.admin.command("ping")
                there = admin.list_database_names()
            except Exception as e:  # noqa: BLE001 - the server's refusal of the administrator, in words of its own
                if _refused(e):
                    raise Refusal(f"{host}:{port} refused the administrator's sign-in: nothing was made") from None
                raise
            if name in there:
                raise Refusal(f"there is a database {name} on {host}:{port} already: Connect keeps one that exists")
            db = admin[name]
            if admin_user:  # a server that signs in: a role of its own, for this database alone
                role, password = f"liminal_{instance.name.replace('-', '_')}", new_password()
                roles = [{"role": ROLE, "db": name}]
                try:
                    db.command("createUser", role, pwd=password, roles=roles)
                except Exception as e:  # noqa: BLE001 - only the role of a try that stopped half way is taken over
                    if getattr(e, "code", None) != USER_EXISTS and "already exists" not in str(e):
                        raise
                    # The role of an earlier make whose database was never written (it is not there: see above) and
                    # whose undoing did not reach the server either: this make finishes it, with a password of its
                    # own and this database's grant alone, rather than failing for good with the server's "User
                    # already exists" (the review of 2026-11-21, item 26).
                    db.command("updateUser", role, pwd=password, roles=roles)
                    lines.append(f"the role {role} was there from a make that stopped half way: taken over, its "
                                 "password renewed")
                try:
                    self.keep_credentials(instance.name, role, password)
                except Exception:
                    db.command("dropUser", role)  # a role nobody holds the password of is taken back
                    raise
                lines.append(f"the role {role} made for it ({ROLE} on {name} alone); its password kept through the login, "
                             "never shown")
            try:
                db[MARKER].insert_one({"_id": "instance", "name": instance.name, "made": instance.at or now_iso(),
                                       "holds": list(instance.holds), "by": f"plugin-platform-mongodb {__version__}"})
            except Exception:
                # No database without its marker, so nothing half made is left: the role and its kept sign-in are
                # taken back (the review of 2026-11-21, item 26; a retry's createUser failed on the role left here).
                if role:
                    try:
                        db.command("dropUser", role)
                    except Exception:  # noqa: BLE001 - a server gone by now: the retry takes the role over (above)
                        pass
                    self._forget_credentials(instance.name)
                raise
        finally:
            admin.close()
        first = f"the database {name} made on {host}:{port} (its {MARKER} collection says what it is)"
        return Made((first, *lines), role=role, grants=(ROLE,) if role else ())

    def own_port(self, instance: Instance, port: int, data_dir: Path) -> dict:
        """The server here's port: changed while the server is stopped, kept where the app's own module reads it."""
        now = mongo.port()
        if port == now:
            return {"ok": True, "said": f"the server here is on {port} already", "lines": []}
        if databases.listening(mongo.HOST, now, fresh=True):
            raise Refusal(f"the server here is running on {now}: stop it first (liminal-charts mongo stop); its port is "
                          "changed while it is stopped")
        if databases.listening(mongo.HOST, port, fresh=True):
            raise Refusal(f"something listens at {mongo.HOST}:{port} already: another port")
        where = self.login.save(PORT_VAR, None if port == mongo.PORT else str(port))
        return {"ok": True, "said": f"the server here starts on {port} from now on",
                "lines": [f"kept in {where} ({PORT_VAR})",
                          "each app reads it when it starts: restart the integrator and the charts app before the server "
                          "is next used"]}

    def api_facts(self) -> dict:
        """What is known of MongoDB here without asking any server: the driver this Python carries, the mongod
        installed here, and where the server here listens when it runs."""
        return {MONGODB.name: {"PyMongo in this Python": driver() or "not installed",
                               "mongod installed here": mongo.version() or "none",
                               "The server here": f"{mongo.HOST}:{mongo.port()}"}}


DATABASE = MongodbPlugin()
