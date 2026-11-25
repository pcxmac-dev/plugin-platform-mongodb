"""What the MongoDB plugin attaches to (plugin API 2.2, liminal_libs.sources.apis; the user, 2026-11-11: "each plugin
should reflect the the API its attached to, and present links that provide documentation ... it should also expose more
of what the API is about"): a MongoDB server, through PyMongo, MongoDB's Python driver.

Every address is one of MongoDB's own pages (mongodb.com), each read on 2026-11-16 (`VERIFIED`): the Database Manual
(9.0 the current release series), mongod and its options, Connection Strings, the commands createUser, dbStats,
serverStatus, ping and shutdown, the $collStats stage, Built-In Roles, TLS/SSL (Transport Encryption), IP Binding in
Self-Managed Deployments, the WiredTiger Storage Engine, the PyMongo driver's documentation (4.x current), the release
notes and the Server Side Public License.

What those pages say and the plugin stands on: mongod binds to localhost unless told otherwise, and listens on 27017
unless given another port; createUser names the new user as the command's own value, with its password and its roles;
createUser and shutdown are not supported on Atlas clusters, so a database there is connected with a role made in
Atlas itself, not made from here."""
from __future__ import annotations

from liminal_libs.sources.apis import Api, Area, Call, Link

VERIFIED = "2026-11-16"
MANUAL = "https://www.mongodb.com/docs/manual/"
MONGOD = MANUAL + "reference/program/mongod/"
STRINGS = MANUAL + "reference/connection-string/"
CREATE_USER = MANUAL + "reference/command/createUser/"
ROLES = MANUAL + "reference/built-in-roles/"
DB_STATS = MANUAL + "reference/command/dbStats/"
COLL_STATS = MANUAL + "reference/operator/aggregation/collStats/"
SERVER_STATUS = MANUAL + "reference/command/serverStatus/"
PING = MANUAL + "reference/command/ping/"
SHUTDOWN = MANUAL + "reference/command/shutdown/"
TLS = MANUAL + "core/security-transport-encryption/"
BINDING = MANUAL + "core/security-mongodb-configuration/"
WIREDTIGER = MANUAL + "core/wiredtiger/"
NOTES = MANUAL + "release-notes/"
PYMONGO = "https://www.mongodb.com/docs/languages/python/pymongo-driver/current/"
SSPL = "https://www.mongodb.com/legal/licensing/server-side-public-license"

MONGODB = Api(
    name="MongoDB",
    maker="MongoDB, Inc. (mongodb.com)",
    about=("A document database server: databases of collections of documents, reached over the network by a driver. The "
           "app keeps documents of uneven shape in one (releases with their files, headlines, filings) when a plugin's "
           "documents are kept in MongoDB: a mongod of its own on this machine alone, started when a store uses it. The "
           "plugin reaches a server through PyMongo, MongoDB's Python driver."),
    kind="sdk",
    base="mongodb://127.0.0.1:27017/liminal for the server here (its port its instance's own); each other instance's address",
    version="MongoDB 9.0 (the server here: 9.0.4), through PyMongo 4.x (4.19)",
    auth=("the server here takes none and listens on this machine alone; another signs in with a role, its name and "
          "password kept through the login, and off this machine over TLS alone"),
    limits="",
    costs="",
    links=(
        Link("MongoDB Database Manual", MANUAL, "docs"),
        Link("mongod: the server's program and its options", MONGOD, "reference"),
        Link("Connection Strings", STRINGS, "reference"),
        Link("PyMongo, the Python driver", PYMONGO, "sdk"),
        Link("Built-In Roles", ROLES, "reference"),
        Link("TLS/SSL (Transport Encryption)", TLS, "guide"),
        Link("IP Binding in Self-Managed Deployments", BINDING, "guide"),
        Link("WiredTiger Storage Engine", WIREDTIGER, "guide"),
        Link("Release Notes", NOTES, "changelog"),
        Link("Server Side Public License (SSPL)", SSPL, "terms"),
    ),
    areas=(
        Area("The server (mongod)", "the server's program: where its data is, the address and the port it listens on "
             "(27017 unless given another), its log, its cache", MONGOD,
             covered="the server here is its own instance; its port is the instance's own, changed while it is stopped"),
        Area("IP binding", "mongod listens on localhost alone unless it is told other addresses", BINDING,
             covered="the server here is on 127.0.0.1 alone; an instance off this machine is kept only when asked twice"),
        Area("TLS", "the connections to a server encrypted, with certificates", TLS,
             covered="an instance off this machine is reached over TLS alone"),
        Area("Users and roles", "who may sign in to a database, and what each role may do there", ROLES,
             covered="a database made on a server that signs in gets a role of its own, readWrite on it alone; a sign-in "
                     "is two pairs through the login"),
        Area("Database commands", "what a client asks a server: ping, the server's build, a database's collections, the "
             "databases, a user made or dropped",
             covered="Test asks ping, the build and the collections; New database the databases and createUser"),
        Area("The Python driver (PyMongo)", "MongoClient and what it gives: databases, collections, commands", PYMONGO,
             covered="every client it opens: one server, short waits, closed after the question"),
        Area("Storage statistics", "a database's and a collection's sizes and counts from the server's own figures",
             DB_STATS),
        Area("The server's status and its shutdown", "what a running server says of itself, and its clean end",
             SERVER_STATUS),
        Area("WiredTiger's cache", "the storage engine's memory: half of the machine's beyond its first gigabyte unless "
             "it is set", WIREDTIGER),
        Area("Connection strings", "a server's address as one string: mongodb:// with every member listed, or "
             "mongodb+srv://", STRINGS),
        Area("Replica sets, sharding and Atlas", "several servers as one, and MongoDB's hosted service", MANUAL),
    ),
    calls=(
        Call("MongoClient(host, port, serverSelectionTimeoutMS=, directConnection=True, tls=, username=, password=, "
             "authSource=)", "a client of one server", "The Python driver (PyMongo)",
             used="every client it opens, closed after the question", docs=PYMONGO),
        Call("ping", "whether a server answers commands", "Database commands", used="Test, and before a database is made",
             docs=PING),
        Call("buildInfo (MongoClient.server_info())", "the server's version", "Database commands",
             used="Test: which MongoDB answers"),
        Call("listCollections", "a database's collections", "Database commands", used="Test: what the database holds"),
        Call("listDatabases", "the databases a server has", "Database commands",
             used="New database: never over one that is there"),
        Call("createUser", "a user made in a database: its name the command's own value, with its password and roles",
             "Users and roles", used="New database on a server that signs in: a role of its own, readWrite on that "
             "database alone", docs=CREATE_USER, writes=True),
        Call("dropUser", "a user removed from a database", "Users and roles",
             used="the role taken back when its password could not be kept through the login", writes=True),
        Call("insert into liminal_instance", "a document written", "Database commands",
             used="a database made here says what it is in it: its name, the day, what it is to hold", writes=True),
        Call("dbStats", "a database's collections, documents and sizes", "Storage statistics", docs=DB_STATS),
        Call("$collStats with storageStats", "a collection's count and sizes, the first stage of an aggregation",
             "Storage statistics", docs=COLL_STATS),
        Call("serverStatus", "a running server's version, uptime, process and memory", "The server's status and its shutdown",
             docs=SERVER_STATUS),
        Call("shutdown", "the server ended cleanly, asked of its admin database", "The server's status and its shutdown",
             docs=SHUTDOWN, writes=True),
        Call("mongod --dbpath --bind_ip --port --wiredTigerCacheSizeGB --logpath", "the server started with its data's "
             "folder, its address, its port, its cache's size and its log", "The server (mongod)", docs=MONGOD, writes=True),
    ),
    verified=VERIFIED,
)

APIS = (MONGODB,)
