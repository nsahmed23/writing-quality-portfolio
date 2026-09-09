Homebrew installs Postgres with SSL compiled in but turned off, so the job is four edits plus a certificate: generate a self-signed cert, point `postgresql.conf` at it, force SSL for TCP connections in `pg_hba.conf`, then tell Django to require it. Budget about 20 minutes. Steps 1 through 6 get you a working encrypted connection; step 7 is optional hardening.

## 1. Install and start Postgres

```bash
brew search postgresql@      # shows which versions are available
brew install postgresql@17
```

Versioned Homebrew formulas are "keg-only", meaning the binaries are deliberately kept off your PATH so they don't collide with other versions. Add them yourself:

```bash
echo 'export PATH="$(brew --prefix)/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
which psql        # should print a path under .../opt/postgresql@17/bin
```

`brew --prefix` is `/opt/homebrew` on Apple Silicon and `/usr/local` on Intel; using the command instead of a literal path keeps this correct either way. If `which psql` prints `/usr/bin/psql` or nothing, the PATH line didn't take and every later command will talk to the wrong install.

Start the server:

```bash
brew services start postgresql@17
psql postgres -c "SELECT version();"
```

Homebrew's `initdb` makes your macOS username the superuser, so `psql postgres` connects with no password. There is no `postgres` role unless you create one; `postgres` here is the name of the default database, not a user.

## 2. Find the data directory

```bash
export PGDATA="$(psql postgres -tAc 'SHOW data_directory;')"
echo "$PGDATA"    # typically /opt/homebrew/var/postgresql@17
```

Do this rather than guessing. Editing a `postgresql.conf` that belongs to a different Postgres install is the single most common way this task fails, and it fails silently: your edits are real, they just aren't the file the running server reads.

## 3. Generate a self-signed certificate

```bash
cd "$PGDATA"
openssl req -new -x509 -nodes -days 3650 \
  -out server.crt -keyout server.key \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 server.key
```

`-nodes` means the private key gets no passphrase, which is what lets the server boot unattended. `chmod 600` is not optional: Postgres refuses to start if the key is readable by group or others, and the file must be owned by the account running the server (that's your own user under Homebrew, so creating it here already satisfies that).

Two caveats. macOS ships LibreSSL as `/usr/bin/openssl`, and older LibreSSL builds reject `-addext` with an "unknown option" error. If that happens, run `brew install openssl@3` and use `$(brew --prefix openssl@3)/bin/openssl` for that one command. The `subjectAltName` only matters if you go on to step 7; current TLS clients ignore `CN` for hostname checking, so a cert without a SAN works for `require` but can never satisfy `verify-full`.

Self-signed is the right choice here. It encrypts the connection but proves nothing about who is on the other end, which is fine when both ends are your own laptop. It is not fine for a real server.

## 4. Turn SSL on

```bash
cat >> "$PGDATA/postgresql.conf" <<'EOF'

ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
EOF
```

Relative paths resolve against the data directory, so those filenames work as written.

## 5. Require SSL for TCP connections

Open `$PGDATA/pg_hba.conf`. The loopback lines currently read `host ... trust`. Change them to `hostssl ... scram-sha-256`:

```
# TYPE     DATABASE  USER  ADDRESS       METHOD
local      all       all                 trust
hostssl    all       all   127.0.0.1/32  scram-sha-256
hostssl    all       all   ::1/128       scram-sha-256
```

`hostssl` rejects any non-SSL TCP connection outright, which is what turns "SSL is available" into "SSL is mandatory". Leave the `local` line alone: it covers the Unix-domain socket, which never uses TLS, and keeping it on `trust` is what lets your own `psql postgres` shortcuts keep working. That same socket is a trap on the Django side, covered in step 6.

Restart and confirm before going anywhere near Django:

```bash
brew services restart postgresql@17
psql "host=localhost dbname=postgres sslmode=require" \
  -c "SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

You want `ssl` to come back as `t` and a version of `TLSv1.3` or `TLSv1.2`. Inside an interactive `psql` session, `\conninfo` prints the same thing in one line.

Now create the app database and a role with an actual password, since `trust` no longer applies over TCP:

```bash
psql postgres <<'EOF'
CREATE ROLE myapp WITH LOGIN PASSWORD 'change-me-locally';
CREATE DATABASE myapp OWNER myapp;
EOF
```

## 6. Configure Django

```bash
pip install "psycopg[binary]"
```

psycopg 3 requires Django 4.2 or newer. On anything older, install `psycopg2-binary` instead; the settings below are identical either way.

In `settings.py`:

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "USER": "myapp",
        "PASSWORD": os.environ["MYAPP_DB_PASSWORD"],
        "HOST": "localhost",   # must be set: blank means Unix socket, which has no SSL
        "PORT": "5432",
        "OPTIONS": {"sslmode": "require"},
    }
}
```

That `HOST` comment is the trap from step 5. Leave `HOST` empty and Django connects over the Unix socket, `hostssl` never comes into play, `sslmode` is ignored, and you get an unencrypted connection that looks like a clean success. Keeping the password in an environment variable rather than in `settings.py` also keeps it out of version control.

Verify from inside Django, not just from `psql`:

```bash
python manage.py shell <<'EOF'
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
    print(c.fetchone())
EOF
```

`(True, 'TLSv1.3')` means you are done.

## 7. Optional: upgrade from `require` to `verify-full`

The `sslmode` values differ in ways worth knowing, because the default is weaker than most people assume:

| sslmode | encrypts | checks certificate | checks hostname |
|---|---|---|---|
| `disable` | no | no | no |
| `prefer` (libpq default) | only if offered, silently falls back | no | no |
| `require` | yes | no | no |
| `verify-ca` | yes | yes | no |
| `verify-full` | yes | yes | yes |

`prefer` is the default when you set no `sslmode` at all, and its silent fallback to plaintext is exactly why step 5 forces the issue at the server. `require` encrypts but accepts any certificate, so it stops passive eavesdropping and not an active man-in-the-middle. On loopback that distinction is close to academic, but matching production settings locally is how you catch cert problems before deploying.

For `verify-full` against your self-signed cert, the cert acts as its own trust root:

```bash
mkdir -p ~/.postgresql
cp "$PGDATA/server.crt" ~/.postgresql/root.crt
```

Then set `"sslmode": "verify-full"` in `OPTIONS`. `~/.postgresql/root.crt` is libpq's default trust store location, so no other setting is needed; if you'd rather not touch your home directory, add `"sslrootcert": "/opt/homebrew/var/postgresql@17/server.crt"` alongside `sslmode` instead. The hostname check passes because of the `subjectAltName` from step 3 and because you connect to `localhost`.

## Failure modes and what they mean

- `FATAL: private key file "server.key" has group or world access`: the `chmod 600` in step 3 was skipped, or the file is owned by a different account than the one running the server.
- `server does not support SSL, but SSL was required`: `ssl = on` did not reach the running server. Run `psql postgres -c "SHOW config_file;"` and confirm that is the file you edited, then restart.
- `no pg_hba.conf entry for host "127.0.0.1", user "myapp", database "myapp", SSL off`: the client attempted plaintext. Check that `sslmode` is set and that Django's `HOST` is not blank.
- `password authentication failed for user "myapp"`: the role has no password, or you set one before switching to `scram-sha-256`. Re-run `ALTER ROLE myapp PASSWORD 'change-me-locally';`, since the hash is computed at the moment the password is set.
- Config edits appear to do nothing: something else already owns port 5432 (Postgres.app, a Docker container, an older brew formula). Run `lsof -nP -i :5432` to see which process it is. This is the second most common cause after editing the wrong config file.
- `brew services start` reports success but nothing is listening: read the log at `$(brew --prefix)/var/log/postgresql@17.log`, which records startup refusals including the key-permissions one above.

## What I could not verify

I have no access to your machine, so these are assumptions rather than checks: your Homebrew prefix, which `postgresql@` versions the formula index currently offers, the actual data directory path, whether another Postgres already holds port 5432, and your Django and Python versions. Every command above prints what it finds, so substitute real values wherever yours differ. The version number `17` appears in the PATH line, the `brew services` commands, and the log path; if you install a different major version, change it in all of them.
