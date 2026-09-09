The reliable path is Django's own serialization: dump the SQLite data to JSON, point `settings.py` at Postgres, run `migrate` against the empty Postgres database, then `loaddata` the JSON back in. Django builds the schema from your migrations, so you get correct Postgres column types instead of whatever a raw file-level conversion would guess.

I can't see your project, so I don't know your Django version, whether you use a custom user model, how your settings are organized, or how much data is in the SQLite file. Where those change a step, I've flagged it inline.

## 1. Precheck, while still on SQLite

```
python -c "import django; print(django.get_version())"
python manage.py makemigrations --check --dry-run
python manage.py showmigrations
```

`makemigrations --check --dry-run` exits non-zero if your models have changed without a matching migration. Fix that before dumping, because the dump will contain fields that the freshly migrated Postgres schema does not have. `showmigrations` should show `[X]` on every line; an unapplied migration means your SQLite tables and your migration history already disagree.

Record the row counts you expect to end up with:

```
python manage.py shell -c "from django.apps import apps; print(sorted((m._meta.label, m.objects.count()) for m in apps.get_models()))"
```

Save that output somewhere. It is the comparison at the end.

## 2. Back up the SQLite file

Copy `db.sqlite3` to a path outside the repo. Nothing below writes to it, but it is the only copy of the data until step 3 succeeds.

## 3. Dump the data

```
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.Permission --exclude admin.logentry --exclude sessions.session --indent 2 -o dump.json
```

What the flags do:

- `--natural-foreign` and `--natural-primary` serialize references by *natural key*, meaning a stable identifier the model defines itself (for content types, the `app_label` plus `model` pair) rather than the auto-increment integer id. This matters because Postgres will assign different integer ids than SQLite did.
- `--exclude contenttypes --exclude auth.Permission` skips the two tables Django repopulates automatically during `migrate`. Without these, `loaddata` fails on duplicate keys. The natural keys from the previous flags let everything that points at those tables (groups, permissions on users) resolve against the newly created rows.
- `--exclude admin.logentry --exclude sessions.session` is optional. Both are churn in a dev database, and dropping them removes two sources of load errors.
- `-o dump.json` writes the file directly. Use it rather than shell redirection: on Windows PowerShell 5.1, `>` writes UTF-16LE and `loaddata` will later fail with a `UnicodeDecodeError`. `-o` requires Django 2.0 or newer; on older versions redirect, then confirm the file is UTF-8.

Open the file and confirm it is not `[]`. An empty dump usually means `manage.py` picked up a different settings module than you expected.

## 4. Install the Postgres driver

Django 4.2 and newer support psycopg 3:

```
pip install "psycopg[binary]"
```

On Django 4.1 or older, use `pip install psycopg2-binary` instead. Add whichever one you install to `requirements.txt`.

## 5. Create the role and database

```
psql -U postgres -c "CREATE ROLE myapp WITH LOGIN PASSWORD 'devpassword';"
psql -U postgres -c "CREATE DATABASE myapp_dev OWNER myapp;"
psql -U postgres -c "ALTER ROLE myapp CREATEDB;"
```

Making the role the database owner matters on Postgres 15 and later, which revoked `CREATE` on the `public` schema from `PUBLIC`; a non-owner role hits `permission denied for schema public` partway through `migrate`. `CREATEDB` is only needed so `manage.py test` can create its `test_myapp_dev` database.

## 6. Point settings at Postgres

```python
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

Use `127.0.0.1` rather than `localhost`; on Windows `localhost` can resolve to `::1` and hit a listener that is not configured for it. If you already use `dj-database-url` or a `.env` file, the equivalent is `DATABASE_URL=postgres://myapp:devpassword@127.0.0.1:5432/myapp_dev`. Keep the old SQLite block commented out or behind an env toggle so you can switch back while verifying.

Confirm the connection before going further:

```
python manage.py dbshell
```

That should drop you into a `psql` prompt against `myapp_dev`. Quit with `\q`.

## 7. Build the schema

```
python manage.py migrate
```

This runs against an empty database, so it should apply every migration in order. It also creates the content types and permissions that step 3 deliberately excluded.

## 8. Load the data

```
python manage.py loaddata dump.json
```

It prints `Installed N object(s) from 1 fixture(s)`. `loaddata` resets each loaded model's Postgres sequence when it finishes, so the next `INSERT` will not collide with an imported id.

## 9. Verify

Re-run the same count command from step 1 and diff it against the saved output:

```
python manage.py shell -c "from django.apps import apps; print(sorted((m._meta.label, m.objects.count()) for m in apps.get_models()))"
```

Expect `contenttypes.ContentType`, `auth.Permission`, and anything else you excluded to differ; every other model should match exactly. Then create one object through the admin or the shell to confirm the sequences advanced correctly, and log in with an existing account to confirm the password hashes came across.

## If a step fails

- `duplicate key value violates unique constraint "django_content_type_app_label_model_..."` or a `Could not load auth.Permission(pk=...)` traceback: the dump included the excluded tables. Redo step 3 with the `--exclude` flags, into a fresh file.
- `value too long for type character varying(N)`: SQLite does not enforce `max_length`, Postgres does. The error names the column; find the offending rows in the SQLite copy and either shorten them or widen the field with a migration.
- `null value in column "x" violates not-null constraint` or `invalid input syntax for type integer: ""`: same cause, a value SQLite tolerated that Postgres rejects. Fix the rows in the dump JSON or in the SQLite copy, then re-dump.
- `RuntimeWarning: DateTimeField ... received a naive datetime`: Postgres stores `timestamptz`, so naive values get interpreted in your `TIME_ZONE`. Harmless if `USE_TZ` was already `True` when the data was written; worth checking if it was not.
- `UnicodeDecodeError` during `loaddata`: the dump file is not UTF-8. Regenerate it with `-o`.
- `FATAL: password authentication failed` or `no pg_hba.conf entry for host`: authentication config, not Django. Adjust `pg_hba.conf` for your local connection and reload Postgres.

To retry cleanly at any point, `DROP DATABASE myapp_dev;`, recreate it, and resume from step 7. Your SQLite file and `dump.json` are untouched by all of this.

## One caveat on scale

`loaddata` holds the whole fixture in memory and inserts row by row, so it gets slow and memory-hungry somewhere in the high hundreds of thousands of rows. If your dump is large enough that this bites, dump and load one app at a time in dependency order, or move to `pgloader`, which copies SQLite to Postgres directly. `pgloader` does not know Django's conventions, so with it you would let `migrate` create the schema and load only table data, and check the column types afterward.

Once the counts match and a login works, delete `dump.json` (it contains password hashes and any other sensitive dev data in plaintext JSON) and remove the SQLite settings block.
