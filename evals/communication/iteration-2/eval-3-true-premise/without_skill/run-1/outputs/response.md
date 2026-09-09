EMFILE is the kernel telling your process no, not Node deciding anything on its own. Every process on Linux has a cap on how many file descriptors it can hold open at once, `RLIMIT_NOFILE`, the number `ulimit -n` reports. A file descriptor covers more than files in the everyday sense: it's the handle the kernel hands back for a TCP socket (every client connection, every outbound HTTP or DB call), a pipe, an actual file on disk, an epoll instance. When your Fastify process tries to open one more of these (accept a connection, open a log file, connect to Postgres) while already at that limit, the syscall fails with `EMFILE`. libuv, the C library underneath Node's event loop, surfaces that errno, and Node wraps it as a JS `Error` whose `.code` is `'EMFILE'`.

Worth separating two similar-looking errors while we're here: `EMFILE` is per-process (you've hit your own `RLIMIT_NOFILE`); `ENFILE` is system-wide (the whole machine hit `fs.file-max`). You're seeing EMFILE, so this is scoped to the one process, not the host.

One thing explains why this takes the whole process down instead of just failing a single request. When `accept()` on your listening socket fails with EMFILE, libuv has an internal workaround in most versions: it holds a spare fd in reserve, frees it to accept the pending connection, immediately closes that connection, then reopens the spare. The point is to stop the accept loop from spinning at 100% CPU retrying the same failed call. But EMFILE can just as easily surface somewhere else: a pool connect, an `fs.open()`, a fresh outbound HTTP socket. If that call site has no catch, or your server has no `.on('error', ...)` listener, it's an unhandled exception and the process exits, which matches "dies" rather than "degrades."

**Why six hours, not immediately**

This timing is the important clue, and it points at one of two different problems that look identical from the error message alone.

The first is a slow leak: something opens a file descriptor and never closes it, for example a DB pool connection not released on an error path, an HTTP client response body never drained, an upload stream not fully consumed, or a log handle reopened without closing the old one. Each leaked fd is small, but under steady request volume they add up linearly until you cross the limit at a roughly fixed elapsed time. A predictable six hours is exactly that signature.

The second is a limit that's simply too low for legitimate concurrency. If your soft limit is the common default of 1024 and your real workload plus nginx's keepalive behavior needs more concurrent sockets than that once traffic builds up over the day, you'll hit the ceiling at your load plateau, not from the first request.

You can tell these apart without waiting for the next crash:

```
# find the pid
pgrep -f "node.*server"     # or whatever your entry file is

# the limit actually applied to that process, not your shell's ulimit
cat /proc/<pid>/limits | grep "Max open files"

# current fd count
ls -1 /proc/<pid>/fd | wc -l

# what kind of descriptor is accumulating (install lsof if it's missing)
lsof -p <pid> | awk '{print $5}' | sort | uniq -c | sort -rn
```

Log the fd count with a timestamp every minute or two over a load period. If it climbs steadily and never drops even when traffic drops, that's a leak; chase it with `lsof -p <pid>` and look for one path or connection type repeating hundreds of times. If it tracks traffic and only breaches the ceiling at peak, raising the limit is a legitimate fix, not a band-aid.

**Likely culprits, roughly in order of likelihood**

- A connection pool not releasing on the error path. With pg, mysql2, Prisma, or anything pooled: if a query throws or times out and the release back to the pool isn't in a `finally`, that socket is gone from the pool's accounting but still open. This leaks at a rate proportional to your error rate, which lines up well with a fixed number of hours to crash.
- Outbound HTTP calls (undici, axios, node-fetch) that don't fully consume the response body, or a custom `http.Agent`/`https.Agent` with no bound on sockets. An unconsumed body can prevent the underlying socket from returning to the pool.
- `@fastify/multipart` uploads where a part's stream isn't fully drained or destroyed, especially on fields you mean to ignore. The temp fd for that part leaks if you don't consume it or explicitly resume and destroy it.
- The logger writing to a file, if something in your own code (not logrotate itself) opens a new write stream or `pino.destination()` on each rotation instead of reusing one handle. This is different from logrotate's default rename-based rotation, which doesn't leak fds on its own; it just leaves Node writing into a deleted file until reopened. That's a data-loss bug, not an EMFILE cause.
- `@fastify/websocket` connections not cleaned up on client disconnect, leaving the upgraded socket open.
- Aborted requests under real traffic (mobile clients, slow connections, client-side timeouts) where a `fs.createReadStream` or proxied stream isn't destroyed when the response cuts short.

nginx is almost certainly not the direct cause since the error surfaces on the Node side, but while you're in its config, check whether the `upstream` block has a `keepalive` directive (unbounded churn to the backend under load is worth ruling out) and whether `proxy_read_timeout`/`proxy_send_timeout` are generous enough that slow backend responses aren't causing connection pileup.

**Raising the limit, if you also want to do that**

Worth doing regardless since 1024 is low for a production HTTP server, but it won't fix a genuine leak, only delay the crash. The common gotcha on Ubuntu: editing `/etc/security/limits.conf` does nothing for a systemd-managed service, since PAM only reads that file for login sessions. For a systemd unit, run `sudo systemctl edit <your-service>` and add:

```
[Service]
LimitNOFILE=65536
```

then `sudo systemctl daemon-reload && sudo systemctl restart <your-service>`, and confirm it took with `cat /proc/<pid>/limits` afterward rather than trusting the unit file alone. If this runs in Docker, the container needs its own `--ulimit nofile=65536:65536` (or the equivalent in `docker-compose.yml`); the host's limit doesn't propagate into a container automatically.

**What I can't verify from here**

I don't have your code, your Fastify plugin list, or your nginx config, so I can't tell you which of the above it actually is, only which are most likely given the symptoms you described. The `lsof -p <pid>` breakdown is the fastest way to narrow it down: a count dominated by `sock` points at pools, HTTP clients, or websockets; a count dominated by regular files points at the logger or upload handling. That single command will cut the list above roughly in half.
