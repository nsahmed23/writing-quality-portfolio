**EMFILE fires when your Fastify process asks the kernel for a new file descriptor and the kernel refuses because that process has hit its open-file ceiling.** The premise in your question is correct: running out of descriptors is exactly what triggers this error, not a side effect of something else.

Quick grounding on the mechanism: every open file, TCP socket, and pipe a process holds occupies one slot in that process's file descriptor table. Linux caps the size of that table per process, via a soft and hard limit (`ulimit -n`, formally `RLIMIT_NOFILE`), separately from a system-wide cap (`fs.file-max`). EMFILE specifically means the per-process limit was hit; hitting the system-wide cap instead produces a different error, ENFILE. So the fix lives in your process's behavior and its per-process limit, not in some global OS setting.

That also explains why it takes down the whole server instead of just failing one request. EMFILE usually surfaces either as an uncaught exception in code that isn't wrapped in a try/catch around the failing call, or as an `error` event on the listening socket itself when `accept()` fails. Node's default response to either is to crash the process. Fastify's built-in error handling only covers errors thrown inside a registered route handler; a leak in a connection pool, a background timer, or the raw accept loop sits outside that boundary.

Two different things are being called "the cause" here, and they matter differently:

1. **Proximate cause**: open descriptors reached the limit, so the next `open()` or `socket()` call failed. This is what the error message reports.
2. **Root cause**: something is opening descriptors faster than it closes them, so the count never levels off. The message doesn't say what.

The six-hour-under-load detail points at the root cause being a leak rather than a genuine concurrency ceiling. If your workload simply needed more simultaneous connections than the limit allows, you'd hit EMFILE almost immediately at peak load, not six hours in. A slow, steady climb to the ceiling is the signature of something opening descriptors and skipping the close, often only on an error branch that rarely fires during normal testing.

Common leak sources in a Fastify/Node stack, roughly in likelihood order:

1. A database or Redis client opened per request instead of drawn from a pool, or a pool whose connections aren't released when a query throws.
2. `fs.createReadStream` (file uploads, static responses) left open when the client disconnects mid-request or the stream errors.
3. Outbound HTTP clients (undici, axios, fetch with a keep-alive agent) accumulating sockets instead of reusing them.
4. WebSocket or SSE connections whose `close`/`error` handlers don't run cleanup.
5. A mismatch between how long nginx keeps idle upstream connections open (its `keepalive` setting for the backend) and how long Fastify's server keeps them open (`server.keepAliveTimeout`), so one side holds sockets the other has already dropped.

I can't see your code, your process, or your nginx config, so I can't tell you which of these it is, confirm your actual `ulimit -n`, or know whether PM2, Docker, or a systemd unit is overriding whatever the shell reports. To narrow it down:

1. Check the limit the live process actually runs under: `cat /proc/<pid>/limits | grep "open files"`. This can differ from what a plain `ulimit -n` shows if a supervisor sets its own limit.
2. Watch the count under real load: `watch -n 5 'ls /proc/<pid>/fd | wc -l'`. A number that climbs steadily and never drops confirms a leak; one that plateaus points at a genuine concurrency ceiling instead.
3. Once it's elevated, see what's actually open: `lsof -p <pid>`. Mostly `socket:[...]` entries means connections; mostly regular file paths means unclosed file handles.
4. Capture the full stack trace on the next crash, not just the message. Where the throw originates (fs call, DB driver, HTTP client) tells you which source above to chase.

Steps 1 and 3 take a couple of minutes each; step 2 only means something after it's run for at least an hour under real traffic.

Raising `ulimit -n` (or systemd's `LimitNOFILE`) buys time by moving the ceiling, but if the count is genuinely unbounded, you'll just hit the new ceiling later. Treat it as a stopgap unless step 2 shows the count plateauing under real peak load rather than climbing indefinitely.

Next: run `cat /proc/<pid>/limits | grep "open files"` against the live process now, so you know the actual ceiling you're working against.
