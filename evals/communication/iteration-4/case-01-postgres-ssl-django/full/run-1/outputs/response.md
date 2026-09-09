Open a terminal and run these four lines:

```bash
brew install postgresql@17
export PG=postgresql@17
export PGDIR="$(brew --prefix)/var/$PG"
export PATH="$(brew --prefix "$PG")/bin:$PATH"
```

Budget about 25 minutes if nothing else is already listening on port 5432, closer to 45 if you hit the certificate or `pg_hba.conf` snags noted below. The three `export` lines only live in this terminal window; if you open a new one, run them again before continuing.

If `postgresql@17` is not found, run `brew search postgresql@`, take the highest version listed, and change the `PG=` line to match. The rest of the steps are version-independent because they all read from `$PG`.

### A. Get the server running

1. Start it and confirm it answers:

```bash
brew services start "$PG"
pg_isready -h localhost
```

Expected: `localhost:5432 - accepting connections`. If you get `no response`, wait five seconds and run `pg_isready` again; the first start does more work than later ones.

2. Confirm where the config files actually live:

```bash
psql -d postgres -c "SHOW data_directory;"
echo "$PGDIR"
```

Those two must print the same path. That directory is the *data directory*: Postgres keeps the database files, `postgresql.conf`, and `pg_hba.conf` there. If they differ, re-run `export PGDIR=` with whatever `psql` printed, because every later step writes into it.

3. Make the tools available in future terminals by adding one line to `~/.zshrc`:

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
```

Use `/usr/local` instead of `/opt/homebrew` on an Intel Mac. `brew --prefix postgresql@17` prints the correct one for your machine.

### B. Make the certificate and turn SSL on

4. Generate a self-signed certificate inside the data directory:

```bash
cd "$PGDIR"
openssl req -x509 -newkey rsa:2048 -days 3650 -nodes \
  -keyout server.key -out server.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost"
```

*Self-signed* means you act as your own certificate authority: the certificate vouches for itself. That is normal for a local database and unacceptable for anything reachable from the internet. `-nodes` leaves the private key unencrypted, which is required here, since a passphrase-protected key makes Postgres prompt at startup and there is nobody to answer the prompt when it starts as a background service. `CN=localhost` has to match the hostname Django will connect to, which is why `localhost` appears again in step 13. `-days 3650` is deliberate; a one-year certificate expires mid-project and produces a confusing failure.

macOS ships LibreSSL at `/usr/bin/openssl`, which may reject `-addext`. If it does, run `brew install openssl@3` and repeat the command with `"$(brew --prefix openssl@3)/bin/openssl"` in place of `openssl`.

5. Lock down the private key:

```bash
chmod 600 "$PGDIR/server.key"
```

Postgres refuses to start if anyone but the owning user can read the key. This is the single most common reason the next restart fails.

6. Turn SSL on:

```bash
echo "ssl = on" >> "$PGDIR/postgresql.conf"
```

Appending is safe because the last setting in the file wins. You do not need to set `ssl_cert_file` or `ssl_key_file`; they already default to `server.crt` and `server.key` in this directory.

7. Require encryption for network connections. Open the access-rules file:

```bash
open -e "$PGDIR/pg_hba.conf"
```

Near the bottom you will see something close to this:

```
local   all   all                  trust
host    all   all   127.0.0.1/32   trust
host    all   all   ::1/128        trust
```

Change the two `host` lines to:

```
hostssl all   all   127.0.0.1/32   scram-sha-256
hostssl all   all   ::1/128        scram-sha-256
```

Leave the `local` line exactly as it is. `local` covers connections through the Unix socket file, which cannot be encrypted at all, and keeping it on `trust` is what lets you keep running admin commands without a password. `host` matches encrypted and unencrypted TCP connections alike; `hostssl` matches only encrypted ones, so switching the keyword is what makes plaintext impossible. `scram-sha-256` replaces `trust` so a password is actually required. Postgres reads this file top to bottom and stops at the first line that matches, so do not leave a plain `host` line for `127.0.0.1` sitting above your new ones.

8. Restart and check it came back:

```bash
brew services restart "$PG"
pg_isready -h localhost
```

If it does not come back, read the log: `tail -n 30 "$(brew --prefix)/var/log/$PG.log"`. `private key file "server.key" has group or world access` means step 5 did not take. `could not access private key file` means the certificate landed somewhere other than `$PGDIR`.

### C. Create the database and prove encryption is on

9. Create the role and the database:

```bash
psql -d postgres -c "CREATE ROLE django_user WITH LOGIN PASSWORD 'pick-a-real-password';"
createdb -O django_user myproject
```

`-O` makes the role the database owner, which also gives it rights on the `public` schema. Postgres 15 and later stopped granting that automatically, and missing it is the usual cause of `permission denied for schema public` during `migrate`.

10. Confirm the connection is encrypted:

```bash
psql "host=localhost dbname=myproject user=django_user sslmode=require" \
  -c "SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

It will prompt for the password from step 9. Expected: `ssl` is `t` and `version` shows a TLS version.

11. Confirm unencrypted is refused:

```bash
psql "host=localhost dbname=myproject user=django_user sslmode=disable" -c "SELECT 1;"
```

This one is supposed to fail, with `no pg_hba.conf entry for host "127.0.0.1", user "django_user", database "myproject", no encryption`. If it succeeds instead, a plain `host` line is still matching first in `pg_hba.conf`; go back to step 7.

### D. Point Django at it

12. Install the driver:

```bash
python -m django --version
pip install "psycopg[binary]"     # Django 4.2 or newer
pip install psycopg2-binary       # Django 4.1 or older
```

Run only the line matching your version. `ENGINE` below is the same either way.

13. In `settings.py`:

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myproject",
        "USER": "django_user",
        "PASSWORD": os.environ["DJANGO_DB_PASSWORD"],
        "HOST": "localhost",
        "PORT": "5432",
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": "/opt/homebrew/var/postgresql@17/server.crt",
        },
    }
}
```

Paste the real path from `echo "$PGDIR/server.crt"` into `sslrootcert`, and set the password in your shell with `export DJANGO_DB_PASSWORD='pick-a-real-password'` before running `manage.py`. Keep it out of the repository.

`HOST` must be filled in. If you leave it empty, Django connects over the Unix socket, and the connection is unencrypted no matter what `sslmode` says, because sockets have no TLS.

The two modes worth knowing apart: `require` encrypts the traffic but never checks who is on the other end, so it does not protect you from something impersonating your database. `verify-full` checks the server's certificate against `sslrootcert` and checks that the hostname matches the name in the certificate, which is why the certificate says `localhost` and `HOST` says `localhost`. A self-signed certificate can serve as its own root, which is what `sslrootcert` pointing at `server.crt` is doing. If `verify-full` fails with a certificate or hostname error, switch to `"sslmode": "require"` to confirm everything else works, then come back and fix the name mismatch.

14. Run the migrations:

```bash
python manage.py migrate
```

Once step 11 fails the way it should, any connection Django makes over `localhost` is encrypted by definition, because the unencrypted alternative is refused at the server. A successful `migrate` is therefore also your proof that Django is on TLS.

### What I could not check from here

I do not have access to your machine, so five things are assumptions rather than observations:

1. That `postgresql@17` is a current Homebrew formula for you. `brew search postgresql@` settles it.
2. That port 5432 is free. Postgres.app and Docker both claim it. `lsof -nP -iTCP:5432 -sTCP:LISTEN` shows what holds it.
3. That your `/usr/bin/openssl` accepts `-addext`. It is LibreSSL, not OpenSSL, and the fallback in step 4 covers it if it refuses.
4. Your Django version and whether you already have a driver installed, which decides between the two `pip` lines in step 12.
5. That this is a fresh install. If a Homebrew Postgres data directory already exists, `brew install` will not re-initialize it, and your `pg_hba.conf` may not look like the block in step 7.

Step 10 printing `t` for `ssl` is the proof the server side is done, and step 11 failing is the proof nothing can route around it.
