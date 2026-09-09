Here is the whole path, from a fresh Homebrew install to Django connecting over verified TLS. Budget about 20 minutes. I have not run any of this on your machine, so a few values (Postgres version, data directory, Intel vs Apple Silicon paths) are things you print rather than things I can tell you; every step below shows you the command that prints them.

**One decision up front.** You can either make a single self-signed certificate, or make a tiny local certificate authority (CA) and use it to sign a server certificate. Do the second. It costs one extra command and it lets you use `sslmode=verify-full`, which is what you want in production.

The difference matters:

| `sslmode` | Encrypts | Checks the cert is trusted | Checks the hostname |
|---|---|---|---|
| `disable` | no | no | no |
| `require` | yes | **no** | no |
| `verify-ca` | yes | yes | no |
| `verify-full` | yes | yes | yes |

`require` sounds strict but accepts literally any certificate the server hands over, so it does not stop a man in the middle. `verify-full` is the real thing. Rehearsing it locally means the day you point Django at a managed database you are only changing a hostname and a CA file, not discovering a broken code path.

---

## 0. Make sure nothing already owns port 5432

If you ever installed Postgres.app, or have a Postgres container running, you will spend an hour editing config files for a server you are not actually talking to. Check first:

```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
```

No output means the port is free. If something is there, stop it (quit Postgres.app, or `docker stop <container>`) before continuing.

## 1. Install and start Postgres

Homebrew ships several versions side by side. See what exists, then pick the newest:

```bash
brew search 'postgresql@'
brew install postgresql@17     # substitute the version you picked
brew services start postgresql@17
```

The formula does not put `psql` on your PATH automatically. Add it to `~/.zshrc`:

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
```

That path is for Apple Silicon. On an Intel Mac the prefix is `/usr/local` instead of `/opt/homebrew`. Run `brew --prefix` if you are not sure which you have. Then open a new terminal and confirm:

```bash
psql --version
```

Homebrew creates a superuser role named after your macOS account and a database of the same name, so `psql` with no arguments should now drop you into a prompt. Type `\q` to leave.

## 2. Find out where your server keeps its files

Do not guess these paths, print them:

```bash
psql -d postgres -tAc 'SHOW data_directory'   # where certs go
psql -d postgres -tAc 'SHOW config_file'      # postgresql.conf
psql -d postgres -tAc 'SHOW hba_file'         # pg_hba.conf
```

Keep that first value handy:

```bash
DATADIR=$(psql -d postgres -tAc 'SHOW data_directory')
echo "$DATADIR"
```

## 3. Create a local CA and a server certificate

Use Homebrew's OpenSSL, not the `openssl` that ships with macOS. Apple's is actually LibreSSL wearing the same name, and some flags behave differently:

```bash
brew install openssl@3
OPENSSL="$(brew --prefix)/opt/openssl@3/bin/openssl"
```

Now generate everything in a directory outside your project:

```bash
mkdir -p ~/pgcerts && cd ~/pgcerts

# 1. The CA: one key, one long-lived self-signed cert.
$OPENSSL req -new -x509 -nodes -days 3650 -newkey rsa:4096 \
  -keyout ca.key -out ca.crt \
  -subj "/CN=Local Dev CA"

# 2. The server's key and a request to have it signed.
$OPENSSL req -new -nodes -newkey rsa:2048 \
  -keyout server.key -out server.csr \
  -subj "/CN=localhost"

# 3. The names this cert is valid for. verify-full checks these.
cat > server.ext <<'EOF'
subjectAltName = DNS:localhost, IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF

# 4. Sign it with the CA.
$OPENSSL x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 825 -sha256 -extfile server.ext
```

The `subjectAltName` line is the part people forget. `verify-full` compares the hostname you connected to against those names, and a certificate with only a common name and no SAN is rejected by modern clients.

Install the server pair into the data directory:

```bash
cp server.crt server.key "$DATADIR/"
chmod 600 "$DATADIR/server.key"
```

Postgres refuses to start if the private key is readable by anyone other than its owner. Under Homebrew the server runs as your own macOS user, so ownership is already correct; on Linux you would also need a `chown postgres`.

## 4. Turn SSL on

Open the file that `SHOW config_file` printed and set:

```
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

Relative filenames resolve against the data directory, so those two lines need no absolute paths. Restart:

```bash
brew services restart postgresql@17
```

If it does not come back up, the reason is in the log. Homebrew writes it to `$(brew --prefix)/var/log/postgresql@17.log`; `brew services info postgresql@17` will confirm the location. A bad key permission or a typo'd filename shows up there as a plain English line.

## 5. Refuse unencrypted TCP connections

SSL being available is not the same as SSL being required. In `pg_hba.conf` (the path `SHOW hba_file` printed), find the TCP lines, which look roughly like this:

```
host    all    all    127.0.0.1/32    trust
host    all    all    ::1/128         trust
```

Change `host` to `hostssl` on both, and change `trust` to `scram-sha-256` so a password is actually required:

```
hostssl    all    all    127.0.0.1/32    scram-sha-256
hostssl    all    all    ::1/128         scram-sha-256
```

Leave the `local` line (the Unix socket) alone so you can still administer the server without a password. Apply the change:

```bash
psql -d postgres -c 'SELECT pg_reload_conf()'
```

## 6. Create the database and role for Django

```bash
createdb myapp
psql -d postgres -c "CREATE ROLE myapp LOGIN PASSWORD 'devpassword'"
psql -d postgres -c "ALTER DATABASE myapp OWNER TO myapp"
psql -d myapp    -c "GRANT ALL ON SCHEMA public TO myapp"
psql -d postgres -c "ALTER ROLE myapp CREATEDB"
```

The last two lines save you two confusing errors later. Since Postgres 15 a plain role no longer gets create rights on the `public` schema, so migrations fail with "permission denied for schema public" without that grant. And `manage.py test` builds a throwaway `test_myapp` database, which needs `CREATEDB`.

## 7. Point Django at it

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "USER": "myapp",
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": "localhost",   # must not be empty, see below
        "PORT": "5432",
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": os.path.expanduser("~/pgcerts/ca.crt"),
        },
    }
}
```

`HOST` is the single most common thing that silently defeats this whole setup. If you leave it empty (or set it to `/tmp`), Django connects over a Unix domain socket, which is a local file, carries no TLS at all, and ignores `sslmode` entirely. Your app works, you assume TLS is on, and it is not. It must be `localhost` or `127.0.0.1`.

Install a driver if you have not: `pip install "psycopg[binary]"` for psycopg 3 (Django 4.2 and newer), or `pip install psycopg2-binary` for the older one. The `ENGINE` string and the `OPTIONS` keys are the same either way; both pass those keys straight through to libpq.

If you use `DATABASE_URL` with `dj-database-url` instead, the equivalent is:

```
postgres://myapp:devpassword@localhost:5432/myapp?sslmode=verify-full&sslrootcert=/Users/you/pgcerts/ca.crt
```

## 8. Prove it, twice

A positive test. This asks the server itself what it thinks of the connection:

```bash
psql "host=localhost dbname=myapp user=myapp sslmode=verify-full sslrootcert=$HOME/pgcerts/ca.crt" \
  -c 'SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid()'
```

You want `t` and something like `TLSv1.3`.

A negative test, which is the one that actually tells you the guard works:

```bash
psql "host=localhost dbname=myapp user=myapp sslmode=disable"
```

This must fail with "no pg_hba.conf entry ... no encryption". If it connects, step 5 did not take effect.

Then the same check through Django, so you are testing the path your app really uses:

```bash
python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute('SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid()')
    print(c.fetchone())
"
```

If `-c` is not supported on your Django version, paste the same three lines into `python manage.py shell`.

---

## Things that will bite you later

**The socket bypass.** Covered above, but it is worth repeating because it is invisible. Any tool you point at this database, `psql`, pgAdmin, a test runner, a Celery worker, uses TLS only when it connects over TCP with an explicit host.

**Typing the CA path constantly.** libpq reads `~/.postgresql/root.crt` by default and does not consult the macOS keychain at all. Run `mkdir -p ~/.postgresql && cp ~/pgcerts/ca.crt ~/.postgresql/root.crt` and then plain `sslmode=verify-full` works without the `sslrootcert` argument.

**Expiry.** The server certificate above is good for 825 days, the CA for ten years. When connections suddenly fail with a certificate error in about two years, rerun step 3's last two commands and restart.

**Secrets in git.** `ca.key` and `server.key` are private keys. They live in `~/pgcerts`, outside your repo, which is deliberate. If you ever move them into the project, add them to `.gitignore` first.

**Production will use a different CA.** RDS, Cloud SQL, Supabase and Neon each publish their own root certificate. Keep the CA path in an environment variable rather than hardcoded, so only the value changes between environments, never the code.

**Client certificates.** If production requires mutual TLS (the client proving its identity with a certificate too, via `sslcert` and `sslkey`), that is a further step on top of this. Say so and I will extend the setup.

---

## What I could not verify from here

I do not have access to your machine, so these are all assumptions rather than observations:

- **The Postgres version.** I wrote `postgresql@17`; run `brew search 'postgresql@'` and substitute whatever is current. The steps do not change between recent versions.
- **Apple Silicon vs Intel.** I used `/opt/homebrew` paths. Intel Macs use `/usr/local`. `brew --prefix` prints yours.
- **Your data directory, config file and hba file locations.** The `SHOW` commands in step 2 print the real ones; do not trust any path I wrote.
- **Whether port 5432 is already taken**, and whether you have an existing `postgresql.conf` with settings that conflict.
- **Your Django version, driver, and settings layout.** I assumed a standard `settings.py` with `DATABASES`; adjust if you use split settings or a `DATABASE_URL`.
- **Your production database's TLS requirements**, which should ultimately drive the local `sslmode` you rehearse against.

If any command gives you output you did not expect, paste it and I will work backwards from it.
