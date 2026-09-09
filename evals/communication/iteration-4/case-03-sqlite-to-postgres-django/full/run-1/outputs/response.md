1. Back up SQLite and dump the data, before touching any settings:

   ```bash
   cp db.sqlite3 db.sqlite3.bak
   python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.Permission --indent 2 -o dump.json
   ```

   Budget about 20 minutes for the whole switch on a dev database of a few hundred thousand rows, assuming step 6 turns up no bad data.

   Those flags are not optional. `migrate` recreates the rows in `django_content_type` and `auth_permission` itself on the new database, so reloading your old copies collides with rows Postgres already has. `--natural-foreign` writes anything that points at a content type (admin history entries, group permissions) as the text pair `["app_label", "model"]` instead of a numeric id, so those references still resolve after the ids are renumbered. Use `-o dump.json` rather than `> dump.json`: shell redirection can write the file in the console's own encoding, and Django then cannot read the fixture back (a fixture is just the JSON file `dumpdata` writes and `loaddata` reads).

   If `dump.json` comes out above roughly a gigabyte, stop here and tell me. `loaddata` parses the whole file into memory at once, and past that size a bulk copy tool such as pgloader is the better route.

2. Install the Postgres driver:

   ```bash
   pip install "psycopg[binary]"
   ```

   That is psycopg 3, which needs Django 4.2 or newer. Check with `python -m django --version`; on anything older, install `psycopg2-binary` instead. The `ENGINE` string in step 4 is the same either way.

3. Create the role and database:

   ```bash
   psql -U postgres -c "CREATE ROLE myapp WITH LOGIN PASSWORD 'devpassword';"
   psql -U postgres -c "CREATE DATABASE myapp_dev OWNER myapp;"
   psql -U postgres -c "ALTER ROLE myapp CREATEDB;"
   ```

   The third line is the one people skip. `manage.py test` builds a throwaway database called `test_myapp_dev`, and without `CREATEDB` your test suite starts failing with a permission error the first time you run it after the switch.

4. Point `settings.py` at Postgres and confirm the connection:

   ```python
   DATABASES = {
       "default": {
           "ENGINE": "django.db.backends.postgresql",
           "NAME": os.environ.get("PGDATABASE", "myapp_dev"),
           "USER": os.environ.get("PGUSER", "myapp"),
           "PASSWORD": os.environ["PGPASSWORD"],
           "HOST": os.environ.get("PGHOST", "127.0.0.1"),
           "PORT": os.environ.get("PGPORT", "5432"),
       }
   }
   ```

   Read the password from the environment rather than hardcoding it, so it does not reach git. Use `127.0.0.1` rather than `localhost`: `localhost` can resolve to the IPv6 address `::1` while Postgres is listening only on IPv4, which shows up as a connection refused error that looks like the server is down.

   Then run `python manage.py dbshell`. A `myapp_dev=>` prompt means the credentials work; `\q` exits. Fix any failure here before going on, because a broken connection makes step 5 fail in a way that looks like a migration problem.

5. Build the schema on the empty database:

   ```bash
   python manage.py migrate
   ```

   Expect a run of `Applying <app>.<migration>... OK` lines. Do not run `loaddata` before this; the tables do not exist yet.

6. Load the data:

   ```bash
   python manage.py loaddata dump.json
   ```

   Success looks like `Installed 12345 object(s) from 1 fixture(s)`. Three failures are common, and all three are SQLite being permissive where Postgres is not:

   - `duplicate key value violates unique constraint "django_content_type_..."` means content types got into the dump. Re-run step 1 with both `--exclude` flags present.
   - `value too long for type character varying(50)` means a row exceeds a `max_length` that SQLite never enforced. Either trim the offending rows in the backup and re-dump, or widen the field with a new migration.
   - `invalid input syntax for type integer` or a similar `DataError` means a column holds a value of the wrong type. SQLite lets a string sit in an integer column; Postgres rejects it on insert. Find it with the model and column named in the traceback.

   `loaddata` resets each table's sequence (the counter Postgres uses to hand out the next id) for every model in the fixture, so new inserts will not collide with loaded ids. If you ever load data by some other route, reset them by hand with `python manage.py sqlsequencereset yourapp | python manage.py dbshell`.

What I could not check, since I do not have your project:

- `db.sqlite3` and `settings.py` are Django's defaults, and `myapp` / `myapp_dev` are placeholders. Substitute your real names.
- If your settings already build `DATABASES` from a `DATABASE_URL` through `dj-database-url` or `django-environ`, change the URL to `postgres://myapp:devpassword@127.0.0.1:5432/myapp_dev` and leave the dict in step 4 alone.
- Your Django version, which decides psycopg 3 versus psycopg2 in step 2.
- Third-party or custom model fields. Plain Django fields round-trip through `dumpdata` cleanly; PostGIS geometry, encrypted fields, and hand-written `Field` subclasses with custom `to_python` are the ones that can need extra work, and I cannot tell whether you have any.

Verify: run `python manage.py runserver`, open `http://127.0.0.1:8000/admin/`, and confirm your existing objects are listed there. `db.sqlite3.bak` stays untouched until you are satisfied.
