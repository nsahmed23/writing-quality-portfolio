Short answer: every socket, pipe, and open file your process holds counts against one per-process ceiling (`ulimit -n`), typically 1024 by default on Ubuntu 22.04 unless something has raised it. Once you're at that ceiling, the next syscall that needs a new descriptor (accepting a connection, opening a file, opening an outbound socket) fails, and Node/libuv surfaces that as `EMFILE`. That part is generic to any process; it isn't Fastify-specific.

What's worth digging into is the ~6 hour timeline. Pure concurrency, just too many simultaneous connections at peak, tends to fail fast under load and recover once load drops. A slow climb to the ceiling over hours is the signature of a leak: something in the request path opens a descriptor and never closes it, so the count only goes up until it hits the wall.

**Likely sources, roughly in order of probability for a Fastify + nginx setup**

1. **Sockets stuck in `CLOSE_WAIT`.** If a client disconnects mid-request (timeout, closed tab, flaky mobile network) and nothing in your handler notices, the socket never gets closed on your end and sits open indefinitely. This shows up almost exclusively on slower endpoints: proxied calls to a slow upstream, long DB queries, SSE, file upload/download. A small, steady fraction of clients bailing early is enough to produce exactly this kind of multi-hour leak.
2. **Outbound HTTP client connections not released.** If a route calls another service (via `undici`, `fetch`, `axios`, `got`, `node-fetch`) and doesn't fully consume or explicitly cancel the response body on every path, including error and timeout branches, the underlying socket never returns to the keep-alive pool. Building a fresh agent or client per request instead of reusing one has the same effect.
3. **DB or Redis connections not returned to the pool.** Especially if release only happens on the happy path and not in a `finally`, so any thrown error leaks a connection (and its socket) permanently. Worth checking whether FD growth tracks your error rate more than your raw traffic.
4. **A client or logger instantiated per request instead of once at startup.** A DB client, HTTP agent, or file handle created inside a route handler instead of during app bootstrap opens a new descriptor on every call. This usually leaks fast enough to crash in minutes, not hours, unless the route itself is low-traffic.
5. **Log file handles.** If you're rotating logs (pino with a file destination, `pino-roll`, or similar) and something reopens the destination without closing the previous handle, you leak one descriptor per rotation.

One caution: the stack trace on the actual `EMFILE` throw doesn't point at the leak. It just shows whichever descriptor-opening call happened to hit the ceiling, often a brand-new incoming connection's `accept()`, which is almost never the code path that caused the problem.

**How to confirm which one, instead of guessing**

```bash
pgrep -f node                                              # find the PID
cat /proc/<PID>/limits | grep "open files"                 # the limit actually applied to this process
watch -n 10 'ls /proc/<PID>/fd | wc -l'                     # climbing steadily = leak; plateaus = just undersized
sudo lsof -p <PID>                                          # what the descriptors actually are
sudo ss -tnp state close-wait | grep "pid=<PID>" | wc -l    # the single most useful number here
```

If the `CLOSE_WAIT` count tracks the overall FD growth, that confirms source 1. If instead you see a growing number of `ESTABLISHED` sockets to your database or an upstream API that never drop, that points to 2 or 3.

You can also sanity-check a leak rate from what you already know: at a limit of 1024 and roughly 6 hours (~21,600s) to crash, you're losing about one descriptor every 20 seconds. Set that against your request rate (if you're running multiple workers via cluster or PM2, divide total traffic by worker count first, since each process has its own descriptor table and its own limit). At 50 req/s that's on the order of one leaked descriptor per thousand requests, which reads like an edge case (an error branch, a client-abort path, a periodic job) rather than the main happy path, since a happy-path leak at that traffic level would exhaust 1024 descriptors in a couple of minutes, not six hours.

**Two things to rule out before you go leak-hunting**

The limit might simply be too low for legitimate traffic (lots of concurrent WebSocket, SSE, or long-poll connections), in which case raising it is a real fix, not a band-aid. The `watch` command above tells you which situation you're in: a plateau means an undersized limit, an unbounded climb means a leak.

Also worth checking: if this runs under systemd, `ulimit -n` and `/etc/security/limits.conf` don't apply to it at all. Systemd services get their limit from `LimitNOFILE=` in the unit file, falling back to `DefaultLimitNOFILE` in `/etc/systemd/system.conf` if that's unset. Check the effective value with `systemctl show <service> -p LimitNOFILE`. It's a common trap to raise the limit system-wide, confirm it with a plain `ulimit -n`, and have the actual systemd-managed process still capped low because the unit file itself was never touched.

**What I can't verify from here:** I don't have your code or server, so I can't point at a specific line. I don't know what HTTP client you use for outbound calls, if any; how your DB or Redis client is instantiated and pooled; whether any route streams files or proxies long-running requests; your nginx `proxy_pass`/`keepalive` configuration; or how the process actually runs (systemd, PM2, Docker, bare `node`) and what limit it's really being given. The `ss -tnp state close-wait` count and the `/proc/<PID>/fd` growth trend from the commands above are what I'd run first; an hour or two of watching those under load will tell you whether you're chasing a socket leak, a file-handle leak, or just a ceiling that needs raising.
