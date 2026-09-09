Postgres speaks SSL only over TCP, never over the Unix domain socket. That one fact causes most of the confusion here: if Django's `HOST` is blank, it connects over the socket at `/tmp/.s.PGSQL.5432` and no TLS happens regardless of what `sslmode` you set. So `HOST` must be `127.0.0.1` or `localhost`.

The whole path is: install Postgres, generate a self-signed certificate inside its data directory, turn `ssl` on, tell `pg_hba.conf` to accept only encrypted TCP connections, then point Django at `127.0.0.1` with `sslmode=require`. About 15 minutes.

## 1. Install and start Postgres

```bash
brew install postgresql@17
brew services start postgresql@17
```

Never use `sudo` with `brew services`. It runs the server as your own macOS user, and that is what makes the file ownership in the later steps work.

Versioned Homebrew formulas are "keg-only", meaning `psql` is not on your `PATH` yet:

```bash
echo 'export PATH="$(brew --prefix postgresql@17)/bin:$PATH"' >> ~/.zshrc
exec zsh
psql --version
```

Substitute your actual major version for `17` everywhere below. `brew search postgresql@` lists what is available.

## 2. Find the data directory

Everything you edit lives in one directory. Ask the server rather than guessing:

```bash
export PGDATA="$(psql -tAX postgres -c 'SHOW data_directory')"
echo "$PGDATA"
```

Expect `/opt/homebrew/var/postgresql@17` on Apple Silicon or `/usr/local/var/postgresql@17` on Intel.

## 3. Generate a self-signed certificate

```bash
cd "$PGDATA"
openssl req -new -x509 -nodes -days 3650 \
  -keyout server.key -out server.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 server.key
```

Two things matter. The key must be mode `600` and owned by the user running the server, or Postgres refuses to start. The `subjectAltName` only matters if you later want `verify-full` (step 9); for `sslmode=require` it is ignored.

If you get `unknown option -addext`, your `/usr/bin/openssl` is Apple's LibreSSL. Install real OpenSSL and use its binary explicitly:

```bash
brew install openssl@3
"$(brew --prefix openssl@3)/bin/openssl" req -new -x509 -nodes -days 3650 \
  -keyout server.key -out server.crt -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

## 4. Turn SSL on

```bash
grep -nE '^#?ssl' "$PGDATA/postgresql.conf" | head -20
```

Find the `#ssl = off` line and change it to:

```
ssl = on
```

Nothing else is needed. `ssl_cert_file` and `ssl_key_file` already default to `server.crt` and `server.key` relative to the data directory, which is exactly where you put them.

## 5. Require SSL in pg_hba.conf

`pg_hba.conf` is the file that decides who may connect and how. Back it up, then look at it:

```bash
cp "$PGDATA/pg_hba.conf" "$PGDATA/pg_hba.conf.bak"
grep -vE '^[[:space:]]*(#|$)' "$PGDATA/pg_hba.conf"
```

You will see something close to this:

```
local   all   all                 trust
host    all   all   127.0.0.1/32  trust
host    all   all   ::1/128       trust
```

Change the two `host` lines to `hostssl`, and `trust` to `scram-sha-256`:

```
local     all   all                 trust
hostssl   all   all   127.0.0.1/32  scram-sha-256
hostssl   all   all   ::1/128       scram-sha-256
```

`hostssl` matches only TLS connections, so a plaintext TCP connection is now refused by the server. Leaving the `local ... trust` line alone keeps `psql postgres` working passwordless over the socket for admin work. Leave the `replication` lines as they are.

This step is the one that actually enforces anything. `sslmode` on the client side is only a request; `hostssl` is the rule.

## 6. Restart and create your database

```bash
brew services restart postgresql@17
psql postgres -c "CREATE ROLE myapp LOGIN PASSWORD 'dev-only-password';"
psql postgres -c "ALTER ROLE myapp CREATEDB;"
psql postgres -c "CREATE DATABASE myapp_dev OWNER myapp;"
```

`CREATEDB` is not optional if you plan to run `manage.py test`, because Django creates and drops a `test_myapp_dev` database on each run.

Changes to `pg_hba.conf` alone need only a reload (`psql postgres -c "SELECT pg_reload_conf();"`), but a restart after the `ssl = on` change is the unambiguous move.

## 7. Prove SSL is actually on

Do not skip this. Connect, then ask the server about your own connection:

```bash
psql "host=127.0.0.1 port=5432 dbname=myapp_dev user=myapp sslmode=require"
```

Then at the prompt:

```sql
SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();
```

You want `t | TLSv1.3 | TLS_AES_256_GCM_SHA384` or similar. `ssl = f` means the connection is plaintext and something above did not take.

Now the negative test, which is the more informative one:

```bash
psql "host=127.0.0.1 dbname=myapp_dev user=myapp sslmode=disable"
```

This should fail with `no pg_hba.conf entry for host "127.0.0.1", user "myapp", database "myapp_dev", no encryption`. If it succeeds instead, your `hostssl` edit is not live and unencrypted connections are still being accepted.

## 8. Point Django at it

Install a driver. On Django 4.2 and newer, psycopg 3 is the better choice:

```bash
pip install "psycopg[binary]"
```

On older Django, use `pip install psycopg2-binary`. The `[binary]` and `-binary` variants matter on macOS because they ship a prebuilt wheel and skip a source build against libpq.

In `settings.py`:

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp_dev",
        "USER": "myapp",
        "PASSWORD": os.environ["MYAPP_DB_PASSWORD"],
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "OPTIONS": {"sslmode": "require"},
    }
}
```

Anything in `OPTIONS` is passed straight through to libpq, which is why `sslmode` goes there rather than at the top level. Keep the password in an environment variable or a `.env` file rather than in the settings file, even for a dev password, so the habit is already in place when a real one shows up.

Then run migrations and confirm Django itself is on TLS, not just psql:

```bash
python manage.py migrate
python manage.py shell <<'PY'
from django.db import connection
with connection.cursor() as cur:
    cur.execute("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
    print(cur.fetchone())
PY
```

`(True, 'TLSv1.3')` means you are done.

## 9. Optional: verify-full

`sslmode=require` encrypts the connection but does not check who the server is, so it stops passive sniffing but not an active man in the middle. Over loopback that distinction is academic. It stops being academic if you want your dev config to rehearse production, since managed Postgres (RDS, Cloud SQL) is usually configured for `verify-full`.

To do that locally, trust your own certificate:

```bash
mkdir -p ~/.postgresql
cp "$PGDATA/server.crt" ~/.postgresql/root.crt
```

Then in Django:

```python
"HOST": "localhost",
"OPTIONS": {"sslmode": "verify-full"},
```

`~/.postgresql/root.crt` is libpq's default trust store location, so no `sslrootcert` entry is needed. This works because `openssl req -x509` marks the certificate as a CA, so it validates as its own root. Use `localhost` rather than `127.0.0.1` here, since it matches the `DNS:localhost` name in the certificate directly. Note that `localhost` is still a TCP connection, not the socket; libpq uses the socket only when the host is empty or begins with `/`.

## What I could not verify

I do not have access to your machine, so every path, version number, and file excerpt above is a template rather than an observation. Specifically:

- **Your Homebrew prefix.** `/opt/homebrew` on Apple Silicon, `/usr/local` on Intel. `brew --prefix` settles it.
- **Your Postgres major version.** I wrote `17` throughout; check `brew search postgresql@` and substitute.
- **Whether port 5432 is already taken** by Postgres.app, a Docker container, or an older formula. Check `lsof -nP -iTCP:5432 -sTCP:LISTEN` before debugging anything else. Two Postgres installations fighting over one port produce symptoms that look exactly like a broken SSL config.
- **Whether your `openssl` accepts `-addext`.** Run `openssl version`; LibreSSL is the case that needs the fallback in step 3.
- **The exact contents of your `pg_hba.conf`.** Defaults vary between formula versions. Read yours and edit it rather than pasting mine over it.
- **Your Django and driver versions.** The settings block assumes Django 4.2 or newer.

## If something breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| `server does not support SSL, but SSL was required` | `ssl = on` did not take, or you edited a different config file | `psql postgres -c "SHOW ssl;"` and `SHOW config_file;` to see what is actually live |
| `no pg_hba.conf entry ... no encryption` from Django | Django connected in plaintext | Confirm `HOST` is not blank and `sslmode` is inside `OPTIONS` |
| `private key file "server.key" has group or world access` | Key permissions | `chmod 600 "$PGDATA/server.key"` |
| Server will not start after your edits | Bad config line | `tail -50 "$(brew --prefix)/var/log/postgresql@17.log"`, then restore `pg_hba.conf.bak` |
| `password authentication failed for user "myapp"` | Role has no password, or `trust` was switched off before one was set | `psql postgres -c "ALTER ROLE myapp PASSWORD '...';"` over the local socket |
| `Connection refused` on 5432 | Service down, or another Postgres owns the port | `brew services list`, then `lsof -nP -iTCP:5432 -sTCP:LISTEN` |
| `certificate verify failed` | Only with `verify-ca` or `verify-full`: missing `root.crt`, or host not in the SAN | Redo step 9, or drop back to `require` |
| psycopg2 fails to compile during `pip install` | Source build cannot find libpq or OpenSSL | Use `psycopg[binary]`, or first export `PATH="$(brew --prefix postgresql@17)/bin:$PATH"`, `LDFLAGS="-L$(brew --prefix openssl@3)/lib"`, `CPPFLAGS="-I$(brew --prefix openssl@3)/include"` |

The log file in row four is worth knowing about up front. When Postgres refuses to start after a config edit, `brew services` reports the failure without the reason, and the reason is always in that log.
