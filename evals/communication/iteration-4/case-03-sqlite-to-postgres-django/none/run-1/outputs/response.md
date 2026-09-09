The path that keeps your data is: dump SQLite to a fixture, point Django at a fresh Postgres database, run `migrate` to build the schema there, then load the fixture. The mechanics are short. The part that actually costs time is step 7, because SQLite accepted data that Postgres will reject.

I can't see your project, so I don't know your Django version, your apps, or whether the SQLite file is still in sync with your migrations. Step 1 checks that last one; everything below assumes a single `default` database.

## 1. Confirm SQLite matches your migrations

```bash
python manage.py showmigrations
python manage.py makemigrations --check --dry-run
```

Every migration should be marked `[X]`, and `makemigrations --check` should report no changes. Fix any drift before continuing: the fixture is serialized through your current models and will be loaded into a schema built from your migration files, so the two have to agree.

Back up the SQLite file now and keep it until Postgres has been fine for a few days.

```bash
cp db.sqlite3 db.sqlite3.backup
```

## 2. Install the driver

Check your version first with `python -m django --version`. On Django 4.2 or later, use psycopg 3:

```bash
pip install "psycopg[binary]"
```

On Django 4.1 or earlier, install `psycopg2-binary` instead. Add whichever you pick to `requirements.txt` or `pyproject.toml`.

## 3. Create the role and database

```bash
psql -U postgres -c "CREATE ROLE myapp LOGIN PASSWORD 'devpassword' CREATEDB;"
psql -U postgres -c "CREATE DATABASE myapp_dev OWNER myapp ENCODING 'UTF8';"
```

`CREATEDB` on the role is not optional if you run tests. Django's test runner creates and drops `test_myapp_dev` on every run, and without that privilege every run dies with "permission denied to create database".

## 4. Dump the data (while settings still point at SQLite)

```bash
python manage.py dumpdata \
  --natural-foreign \
  --exclude contenttypes \
  --exclude auth.Permission \
  --exclude admin.logentry \
  --exclude sessions.session \
  --indent 2 \
  -o dump.json
```

(In PowerShell, put it on one line or use backticks instead of backslashes.)

Why each piece matters:

- `--natural-foreign` serializes foreign keys to content types and permissions by name, `["auth", "user"]`, instead of by integer id. Those ids are assigned in migration order and will not line up on the new database. Skipping this is the classic cause of a load that reports success but attaches objects to the wrong content types.
- `--exclude contenttypes --exclude auth.Permission` leaves out rows that `migrate` recreates on the Postgres side. Loading yours on top of those trips the unique constraint on `(app_label, model)` and the load aborts.
- `admin.logentry` and `sessions.session` are dev noise. Drop them unless you want the admin history.
- `-o dump.json` rather than `> dump.json`. Windows PowerShell 5.1 redirection writes UTF-16 with a BOM and `loaddata` will not parse it. Django's `-o` writes UTF-8 whatever the shell does.

One thing to leave off: do not add `--natural-primary`, even though most guides pair it with `--natural-foreign`. It omits the primary key for any model that defines `natural_key()`, and `AbstractBaseUser` defines one, so your users get renumbered on load. Real foreign keys survive that (they resolve by username), but anything holding a raw integer user id, a `GenericForeignKey` to User or a denormalized column, silently points at the wrong person.

If the dump runs to hundreds of MB, `loaddata` holds the whole thing in memory. On Django 4.2+ you can use `--format jsonl -o dump.jsonl`, which loads line by line.

## 5. Point settings at Postgres

```python
# settings.py
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "myapp_dev"),
        "USER": os.environ.get("PGUSER", "myapp"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}
```

Two details. The engine string is `django.db.backends.postgresql`; `postgresql_psycopg2` is the pre-2.0 alias and you do not want it. And use `127.0.0.1`, not `localhost`, which resolves to `::1` first on Windows and adds a per-connection stall if Postgres is listening on IPv4 only.

Keep the old SQLite block in the file, commented out, until the load is verified. Keep the password in `.env` or your shell profile, not in `settings.py`.

## 6. Build the schema and load

```bash
python manage.py migrate
python manage.py loaddata dump.json
```

If any app lacks a `migrations/` package, follow the first command with `python manage.py migrate --run-syncdb`, or its tables will not exist and the load will fail on them.

## 7. Expect the load to fail at least once

This is normal, and it is the real work. SQLite has dynamic typing and mostly ignores `max_length`, so it stored things your Postgres schema forbids. What comes out, and what each one means:

- `null value in column "x" violates not-null constraint`: rows written before you added the field, or written by raw SQL. Fix them in SQLite, re-dump, or add a default plus a data migration.
- `value too long for type character varying(N)`: a `CharField` whose `max_length` SQLite never enforced.
- `invalid input syntax for type integer / numeric / timestamp`: a string sitting in a numeric column, or a date like `0000-00-00`.
- `insert or update on table "x" violates foreign key constraint`: an orphaned row pointing at a deleted parent. SQLite only enforces foreign keys when `PRAGMA foreign_keys=ON`, which older code often left off.

`loaddata` runs in one transaction, so a failure leaves Postgres clean and you can fix and retry. The error names the model and the offending object, so work through them one at a time. Fix the data in SQLite where you can, so the fix survives a re-dump.

## 8. Verify

Run this against SQLite before you switch, and again after the load, then diff the two outputs:

```bash
python manage.py shell -c "from django.apps import apps; [print(m._meta.label, m._default_manager.count()) for m in apps.get_models()]"
```

Only content types, permissions, log entries and sessions should differ.

`loaddata` resets Postgres sequences after a successful load, so creating new objects should just work. If your first create instead raises `duplicate key value violates unique constraint "..._pkey"`, that is the sequence sitting behind your loaded ids:

```bash
python manage.py sqlsequencereset app1 app2 | python manage.py dbshell
```

Then run the test suite and click through the app.

## Behavior that changes once you are on Postgres

- `__contains` and `__startswith` become case-sensitive. SQLite's `LIKE` is case-insensitive for ASCII, so `filter(name__contains="foo")` used to match "Foo". Search boxes are where this bites. Use `__icontains` wherever you meant case-insensitive.
- NULL ordering flips. Postgres sorts NULLs last ascending and first descending; SQLite does the opposite. Where it matters, be explicit with `F("field").asc(nulls_last=True)`.
- Alphabetical order can shift, because Postgres orders by the database collation rather than SQLite's byte comparison.
- Type mismatches now raise. Comparing a string against an integer column, or mixed-type arithmetic in an annotation, was silently coerced before and now raises `ProgrammingError` or `DataError`.
- `DecimalField` values are real `numeric` now, so figures that drifted through SQLite's float storage may differ in the last digits.
- Raw SQL needs review. Grep for `.raw(`, `connection.cursor()`, `RunSQL`, and `PRAGMA`. SQLite-only constructs such as `strftime()`, `datetime()`, `IFNULL()`, `AUTOINCREMENT` and every `PRAGMA` have no Postgres equivalent as written.

## What I could not verify

Working without the repo, these are assumptions rather than checks:

- Your Django version, which decides psycopg 3 versus psycopg2.
- That the SQLite schema is actually in sync with the migration files (step 1 tests it).
- That there is one database and no custom `DATABASE_ROUTERS`, and that `settings.py` holds no SQLite-specific `OPTIONS` or `TEST` config, or a `dj-database-url` call you would edit instead of the block in step 5.
- Which apps exist, whether any lack migrations, and whether any model defines its own `natural_key()` beyond the built-ins.
- The size of the data, which decides whether plain `loaddata` is fine, or you want `--format jsonl`, or `pgloader` for something genuinely large.
- Whether the codebase contains raw SQL or SQLite-specific database functions.

Point me at the project directory and I will run steps 1 through 4 and stop with the fixture written, so you can inspect it before anything touches Postgres.
