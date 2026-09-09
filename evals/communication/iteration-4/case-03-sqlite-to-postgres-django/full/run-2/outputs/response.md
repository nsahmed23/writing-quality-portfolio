Dump the data first, while `settings.py` still points at SQLite:

```bash
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.Permission --exclude admin.LogEntry --exclude sessions.Session --indent 2 > dump.json
```

Those excludes are not optional. `migrate` recreates the content type and permission rows on the new database by itself, so loading dumped copies on top raises `IntegrityError: duplicate key value violates unique constraint "django_content_type_app_label_model_..."`. The `--natural-foreign` flag makes any foreign key pointing at those tables serialize as a readable key (`["auth", "user"]` instead of the integer `4`), which is what makes dropping the rows themselves safe.

One caveat on `--natural-primary`: it omits the primary key for models that define a natural key, and `auth.User` is one, so your users get fresh IDs in Postgres. Foreign keys follow automatically. Raw integer IDs stored outside a foreign key do not, so a `GenericForeignKey`'s `object_id` column, an ID saved into a `JSONField`, or an ID held by an external system will point at the wrong row afterwards. If you have any of those, drop `--natural-primary`, keep `--natural-foreign`, and re-dump.

Budget about 20 minutes for a dev database of a few thousand rows. Add time if the load step rejects rows, which is where the surprises land.

### Prepare (steps 1 to 4)

1. Run the dump above, then snapshot row counts so you have something to compare against later:
   ```bash
   python manage.py shell -c "from django.apps import apps; [print(m._meta.label, m.objects.count()) for m in sorted(apps.get_models(), key=lambda m: m._meta.label)]" > counts-sqlite.txt
   ```
   Leave `db.sqlite3` exactly where it is. It is your rollback until the new database is verified.
2. Install the driver: `pip install "psycopg[binary]"` on Django 4.2 or newer, `pip install psycopg2-binary` on 4.1 or older. Run `python -c "import django; print(django.get_version())"` if you are not sure which you are on.
3. Create the role and database, in `psql` as a superuser:
   ```sql
   CREATE USER myuser WITH PASSWORD 'change-me';
   CREATE DATABASE myproject OWNER myuser;
   ```
   Make `myuser` the owner rather than granting privileges afterwards. Postgres 15 removed everyone's default permission to create tables in the `public` schema, and a merely-granted user hits `permission denied for schema public` at step 5; the database owner does not.
4. Point Django at it:
   ```python
   DATABASES = {
       "default": {
           "ENGINE": "django.db.backends.postgresql",
           "NAME": "myproject",
           "USER": "myuser",
           "PASSWORD": os.environ["PGPASSWORD"],
           "HOST": "127.0.0.1",
           "PORT": "5432",
       }
   }
   ```
   Read the password from the environment rather than committing it. `django.db.backends.postgresql` is the correct `ENGINE` for both drivers; Django uses psycopg 3 when it is installed and falls back to psycopg2. Confirm the connection before going further with `python manage.py dbshell`, which should land you at a `myproject=>` prompt (`\q` exits).

### Load and verify (steps 5 to 7)

5. Build the schema: `python manage.py migrate`. This creates the empty tables plus the content type and permission rows you excluded from the dump.
6. Load the data: `python manage.py loaddata dump.json`. It runs inside a single transaction, so a failure rolls the whole thing back and leaves you an empty database to retry against, not a half-loaded one.
7. Snapshot the counts again and compare. Run the same `shell -c` command from step 1, redirected to `counts-postgres.txt`, then:
   ```bash
   diff counts-sqlite.txt counts-postgres.txt
   ```
   The only lines that should differ are `sessions.Session` and `admin.LogEntry`, which you deliberately left behind, plus `contenttypes.ContentType` if your SQLite file still holds rows for apps you have since removed.

### If step 6 fails

1. `value too long for type character varying(200)`: SQLite does not enforce `max_length` on a `CharField` and Postgres does, so an overlong string has been sitting in the file unnoticed. Find it against SQLite with `from django.db.models.functions import Length` and `SomeModel.objects.annotate(n=Length("field")).filter(n__gt=200)`, trim the rows, re-dump.
2. `duplicate key value violates unique constraint "myapp_thing_pkey"` when you create your first new record after loading: the Postgres sequence is behind the IDs that were inserted explicitly. `loaddata` normally resets sequences itself, so if you see this anyway, run `python manage.py sqlsequencereset myapp | python manage.py dbshell`, once per app label.
3. An `IntegrityError` naming a model whose rows one of your migrations creates (default categories, a `Site` record, any seed data): `migrate` inserted them at step 5 and the fixture is inserting them again. Re-dump with `--exclude myapp.ThatModel` added, then `python manage.py flush --no-input` before retrying step 6. Only run `flush` while settings point at the new Postgres database; it empties every table in whichever database is configured.

### What I could not check

I do not have your project, so four things here are assumptions rather than verified facts: your Django version, which decides psycopg versus psycopg2 at step 2; your settings layout, since a settings package or `dj-database-url` changes where the step 4 block goes; whether you use a custom `AUTH_USER_MODEL`, which interacts with the natural-key caveat above; and whether any of your migrations seed rows that the fixture also contains. None of those change the shape of the sequence, only which line you edit and which excludes you need. I also have not run any of these commands against your data.

You are done when `diff counts-sqlite.txt counts-postgres.txt` prints nothing but the `sessions.Session` and `admin.LogEntry` lines.
