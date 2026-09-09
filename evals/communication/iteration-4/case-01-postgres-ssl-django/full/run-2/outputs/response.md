```bash
brew install postgresql@17
```

That is step 1 of 11. Budget about 30 minutes the first time; the `brew install` download is the longest single wait at roughly 3 to 10 minutes, and the rest is short commands.

Two things Homebrew does for you that Linux tutorials will not prepare you for: it runs `initdb` automatically (so the database cluster already exists after install), and it makes **your macOS username** the superuser. There is no `postgres` user account on this setup. If a tutorial tells you to `sudo -u postgres psql`, it is not describing your machine.

## Install and start the server

1. `brew install postgresql@17`

   If `brew search postgresql@` shows a different set of versions, pick any of 16, 17, or 18. They behave identically for everything below; only the version number inside the paths changes.

2. Put the Postgres commands on your PATH:

   ```bash
   echo 'export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc
   exec zsh
   which psql
   ```

   Versioned Homebrew formulas are *keg-only*, meaning Homebrew deliberately does not link them into the main `bin` directory so they cannot collide with another Postgres you might install later. That is why this step is needed at all. On an Intel Mac, replace `/opt/homebrew` with `/usr/local`; run `brew --prefix` to see which one you have. `brew info postgresql@17` reprints the exact export line if you lose it.

3. Start it and confirm it answers:

   ```bash
   brew services start postgresql@17
   psql postgres -c "SELECT version();"
   ```

   If that hangs or is refused, read the log at `/opt/homebrew/var/log/postgresql@17.log`. The most common cause on a Mac is that something else already holds port 5432 (Postgres.app, or a Docker container you forgot about). Check with `lsof -nP -iTCP:5432 -sTCP:LISTEN` and stop whatever appears.

## Turn on TLS

4. Ask the running server where its files live, then generate a certificate there:

   ```bash
   psql postgres -c "SHOW data_directory;"
   ```

   Use whatever path that prints (it should be `/opt/homebrew/var/postgresql@17`) for the `cd` below. I am asking the server rather than telling you the path because I cannot see your machine, and this way the answer is right even if your install differs from my assumption.

   ```bash
   cd /opt/homebrew/var/postgresql@17
   openssl req -new -x509 -nodes -days 825 \
     -subj "/CN=localhost" \
     -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
     -keyout server.key -out server.crt
   chmod 600 server.key
   ```

   Four things worth knowing about that command:

   - `-nodes` means "no encryption on the private key." If the key had a passphrase, the server would freeze at startup waiting for someone to type it.
   - `server.crt` and `server.key` in the data directory are Postgres's built-in defaults, so putting them there saves you two config lines.
   - `chmod 600` is not optional. Postgres refuses to start with `FATAL: private key file "server.key" has group or world access`.
   - If your `openssl` rejects `-addext` (older macOS ships LibreSSL, which added that flag later), delete that line. The `CN=localhost` alone still satisfies the hostname check in step 10, because clients fall back to the common name when a certificate carries no subject alternative name.

5. Enable TLS and restart:

   ```bash
   echo "ssl = on" >> /opt/homebrew/var/postgresql@17/postgresql.conf
   brew services restart postgresql@17
   ```

   The shipped config already contains a commented-out `#ssl = off`. Appending is still safe: when a parameter appears more than once in `postgresql.conf`, the last one wins.

6. Prove the server is actually speaking TLS:

   ```bash
   psql "postgresql://localhost:5432/postgres?sslmode=require" \
     -c "SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
   ```

   You want `t | TLSv1.3 | TLS_AES_256_GCM_SHA384` or similar.

   This step trips up nearly everyone, for a reason that is genuinely confusing: plain `psql postgres` does not connect over the network at all. It connects through a Unix domain socket, which is a file on disk, and sockets never carry TLS. So a bare `psql postgres` will always report no SSL even when SSL is working perfectly. You have to name a host to get a real TCP connection.

## Create the database and lock down network access

7. Create the role and database over the socket, while it is still easy:

   ```bash
   psql postgres -c "CREATE ROLE djangouser LOGIN PASSWORD 'pick-a-real-password';"
   psql postgres -c "CREATE DATABASE djangodb OWNER djangouser;"
   ```

   Make `djangouser` the **owner**, not just a grantee. Since Postgres 15, a role that does not own the database cannot create tables in the `public` schema, and `manage.py migrate` dies with `permission denied for schema public`. Ownership avoids that entirely.

8. Require TLS for anything arriving over the network. Find the file, then edit it:

   ```bash
   psql postgres -c "SHOW hba_file;"
   ```

   Open that file (`nano` is fine) and change the two `host` lines so they read:

   ```
   hostssl all all 127.0.0.1/32 scram-sha-256
   hostssl all all ::1/128      scram-sha-256
   ```

   `hostssl` matches only encrypted TCP connections; `host` matches encrypted and unencrypted alike. `scram-sha-256` replaces `trust`, which accepts anyone claiming any username without a password.

   Leave the `local` line at the top alone. That is your socket connection, and it is how you keep administering the server, since your own superuser role has no password set.

   Reload and confirm the door is shut:

   ```bash
   psql postgres -c "SELECT pg_reload_conf();"
   psql "postgresql://localhost/djangodb?sslmode=disable"
   ```

   The second command should **fail** with `no pg_hba.conf entry ... no encryption`. A failure here is the success signal; it means unencrypted connections are now genuinely impossible rather than merely discouraged.

## Point Django at it

9. Install the driver:

   ```bash
   pip install "psycopg[binary]"
   ```

   Django 4.2 and later use psycopg 3. On anything older, install `psycopg2-binary` instead.

10. In `settings.py`:

    ```python
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "djangodb",
            "USER": "djangouser",
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

    Add `import os` at the top of the file if it is not already there; recent Django project templates import `Path` but not `os`. Then set the variable in your shell: `export DJANGO_DB_PASSWORD='pick-a-real-password'`.

    On the two `sslmode` values: `require` encrypts the connection but accepts literally any certificate the server presents, so it stops eavesdropping but not impersonation. `verify-full` additionally checks that the certificate chains up to the file named in `sslrootcert` and that the name on it matches `localhost`. A self-signed certificate is its own root, which is why pointing `sslrootcert` at the same `server.crt` you generated is correct rather than a hack.

11. Verify from inside Django, then migrate:

    ```bash
    python manage.py shell -c "from django.db import connection; c = connection.cursor(); c.execute('SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()'); print(c.fetchone())"
    python manage.py migrate
    ```

## What I could not check

Your machine is not available to me, so everything above is written from the standard Homebrew layout rather than from anything I observed:

- **Paths** assume Apple Silicon (`/opt/homebrew`). Intel Macs use `/usr/local`. Steps 4 and 8 route around this by asking the server for its own paths, so trust those over my literals.
- **Postgres version.** I assumed `postgresql@17`. I have no way to see what your Homebrew currently offers.
- **Port 5432 being free.** If Postgres.app or a Docker container is already listening, step 3 fails in a way whose error message does not point at the real cause.
- **Your shell.** `~/.zshrc` assumes zsh, the macOS default since Catalina. Run `echo $SHELL` to confirm.
- **Your Django version and project layout**, including whether `settings.py` is split across environments.

One caveat on the certificate itself: it is self-signed and its key sits unencrypted on your laptop. That is the right trade for local development and wrong everywhere else. Do not copy either file to a server. Managed providers (RDS, Cloud SQL, Neon, Supabase) publish a real CA bundle, and in production you point `sslrootcert` at that file instead, leaving the rest of the Django config unchanged. That parity is most of the value of doing this locally: it exercises your `sslmode` and certificate handling now, rather than during a deploy.

The single line that proves the whole chain worked is step 11's output: `(True, 'TLSv1.3')`. If it prints `(False, None)`, Django connected without encryption, which means step 5, step 8, or the `OPTIONS` block in step 10 did not take.
