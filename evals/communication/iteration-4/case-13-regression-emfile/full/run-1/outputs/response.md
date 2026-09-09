Your premise is correct, and the chain is short with no intermediate step. A file descriptor is a small integer the kernel hands your process for every open thing it holds: a log file, an accepted TCP connection from nginx, an outbound socket to Postgres or another API, a pipe, an epoll instance. The kernel caps how many one process may hold at once (`RLIMIT_NOFILE`, the soft "open files" limit). At the cap, the next request for one does not queue or wait. `open()`, `socket()`, `accept()`, or `pipe()` returns -1 and sets `errno` to `EMFILE`, and Node prints that errno string verbatim as `Error: EMFILE: too many open files`.

One lookalike worth separating now: `EMFILE` is your process hitting its own limit, while `ENFILE` ("too many open files in system") is the whole machine hitting `/proc/sys/fs/file-max`. Different problem, different fix. Your message says EMFILE, so this is per-process.

## Why it kills the app instead of degrading

Once you are at the ceiling, nearly everything that needs a new descriptor fails at once, including the operations you would use to recover: opening a log file, connecting to the database, accepting the next request. In most Node code paths that error is not caught, and the uncaught exception or unhandled rejection exits the process. The accept loop itself is more forgiving, since libuv keeps one spare descriptor in reserve so it can accept and immediately close new connections rather than spin, which is why the fatal error usually surfaces from your own code (an `open` or an outbound `socket`) rather than from the listener.

## What "dies after ~6 hours" tells you, and what it does not

It tells you the descriptor count grows with elapsed time or accumulated work and crosses the limit at around six hours. It does not tell you why the count grows. Two very different situations produce the same six-hour crash:

- **A leak.** Descriptors are opened and never closed, so the count climbs steadily and never levels off. The limit value is almost irrelevant here; it only sets the clock.
- **An undersized limit.** The count climbs to a legitimate level for your real concurrency and plateaus there, but that plateau sits above your limit. Six hours is just how long traffic took to ramp.

I cannot see your server, so I do not know which of these you have, what your current limit is, or what those descriptors actually are. All of that is unverified and the steps below are how to settle it. You also have not mentioned a deploy or config change, so I am treating this as ongoing behavior rather than something a recent change introduced.

## Find the shape and the culprit

Steps 1 to 4 take about five minutes total. Step 5 needs 30 to 60 minutes of normal traffic, because it is the one that distinguishes leak from undersized limit. Add `sudo` to the `/proc` reads if the service runs as a different user than your login.

1. Get the process id and read the real limit next to the current count.

   ```bash
   PID=$(systemctl show -p MainPID --value your-fastify-service)
   grep 'Max open files' /proc/$PID/limits
   ls /proc/$PID/fd | wc -l
   ```

   The `Max open files` line shows soft and hard limits. On Ubuntu 22.04 the soft limit for a systemd service is commonly 1024 unless the unit overrides it, but read the real number rather than trusting that.

2. Get the full error line, not just the prefix you quoted.

   ```bash
   sudo journalctl -u your-fastify-service --since '24 hours ago' | grep -m5 EMFILE
   ```

   Node appends the failing syscall and resource after the comma. `, open '/var/log/app.log'` points at file handles; `, socket` or a `connect` frame points at outbound connections. That alone halves the search space.

3. Break the open descriptors down by type.

   ```bash
   sudo ls -l /proc/$PID/fd | awk '{print $NF}' | sed 's/:\[[0-9]*\]//' | sort | uniq -c | sort -rn | head -20
   ```

   A few thousand `socket` entries means connections. A repeated file path means an fs handle opened in a loop.

4. If it is sockets, get their states and their direction.

   ```bash
   sudo ss -tanp | grep "pid=$PID," | awk '{print $1}' | sort | uniq -c | sort -rn
   ```

   A large `CLOSE-WAIT` count means the peer closed and your app never called `close()`, which is the classic leak signature. Then split by local port: sockets whose local port is your Fastify port are inbound from nginx; everything else is outbound calls your app made. Whichever side is growing is where the bug lives.

5. Sample the count over time to see the shape.

   ```bash
   while sleep 60; do echo "$(date +%T) $(ls /proc/$PID/fd | wc -l)"; done
   ```

   A line that climbs and never flattens is a leak. A line that rises and plateaus is real concurrency against a limit that is too low.

## Then fix the one you actually have

**If it is a leak**, these four sources cover most Fastify cases, most likely first:

1. Outbound HTTP responses whose bodies are never consumed. `fetch` in Node 18+ is undici, which holds the socket until the body is read or cancelled. Every `fetch` needs `await res.json()`, `await res.text()`, or an explicit `res.body.cancel()`, including on the error branches where you already know you do not want the body.
2. A client constructed per request instead of once at boot. A `new Redis(...)`, a new `pg.Pool`, or a new `Agent` inside a route handler opens a fresh connection every call.
3. Streams opened on a path that throws before close. `fs.createReadStream` without `pipeline()` or an error handler leaks the handle on failure.
4. Real long-lived connections with no idle timeout (websockets, SSE), plus nginx upstream `keepalive` holding idle sockets open. Not a leak, but it consumes the same table and raises the floor everything else sits on.

**If the limit is simply too low**, raise it on the unit, not in your shell:

```bash
sudo systemctl edit your-fastify-service
```

```ini
[Service]
LimitNOFILE=65535
```

```bash
sudo systemctl daemon-reload && sudo systemctl restart your-fastify-service
grep 'Max open files' /proc/$(systemctl show -p MainPID --value your-fastify-service)/limits
```

The trap that costs people an afternoon: `/etc/security/limits.conf` and `ulimit -n` in your SSH session do not affect a systemd service. PAM applies `limits.conf` at login, while systemd sets a service's limits from the unit file. The last command above is the only proof that the new value took.

Raising the limit while a leak is still present is a stopgap, and a short one. If you crash at 1024 in six hours and the growth is roughly linear, going to 65535 buys about 64 times as long, so roughly two weeks, then the same crash. Do it to stop the bleeding tonight, then run step 5 to find out whether you needed it.

Start at step 1. If `Max open files` reads 1024 and the live count is already in the high hundreds, you know you are near the ceiling before the sample in step 5 even finishes.
