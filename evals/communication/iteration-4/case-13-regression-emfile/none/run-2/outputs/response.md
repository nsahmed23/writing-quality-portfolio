There's a small loop in the premise worth untangling first: EMFILE isn't a *consequence* of running out of file descriptors, it's the *name* of that event. `EMFILE` ("too many open files") is what the Linux kernel returns when a process asks for a new file descriptor and is already at its `RLIMIT_NOFILE` soft limit. Sockets, regular files, pipes, epoll instances, and inotify watches all draw from that same per-process budget. So the question with an actual answer is: what is your Fastify process opening and never closing?

Two things your description already narrows down.

**Dying at a consistent ~6 hours means a permanent leak, not concurrency.** Legitimate load makes fd count track traffic and plateau, and you'd die at your daily peak rather than at a fixed offset from each restart. A clean climb to the ceiling on a stopwatch means some path takes an fd and never gives it back. This also rules out the whole class of bugs that hold an fd for a *bounded* time (an undici response body you never read is freed when `bodyTimeout` fires, 5 minutes by default). Those settle at a plateau of `rate × hold time`; they don't ramp for six hours.

**Ignore the stack trace on the EMFILE.** Whatever call happens to need the next fd is what throws, and it's almost never the leaking code. Chasing that trace burns hours.

## 1. Get the real ceiling and the current count

```bash
PID=$(systemctl show -p MainPID --value your-app.service)   # or: pgrep -f 'node.*server'
grep 'open files' /proc/$PID/limits
ls /proc/$PID/fd | wc -l
```

Check the actual limit rather than assuming. On Ubuntu 22.04 (systemd 249) services get a **1024 soft** limit by default, no matter what `ulimit -n` says in your shell, and `/etc/security/limits.conf` does *not* apply to systemd units (that's PAM, for login sessions). If you're under Docker or PM2 the limit comes from there instead. A round 1024 ceiling is a very common reason a Node service falls over at a suspiciously regular interval.

Related term, in case you see it later: `EMFILE` is the *per-process* limit; `ENFILE` is the *system-wide* one (`/proc/sys/fs/file-max`). Your error is the per-process one.

## 2. Confirm the shape of the leak

```bash
while true; do echo "$(date +%s) $(ls /proc/$PID/fd | wc -l)"; sleep 60; done | tee fds.log
```

Straight line up = leak. Sawtooth or plateau = you're just under-provisioned and step 5 is your fix.

## 3. Do the arithmetic, it narrows the search a lot

Leak rate = `(limit - baseline_after_warmup) / minutes_to_death`. At a 1024 limit with a ~50 fd baseline dying in 6 hours, that's `974 / 360 ≈ 2.7 fds/min`. Now divide by your request rate. If you serve 500 req/min, roughly 1 request in 185 leaks, which means it is **not** the happy path; look at error branches, rare endpoints, or a scheduled job. If the leak rate is near your request rate, it's every request. If it lands suspiciously close to a cron or `setInterval` period, you've found it.

## 4. Classify what's actually leaking

```bash
for f in /proc/$PID/fd/*; do readlink "$f"; done \
  | sed 's/:\[[0-9]*\]/:/' | sort | uniq -c | sort -rn | head -20

sudo ss -tanp | grep "pid=$PID" | awk '{print $1}' | sort | uniq -c
```

How to read the result:

- **Mostly `socket:` in `CLOSE-WAIT`** (the peer sent FIN, your side never called `close`): you're holding sockets that are already dead. Usually a socket you took ownership of (`request.raw.socket`, an upgrade/WebSocket handler, a raw `net` connection) or a stream that errored without cleanup.
- **Mostly `ESTAB` to one upstream `ip:port`**: connection pool leak, see #1 below.
- **Lots of `ESTAB` back toward nginx**: inbound sockets aren't being reaped, see #5 below.
- **The same file path repeated**: an `fs` handle never closed.
- **`anon_inode:[eventpoll]` climbing**: something is creating new event loops or watchers.
- **`pipe:` climbing**: child processes spawned and never reaped (`ps --ppid $PID`).

For an in-process view, start Node with `--report-on-signal`, then at ~80% of the limit run `kill -SIGUSR2 $PID`. Node writes a diagnostic report JSON to the working directory whose `userLimits.open_files` confirms the ceiling and whose `libuv` array lists every live handle with its type and, for TCP handles, its local and remote endpoints:

```bash
jq '.libuv | group_by(.type) | map({type: .[0].type, n: length})' report.*.json
jq -r '.libuv[] | select(.type=="tcp") | .remoteEndpoint.host' report.*.json | sort | uniq -c | sort -rn
```

That second command usually names the culprit outright.

## 5. Suspects, ranked for a "never released" leak on Fastify

1. **A client/agent/pool constructed per request** and never closed: `new undici.Agent()`, `new http.Agent({keepAlive:true})`, `new pg.Pool()`, a fresh `ioredis` or Mongo client per request or per tenant. Each one holds sockets for the life of the process. This is the single most common cause of exactly your symptom.
2. **`.pipe()` instead of `stream.pipeline()`.** `.pipe()` does not destroy the source when the destination errors or the client disconnects mid-download, so the underlying `fs` handle or socket stays open forever. `stream.pipeline()` (or `pipeline` from `node:stream/promises`) does clean up. Same story for `fs.open`/`fsPromises.open` with the `close` sitting after a line that can throw, instead of in a `finally`.
3. **`@fastify/multipart` temp files** not consumed or unlinked on the error path.
4. **Child processes** spawned per request and never awaited or killed; each leaves stdio pipes behind.
5. **A disabled inbound timeout.** Worth checking specifically because nginx is in front: if someone set `keepAliveTimeout` to `0` on the Node server (a popular "fix" for nginx 502s, where the real fix is to make Node's value *larger* than nginx's `keepalive_timeout`, not zero), idle inbound sockets never time out. Same for `requestTimeout: 0` or `headersTimeout: 0`. Any client that vanishes without a FIN then costs you an fd permanently. Grep your Fastify setup for `keepAliveTimeout`, `connectionTimeout`, `requestTimeout`, `headersTimeout`.

Behind nginx with upstream keepalive, your inbound socket count should be roughly bounded by nginx's `keepalive` pool size. If it isn't, #5 is your answer.

If this started recently rather than being there all along, `git log` the deploy that preceded the first crash and look for anything on that list; it's much faster than bisecting a six-hour reproduction.

## 6. Stopgap while you hunt

```bash
sudo systemctl edit your-app.service
```
```ini
[Service]
LimitNOFILE=65535
```
```bash
sudo systemctl daemon-reload && sudo systemctl restart your-app.service
grep 'open files' /proc/$(systemctl show -p MainPID --value your-app.service)/limits
```

Be clear with yourself that this buys time proportional to the increase and fixes nothing. Going 1024 to 65535 turns a 6-hour crash into roughly a 16-day one at the same leak rate, which mostly means you stop noticing until a traffic spike compresses it back down. Pair it with an alert on fd usage so the leak stays visible:

```bash
awk -v p=$PID 'BEGIN{ "ls /proc/" p "/fd | wc -l" | getline n; print n }'
```

or expose `process.report.getReport().libuv.length` on a metrics route and graph it.

## What I could not check

I can't see your server, so none of the above is a diagnosis. I don't know your actual `RLIMIT_NOFILE`, your fd type breakdown, your Node version, your request rate, which HTTP client you use for outbound calls, or whether the process runs under systemd, PM2, or Docker. The 1024-limit and 6-hour arithmetic are illustrative and depend on what step 1 reports. Steps 1 through 4 are cheap and non-invasive; run them and the answer usually falls out of step 4 in a few minutes. If you paste the output of the `readlink` breakdown and the `ss` state counts, I can narrow it down further.
