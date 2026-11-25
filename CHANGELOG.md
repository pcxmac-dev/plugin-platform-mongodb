# Changelog

## 0.2.0 (2026-11-25)

Renamed `plugin-platform-mongodb` (the package `plugin_platform_mongodb`; it was `plugin-integrator-mongodb`): a platform
plugin of the Databases section (Monday list item 30, step 3; the user, 2026-11-25: the packages renamed
`plugin-platform-sqlite`, `-duckdb`, `-mongodb`, plugin names and settings kept). Since liminal-libs 1.90.0
`DatabasePlugin` is a `PlatformPlugin` (SYSTEM "platform", SECTION "databases"; KIND "database" kept), so the
platform draws it and the integrator and the charts include the platform to open it.

- Its name is still `mongodb`: every instance kept under `MONGODB_INSTANCES` and every kept sign-in is untouched.
- The entry point group is the same (`liminal.providers`), as for every platform plugin.
- A database it makes now says `by: plugin-platform-mongodb 0.2.0` in its `liminal_instance`; ones made before keep
  what they said.
- Uninstall `plugin-integrator-mongodb` and take its checkout out of `plugins/` in the same step: the registry refuses a
  second plugin for one engine.
- Needs liminal-libs>=1.90.0.

## 0.1.1 (2026-11-24)

A make that stopped half way no longer fails for good (the review of 2026-11-21, item 26). On a server that signs
in, `make` made the database's role, kept its password, then wrote the marker; when that write failed, the role and
its kept sign-in were left behind, and every retry's `createUser` failed with the server's "User already exists".
Now a failed marker write takes the role back (`dropUser`) and forgets its sign-in, and a retry that finds the role
with no database (its undoing did not reach the server either) takes it over (`updateUser`: a new password, this
database's grant alone) and finishes, saying so. Test: a marker write that fails, then its retry; then one whose
undoing fails too, then its retry.

## 0.1.0 (2026-11-16)

The first release: MongoDB as a database plugin (plugin API 2.3, liminal-libs 1.61.0; the user, 2026-11-15: "for the
integrator i need plugins for each type of database and in each plugin can setup either new databases or connections
to existing databases using many different types of IP or IPC methods. each instance in the plugin has it's own
configuration how it's shared, ports, permissions etc").

- Its own instance `local`: the server the app runs on this machine alone, never started to be asked. Its port is the
  instance's own, changed while the server is stopped and kept where the app's own module reads it.
- Connect (a database on another server, kept only when it answers, signing in where the server wants it) and New
  database (a role of its own, readWrite on that database alone, where the server signs in; the administrator asked
  once and not kept).
- One method, `tcp`; off this machine only when asked twice, over TLS and signed in.
- A sign-in is two pairs through the login: never in the value the instances are kept in, never in what a page is
  given. Every client it makes is closed after the question.
- Its API card: MongoDB through PyMongo, every address one of mongodb.com's own pages, read on 2026-11-16.
