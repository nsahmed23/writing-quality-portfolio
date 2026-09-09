EMFILE isn't a Node bug; it's a Linux resource limit surfacing through Node. Every open socket, file, and pipe counts against a per-process cap on file descriptors (`ulimit -n`). When your process tries to open one more, accepting a new connection, opening a file, connecting to a database, the kernel's `open()`/`accept()`/`socket()` call fails with the errno `EMFILE` instead of handing back a new descriptor. libuv, the C library under Node's event loop, surfaces that errno as the `Error: EMFILE: too many open files` you're seeing, thrown from whatever operation just tried to grab a descriptor. (The system-wide version of this is `ENFILE`; you're hitting the per-process limit, which is almost always the one you hit first.)

The telling detail in your report is the six hours under load before it dies, not that it dies at all. If the limit were simply too low for your real concurrency, you'd hit it quickly and repeatably at a given load level, not gradually over hours. A slow climb to the ceiling is the signature of a leak: something in the request path opens a socket or file and doesn't release it, at a low enough rate per request that it takes hours of sustained traffic to exhaust the limit.

It's also worth checking exactly where the EMFILE is thrown, because that explains why it takes the whole server down rather than just failing one request. Node doesn't automatically retry a failed `fs` operation or outbound connection; it just surfaces the error to whatever called it. If that call is inside a request handler and the rejection or throw isn't caught (no `try/catch` around an `await`, no `.catch()`, and no `unhandledRejection`/`uncaughtException` handler at the process level), Node's default behavior is to crash the whole process on an uncaught error. That matches "dies" much better than a single failed request would, and it's a strong hint that the fix isn't just about the FD limit but about error handling somewhere in the request path too.

**Where the leak probably is**

For a Fastify app behind nginx, roughly in order of likelihood:

- **Sockets stuck in `CLOSE-WAIT`.** If a handler calls out to a database, Redis, or an external API (via `undici`/`fetch`/`axios`/a driver's pool) and the response isn't fully consumed or the connection isn't released on every code path, including error paths, the socket sits half-closed. It still counts as an open FD until your process actually closes it.
- **The nginx-to-Node keep-alive connection itself.** If nginx's `keepalive_timeout`/`proxy_http_version` settings and Fastify's `server.keepAliveTimeout`/`headersTimeout` disagree about how long a connection should live, you get connection churn, and anything on the Node side holding a reference that prevents a socket's close handler from firing will leak on every churn cycle.
- **Database or cache pool leaks.** A client acquired from a pool (`pg`, `mysql2`, `ioredis`, etc.) that isn't released when a query throws mid-flight eventually exhausts the pool, and the underlying sockets can leak independently of the pool's own accounting.
- **File or log streams without a `finally`.** Any `fs.createReadStream`/`fs.open`/log file handle opened per request, or a `fs.watch` call from a dependency, that isn't guaranteed to close on the error path leaks one descriptor per failure.
- **Upload handling.** With `multer`/`busboy`/Fastify's multipart plugin, a client aborting an upload mid-stream can leave a temp file descriptor open if the abort path isn't handled explicitly.

I don't have your code, logs, or server, so I can't tell you which of these it actually is, only that the multi-hour-under-load pattern points at one of them rather than at simple under-provisioning.

**Confirming it before it happens again**

Get the PID (`systemctl status <your-service>` or `ps aux | grep node`), then:

1. Watch the count climb: `watch -n 5 "ls /proc/<PID>/fd | wc -l"`. Steady growth under load that never drops back down between bursts confirms a leak rather than legitimate concurrency.
2. See what's accumulating: `lsof -p <PID>` and check the TYPE column. Mostly `sock`? Run `ss -tnp | grep <PID>` and look at connection states; a growing pile of `CLOSE-WAIT` is a leaked-socket signature specifically. Mostly `REG`? That points at unclosed file handles instead.
3. Confirm the real limit in force: `cat /proc/<PID>/limits` and check "Max open files". Don't trust `ulimit -n` in your own shell. If the app runs as a systemd unit, its limit comes from `LimitNOFILE` in the unit file, or systemd's default if the unit doesn't set one, which on Ubuntu 22.04 is commonly a soft limit of 1024. (If it's PM2 or Docker instead, check that process manager's own file descriptor settings rather than systemd's.)

**Fixes**

Raising the limit (`LimitNOFILE=65535` in the unit's `[Service]` section, then `systemctl daemon-reload` and a restart) is worth doing regardless, since 1024 is low for real concurrent load. But if there's a genuine leak, this only buys time before the next crash; it doesn't fix it. Use it as a stopgap while you track down the actual unclosed resource with the diagnostics above, and then fix the specific path that fails to close it: add the missing `.destroy()`/`.release()`/`.close()` in a `finally` block, or align the keep-alive timeouts between nginx and Fastify. Add an `uncaughtException`/`unhandledRejection` handler too if you don't have one, at minimum to log which operation is throwing before the process exits, so the next occurrence tells you exactly where to look instead of just "EMFILE" with no context.

Once it's fixed, add a standing check rather than waiting for the next crash: a Prometheus `node_exporter` `process_open_fds` metric with an alert threshold, or even just a periodic log line of `fs.readdirSync('/proc/self/fd').length`, so you see the climb hours before it becomes an outage.
