Here's the full path from a clean Homebrew install to Django talking to Postgres over a verified TLS connection. Nine steps, each with a check so you know it worked before moving on.

Two things to know before you start, because they cause most of the confusion:

- **TLS only applies to TCP connections.** Postgres over a Unix socket is never encrypted, and it never errors about it. If Django's `HOST` is blank, it uses the socket and your SSL config does nothing, silently. Every step below uses `127.0.0.1` deliberately.
- **`sslmode=require` does not verify anything.** It encrypts, but accepts any certificate from anyone. `verify-full` is the mode that checks the certificate was signed by a CA you trust and that the hostname matches. We'll set up `verify-full`, since a dev setup that skips verification won't catch the mistakes you're trying to catch.

I can't see your machine, so I haven't verified your Homebrew prefix, which Postgres majors your Homebrew has, whether you already have a Postgres data directory, which `openssl` is first on your PATH, or your Django/psycopg versions. Every step has a command whose output tells you the answer, so run them rather than assuming my defaults match.

## 1. Install Postgres and put it on your PATH

```bash
brew search postgresql@
```

Pick the newest major that appears. I'll use 18 below; substitute yours everywhere.

```bash
export PG=postgresql@18
brew install $PG
```

Homebrew's Postgres formulae are "keg-only," meaning `brew install` deliberately does not symlink `psql` into your PATH (so it can't collide with other Postgres versions). Add it yourself:

```bash
echo "export PATH=\"\$(brew --prefix)/opt/$PG/bin:\$PATH\"" >> ~/.zshrc
exec zsh
export PG=postgresql@18   # re-set it, the new shell dropped it
which psql && psql --version
```

If `which psql` prints nothing, the PATH line didn't take. Check that you're actually using zsh (`echo $SHELL`); if it's bash, append to `~/.bash_profile` instead.

## 2. Start the server and confirm it's alive

Homebrew runs `initdb` for you during install, so the data directory already exists.

```bash
brew services start $PG
psql postgres -c 'select version();'
```

That `psql` call goes over the Unix socket and should print the version string. If it fails with "connection refused," read the log before doing anything else:

```bash
tail -40 "$(brew --prefix)/var/log/$PG.log"
```

Set the data directory path now; the rest of the steps use it:

```bash
export DATA_DIR="$(brew --prefix)/var/$PG"
ls "$DATA_DIR/postgresql.conf"
```

## 3. Create a local certificate authority and a server certificate

Postgres needs a certificate and a private key. For `verify-full` to be meaningful, the certificate has to be signed by something, so you'll make a one-off CA that exists only on this laptop and sign with it.

```bash
mkdir -p ~/pgcerts && cd ~/pgcerts

# The CA: this is what Django will be told to trust.
openssl req -new -x509 -nodes -newkey rsa:4096 -days 3650 \
  -keyout ca.key -out ca.crt \
  -subj "/CN=Local Dev Postgres CA"

# The server's own key and a signing request.
openssl req -new -nodes -newkey rsa:2048 \
  -keyout server.key -out server.csr \
  -subj "/CN=localhost"

# Subject Alternative Names. Modern TLS clients check SANs, not CN, so
# both the hostname and the IP you might connect as have to be listed.
cat > server.ext <<'EOF'
subjectAltName = DNS:localhost, IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 825 -sha256 -extfile server.ext
```

Check the SANs actually landed:

```bash
openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"
```

You should see `DNS:localhost, IP Address:127.0.0.1`. If that section is missing, the `-extfile` was ignored, and `verify-full` will fail later with a hostname mismatch.

macOS ships LibreSSL as `/usr/bin/openssl`, not OpenSSL, and it occasionally differs on flags. If any of the above errors out, install real OpenSSL and use it explicitly:

```bash
brew install openssl@3
export PATH="$(brew --prefix openssl@3)/bin:$PATH"
```

## 4. Install the certificate into the data directory

```bash
cp server.crt server.key "$DATA_DIR/"
chmod 600 "$DATA_DIR/server.key"
ls -l "$DATA_DIR/server.key"
```

The permissions matter: Postgres refuses to start if the private key is readable by group or others. You want `-rw-------` and your own username as owner. This is the most common "it worked yesterday" failure after copying files around.

## 5. Turn SSL on

Settings later in `postgresql.conf` override earlier ones, so appending is safe and avoids fiddling with the commented-out defaults:

```bash
cat >> "$DATA_DIR/postgresql.conf" <<'EOF'

# --- local dev TLS ---
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
EOF
```

Those filenames are relative to the data directory, which is why the plain names work.

## 6. Create the database role and database

Do this **before** locking down authentication, so you have a working password when the trust rules go away.

```bash
createuser --pwprompt djangouser
createdb -O djangouser myapp
```

Pick a password at the prompt and keep it; you'll put it in an environment variable in step 8.

## 7. Require SSL for TCP connections

Open `$DATA_DIR/pg_hba.conf`. Homebrew ships something like this:

```
local   all   all                trust
host    all   all   127.0.0.1/32 trust
host    all   all   ::1/128      trust
```

Change the two `host` lines to `hostssl`, and `trust` to `scram-sha-256`, leaving the `local` line alone:

```
local     all   all                trust
hostssl   all   all   127.0.0.1/32 scram-sha-256
hostssl   all   all   ::1/128      scram-sha-256
```

`hostssl` means the rule only matches TLS connections, so a plaintext TCP attempt is now rejected outright instead of quietly succeeding. Keeping `local ... trust` leaves you a working way in over the Unix socket if you break the TCP config, which is worth having.

Confirm what you actually wrote:

```bash
grep -v '^#' "$DATA_DIR/pg_hba.conf" | grep .
```

Then restart. `ssl = on` needs a full restart, not just a config reload:

```bash
brew services restart $PG
tail -20 "$(brew --prefix)/var/log/$PG.log"
```

If the server didn't come back, the log names the reason. The usual two are key file permissions (step 4) and a typo in `pg_hba.conf`.

## 8. Verify with psql before touching Django

This is the step that tells you whether the problem is Postgres or Django, so don't skip it.

```bash
psql "host=127.0.0.1 dbname=myapp user=djangouser sslmode=verify-full sslrootcert=$HOME/pgcerts/ca.crt"
```

At the prompt:

```sql
SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();
```

You want `ssl = t` and a TLS version like `TLSv1.3`. Also confirm the negative case, which proves `hostssl` is doing its job:

```bash
psql "host=127.0.0.1 dbname=myapp user=djangouser sslmode=disable"
```

This should be **rejected** with "no pg_hba.conf entry ... no encryption". If it connects, your `hostssl` edit didn't take effect.

## 9. Point Django at it

Install a driver if you haven't (psycopg 3 is the current one, and Django 4.2+ supports it):

```bash
pip install "psycopg[binary]"
```

In your settings module:

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "USER": "djangouser",
        "PASSWORD": os.environ["DJANGO_DB_PASSWORD"],
        "HOST": "127.0.0.1",   # required: blank means Unix socket, which is unencrypted
        "PORT": "5432",
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": os.path.expanduser("~/pgcerts/ca.crt"),
        },
    }
}
```

Everything in `OPTIONS` is passed straight to libpq, which is why the same `sslmode` and `sslrootcert` names work here as on the `psql` command line.

Set the password in your shell (or your `.env` loader) and run:

```bash
export DJANGO_DB_PASSWORD='...'
python manage.py migrate
```

Then confirm Django's own connection is encrypted, rather than assuming it inherited what psql did:

```bash
python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute('SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid()')
    print(c.fetchone())
"
```

A tuple like `(True, 'TLSv1.3', 'TLS_AES_256_GCM_SHA384')` means you're done.

## Things that will bite you later

**Don't commit the keys.** Add to `.gitignore`:

```
pgcerts/
*.key
```

`ca.key` in particular signs certificates your Django app trusts.

**The server certificate expires in 825 days.** When it does, you'll get `certificate verify failed` and nothing else useful. Re-run step 3's last two commands (the CSR and the signing) and restart Postgres. The CA is good for 10 years.

**Hostname has to match the certificate.** The SANs cover `localhost` and `127.0.0.1`. If you later set `HOST` to your machine's `.local` name or a Docker service name, `verify-full` will reject it until you reissue the certificate with that name in `server.ext`.

**A local CA is a dev pattern, not a production one.** In production you don't generate anything: you download your provider's CA bundle (RDS, Cloud SQL, Supabase all publish one) and point `sslrootcert` at that. The Django settings shape stays identical, which is the point of setting it up this way now.

**If you ever install a second Postgres major**, `brew services` will happily run both and fight over port 5432. `brew services list` shows what's running.
