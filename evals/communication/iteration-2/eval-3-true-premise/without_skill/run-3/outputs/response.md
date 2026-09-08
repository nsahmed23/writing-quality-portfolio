EMFILE isn't a separate consequence of running out of file descriptors, it's the literal name for that condition. On Linux, every open socket, file, and pipe your process holds counts against a per-process ceiling (`RLIMIT_NOFILE`, what `ulimit -n` reports). When your Fastify process tries to accept one more connection or open one more file while it's already at that ceiling, the kernel refuses and Node surfaces it as `EMFILE: too many open files`. It's specifically EMFILE and not ENFILE because the ceiling being hit is your process's own limit, not the system-wide one; if the whole box were out of descriptors you'd expect other services to start failing around the same time too. So the real question isn't why hitting the limit produces this error, it's why your process is accumulating descriptors until it reaches that limit at all.

The ~6-hour-under-load pattern is the tell. If your traffic just needed more concurrent descriptors than the limit allows, you'd see EMFILE near peak load, not on a slow clock that runs out regardless of the specific spike. Dying reliably after a fixed run time under sustained traffic is the signature of a leak: something in the request path opens a socket or file handle and doesn't close it on every path, including error paths, so the open-fd count ratchets upward request after request until it crosses the ceiling.

**Likely sources, given Fastify behind nginx:**

- Outbound connections your app makes per request (database, Redis, an internal API, S3, etc.) that aren't pooled with a bounded max, or that leak when a request throws before the connection or response stream gets released back to the pool. This is the most common cause in practice.
- File streams opened by `@fastify/multipart` (uploads) or `@fastify/static` that never get closed when a client aborts mid-request or a handler throws before fully consuming the stream.
- A DB client pool (`pg`, `mysql2`, etc.) where `client.release()` or the equivalent only runs on the success path instead of in a `finally`.
- Log file destinations (pino with a file transport, or a hand-rolled `fs.createWriteStream` for access logs) that get reopened per write instead of held open once.
- Long-lived connections, WebSockets or SSE, whose sockets aren't cleaned up on disconnect.

nginx itself is a less likely culprit but worth a quick check: if your upstream block doesn't set `keepalive N;` (with `proxy_http_version 1.1;` and `proxy_set_header Connection "";`), nginx opens a fresh TCP connection to Fastify per request instead of reusing a small pool. That alone usually isn't enough to cause a leak, but it raises the baseline load on Node to close connections promptly, which makes a real leak elsewhere tip over the ceiling sooner.

**Confirming it's a leak and finding the source, on the running box:**

1. Check the limit the process is actually running under, since it can differ from your shell's `ulimit -n` depending on how it's launched:
   `cat /proc/<pid>/limits | grep "open files"`
2. Watch the count over time and correlate with traffic:
   `watch -n 30 'ls /proc/<pid>/fd | wc -l'`
   Climbing steadily and never dropping back between traffic dips confirms a leak rather than a legitimate concurrency ceiling.
3. Once it's climbing, sample what the descriptors actually are:
   `lsof -p <pid>` (or `ls -l /proc/<pid>/fd` if `lsof` isn't installed)
   Sockets piling up toward one remote address points at an unpooled or unreleased outbound client or DB connection. Regular files piling up points at logging, uploads, or static-file handling.
4. If you can catch it live, run the process with `--report-on-signal` and trigger `kill -USR2 <pid>` while the count is elevated; the generated diagnostic report includes the active libuv handle list.

**Fixes:**

- Immediate mitigation, not a fix: raise the limit for more runway before a crash (systemd unit: `LimitNOFILE=65536`; pm2: the equivalent env or config option; Docker: `--ulimit nofile=65536:65536`). This delays the same crash if the leak itself isn't addressed.
- Real fix: audit every place the app opens a socket or file and make sure the close or release happens in a `finally`, or that the stream's `error` handler also calls `.destroy()`, not just the success path. For outbound HTTP, use a client or agent with an explicit `maxSockets` or `connections` cap so a burst can't open unbounded connections. For DB clients, confirm the pool's release or end is called even when the query throws.

I don't have access to your code, nginx config, or how the process is launched (systemd, pm2, Docker, or bare `node`), so I can't point to the specific line that's leaking. The steps above should narrow it to a specific subsystem (outbound client, DB pool, file streams, or logging) within a single run, since you already have a reliable ~6-hour reproduction window.
