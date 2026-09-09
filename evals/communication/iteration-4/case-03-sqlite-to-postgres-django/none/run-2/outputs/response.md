Use Django's own serializer for this, not a table-level copy. Dump from SQLite with natural keys, build a fresh schema in Postgres with `migrate`, then load the dump. Tools like pgloader will move the tables, but they leave you reconciling `django_content_type` and `auth_permission` by hand, and that is the part that actually breaks.

I don't have your project, so `myapp`, `myapp_dev`, and `db.sqlite3` below are placeholders, and the steps assume a single default database with `manage.py` at the project root.

**1. Back up, and confirm the schema matches your migrations**

```bash
cp db.sqlite3 db.sqlite3.backup
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

`db.sqlite3.backup` is your rollback. The `--check` run matters: if the SQLite schema drifted from the migration files (a model edited without a migration), the fresh Postgres schema will not have the columns your dump refers to, and the load fails in a confusing way. Fix that while you are still on SQLite.

**2. Dump the data while still pointed at SQLite**

```bash
python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --exclude sessions.session \
  --indent 2 -o dump.json
```

Each flag earns its place:

- `--natural-foreign` serializes foreign keys as natural keys instead of integer PKs. That is what lets `user.user_permissions` and `group.permissions` survive, because the permission rows in Postgres will be brand new with different integer IDs.
- `--exclude contenttypes --exclude auth.permission` because `migrate` recreates both from your models. Dumping them gives you duplicate-key errors on load.
- `-o dump.json` rather than `> dump.json`. On PowerShell the redirect writes UTF-16LE and `loaddata` cannot parse it. `-o` writes UTF-8 everywhere.
- Sessions and admin log entries are dev noise. Dropping sessions logs you out once.

Put `dump.json` at the project root, not inside any `fixtures/` directory, so test fixture autodiscovery does not pick it up.

**3. Install the driver**

Django 4.2 and newer: `pip install "psycopg[binary]"`. Django 4.1 and older: `pip install psycopg2-binary`. Add it to `requirements.txt`. Nothing needs removing, since the SQLite backend ships with Python.

**4. Create the role and database**

```bash
psql -U postgres -c "CREATE ROLE myapp WITH LOGIN PASSWORD 'devpassword' CREATEDB;"
psql -U postgres -c "CREATE DATABASE myapp_dev OWNER myapp ENCODING 'UTF8';"
```

`CREATEDB` on the role is not optional if you run `manage.py test`. Django creates and drops `test_myapp_dev` on every run, and without that privilege the whole suite dies at startup.

**5. Point settings at Postgres**

```python
# settings.py
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "myapp_dev"),
        "USER": os.environ.get("PGUSER", "myapp"),
        "PASSWORD": os.environ.get("PGPASSWORD", "devpassword"),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}
```

Use `django.db.backends.postgresql`, not the old `postgresql_psycopg2` alias. Read the values from env vars even though this is dev; it is the same block you will reuse for staging. Prefer `127.0.0.1` over `localhost` if you hit connection oddities, since `localhost` can resolve to an IPv6 address the server is not listening on.

**6. Build the schema, then load**

```bash
python manage.py migrate
python manage.py loaddata dump.json
```

`migrate` against the empty database creates your tables plus fresh contenttypes and permissions. `loaddata` runs in a single transaction, so a failure part of the way through leaves the database untouched; fix the offending data and rerun rather than cleaning up. It also resets the Postgres sequences for the models it loaded, so the next insert will not collide with an existing ID. Confirm that with one create through the shell or admin before you trust it.

**7. Verify by row count, not by feel**

Temporarily add the old file as a second alias:

```python
DATABASES["old_sqlite"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "db.sqlite3.backup",
}
```

Then in `python manage.py shell`:

```python
from django.apps import apps
for m in apps.get_models():
    old = m.objects.using("old_sqlite").count()
    new = m.objects.using("default").count()
    if old != new:
        print(f"{m._meta.label}: {old} -> {new}")
```

`ContentType`, `Permission`, `Session`, and `LogEntry` should differ; that is the exclusions doing their job. Anything else that differs is a real problem. Remove the extra alias once you are satisfied.

**What will behave differently from now on**

SQLite is permissive and Postgres is not. Three differences bite in practice.

`__contains` was quietly case-insensitive. SQLite's `LIKE` ignores case for ASCII, so `filter(name__contains="ana")` matched "Banana" and will stop doing so. Grep for `__contains` and `__startswith` and decide which ones should have been `__icontains` all along. This is documented Django behavior, not a bug in either backend.

Unordered querysets had a stable order and no longer do. SQLite tends to return rows in rowid order, so `.all()` without `order_by()` looked sorted by ID. Postgres makes no such promise, particularly after updates. Tests asserting `qs[0]` is a specific object will start failing intermittently. Add explicit ordering.

Constraints are enforced now. `max_length` was ignored by SQLite and becomes a real `varchar(n)`, so an over-long value that saved fine before will be rejected. Same for NULLs in non-nullable columns. If the load rejects a row, that row was already invalid; the move just surfaced it.

**Errors you are likely to hit**

| Error | Cause |
|---|---|
| `duplicate key value violates unique constraint "django_content_type_..."` | contenttypes got into the dump; re-dump with the excludes |
| `Permission matching query does not exist` | dumped without `--natural-foreign` |
| `value too long for type character varying(N)` | a row exceeds `max_length`; fix the row in the SQLite copy, or widen the field and add a migration |
| `null value in column "x" violates not-null constraint` | SQLite accepted a NULL that Postgres will not |
| `Expecting value: line 1 column 1` during `loaddata` | UTF-16 file from a PowerShell redirect; re-dump with `-o` |
| `FATAL: role "myapp" does not exist` | step 4 ran against a different cluster or port than settings point at |

**What I could not check**

I have not seen your project, so several things are assumptions rather than facts: your Django version, which decides psycopg 3 versus psycopg2; whether you have a custom user model, `DATABASE_ROUTERS`, or more than one database alias, any of which changes the dump and load steps; whether any migration contains a `RunPython` data step, since those already ran once on SQLite and will run again against the empty Postgres database, potentially colliding with the same rows in your dump; whether you use `django.contrib.sites`, whose post-migrate `Site` row can conflict with a dumped one; and how much data is involved. `dumpdata` holds the full queryset in memory, which is fine for a dev database and wrong past a few million rows. At that size the answer is pgloader plus a manual contenttypes and permissions fixup instead.
