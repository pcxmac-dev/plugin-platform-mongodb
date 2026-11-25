# plugin-platform-mongodb

MongoDB for [Liminal](https://github.com/pcxmac-dev/liminal-charts): the server the app runs on this machine
as an instance of its own, its port its own setting, with databases on other servers beside it.

## What a database plugin is

A Liminal plugin of the platform's (plugin API 2.3, `liminal_libs.storage.databases`), drawn in its Databases
section: one engine's. It holds
**instances**. An instance is a database the plugin made, or a connection to one that exists, and each has its own
configuration: what it holds, where it is, the method it is reached by, its port, who else may attach and how far,
and on a server the role used there. The platform's Databases section lists them, tests them and changes them;
the integrator and the charts include the platform and open them in their own process.

- **With nothing set, nothing changes.** The plugin's own instance is what the app keeps in this engine today, where
  it is and opened as it is.
- **What you add is kept through the plugin's login**, as one value under `MONGODB_INSTANCES`: never in a file of this
  software's. A sign-in is two more pairs through the login, never in that value and never shown.
- **A change is made by the system that holds the data alone.** The suite on another system (the one inside WSL) reads
  what is kept there and changes nothing of it.
- **Forgetting an instance removes nothing**: what it holds stays where it is. Only you remove data.

## Installing

The app finds it through the entry point group `liminal.providers` and lists it as `package:
plugin-platform-mongodb`, with this package's version; a checkout in the workspace's `plugins/` folder is loaded
from there. It needs `liminal-libs` 1.90.0 or newer and `pymongo`.

```
python -m pip install -e ".[dev]"
python -m pytest -q
```

It was `plugin-integrator-mongodb` (0.1.x) until 0.2.0. The plugin's name is still `mongodb`, so every instance kept
under `MONGODB_INSTANCES` and every kept sign-in stays as it was. Only one of the two may be installed or in
`plugins/`: the registry refuses a second plugin for one engine.

The tests open only files of their own; no server is started, asked or needed (stand-in servers); one of them reads the makers' documentation pages, and only with
`LIMINAL_VENDOR_PAGES=1`.

## Its instances

- **`local`, its own**: the server the app keeps documents in when a plugin's documents are kept in MongoDB: mongod on
  127.0.0.1 alone, started by the app when a store uses it and stopped when nothing does, its data in the data
  folder's `mongo/`, its database `liminal`. The plugin never starts it to ask it anything: when it is not running,
  it says so. **Its port is the instance's own**: 27017 unless you change it, here, while the server is stopped; it is
  kept where the app's own module reads it (`LIMINAL_MONGO_PORT`, through the login), and each app reads it when it
  starts.
- **Connect**: a database on another server, kept only when it answers: one on this machine at another port, or one
  off this machine. A server that signs in is given the role's name and password with the connection; the role is
  looked for in its own database first, then in the server's `admin`.
- **New database**: on a server you name. On a server that signs in, with a role of its own that may read and write
  that database and no other; the administrator's name and password are asked once and not kept, and the role's
  password is made here, kept through the login and never shown. A role whose password could not be kept is taken
  back. The database says what it is in a small collection (`liminal_instance`). MongoDB's hosted service does not
  take these commands: a database there is connected with a role made there.

## Its method

**`tcp`**: an address and a port. **Off this machine only when you say so twice**, and then over TLS and signed in
alone. A status asks this machine alone whether a server listens; another machine is asked only by a test you start.
A Unix socket is not offered yet.

## Sharing

The plugin keeps no shares, and says so: who reaches a server is the server's to decide. The one here listens on this
machine alone and takes no sign-in.

## Its API

Its page in every app shows what it attaches to (`DATABASE.apis`): the maker's pages, every part of the engine with what the plugin does with it, and the calls it makes among the rest; and what it knows of the engine here without asking anything (`DATABASE.api_facts()`).
