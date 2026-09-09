EMFILE and "running out of file descriptors" aren't cause and effect; they're the same fact stated two ways. EMFILE is the kernel's name for the moment your process hits its own file descriptor limit (the per-process cap on how many open files, sockets, and pipes it can hold at once, set by `RLIMIT_NOFILE` and readable with `ulimit -n` or `/proc/<pid>/limits`), as opposed to the whole-system ceiling (`ENFILE`, controlled by `fs.file-max`), which is a much bigger number and almost never what you're actually hitting. Node's networking layer (libuv) just relays that kernel refusal upward as `Error: EMFILE: too many open files`. The real question is upstream of that: what's consuming descriptors for six hours until you cross your process's ceiling.

## Why it takes hours, not seconds

A process that needs, say, 300 open sockets at peak traffic hits its ceiling immediately if the limit sits below 300; that fails on the first spike. Failing only after about six hours of sustained load is the signature of a slow leak instead: something opens a file or socket on some fraction of requests and doesn't reliably close it, so the open count creeps upward request after request until it crosses `RLIMIT_NOFILE`. A short load test wouldn't reproduce this, since it ends before the leak climbs that far; hours of real production traffic will.

## Why the process dies, not just one request

That the whole process dies, rather than a rising rate of failed requests, is itself a clue. An EMFILE thrown inside an awaited Fastify route handler is exactly the kind of error Fastify's own error handling catches and turns into a 500 response; the process would keep running with a worse error rate, not exit. Actually dying points at the error surfacing somewhere Fastify isn't wrapping for you: the HTTP server's own accept-a-new-connection step, a stream's `error` event with no listener attached, or a fire-and-forget callback. Node's default behavior when an `error` event fires on an `EventEmitter` with nobody listening is to throw and take the process down with it, which fits "dies" better than "some requests start failing." A `server.on('error', ...)` plus a `process.on('uncaughtException', ...)` handler that logs and shuts down deliberately (or refuses new work and drains in-flight requests) turns a silent hard crash into a controlled one; it doesn't fix the leak, but it makes the failure safe to alarm on.

## Likely sources in this stack

1. Keep-alive mismatch between nginx and Node: the two sides disagree about how long an idle connection should live, so sockets pile up on whichever side still thinks the connection is good.
2. Outbound calls (a database client, requests to another service) opening a new connection per request instead of reusing a pool or a shared `http.Agent` (Node's connection-pooling object for outbound requests).
3. File streams (uploads, static files, a custom route using `fs.createReadStream`) left open when a request errors or the client disconnects mid-transfer.
4. Long-lived connections (WebSocket, SSE) whose `close` handler never runs because nothing enforces an idle timeout or heartbeat.
5. A logger or log-rotation setup that opens a new file handle on rotation without releasing the old one.

## Find out which one, on your box

About ten minutes to set up, then an hour of normal traffic shows the shape of the curve.

1. Get the PID and its real ceiling: `pgrep -f node` (or `systemctl status <unit>`), then `cat /proc/<pid>/limits | grep "open files"`.
2. Watch the count over that first hour: `watch -n 30 'ls /proc/<pid>/fd | wc -l'`.
3. If it's climbing, check what kind of handle is growing: `lsof -p <pid>` (or `ls -l /proc/<pid>/fd` if `lsof` isn't installed).
4. If it's sockets, check their state: `ss -tnp | grep "pid=<pid>"`.

Flat in step 2 means the limit is just too low for real concurrency. Climbing without bound means a leak. In step 4, a growing pile of `CLOSE_WAIT` (the remote side already closed the connection; your process hasn't called `close()` on its end yet) points at code that isn't closing something on error or disconnect. Growth in `ESTABLISHED` points at keep-alive tuning or a connection pool that isn't reusing connections.

## Raising the limit fixes a low ceiling, not a leak

If `/proc/<pid>/limits` shows a low ceiling (1024 is a common unmodified default) and step 2 shows a flat count that simply exceeds it, raising the limit is the real fix. For a systemd-managed service, add `LimitNOFILE=65536` under `[Service]` in the unit file, run `sudo systemctl daemon-reload && sudo systemctl restart <unit>`, and re-check `/proc/<pid>/limits` afterward rather than trusting `ulimit -n` in an interactive shell; systemd services don't inherit a login shell's limits, so the shell's number can be wrong for the daemon. (If this runs in a container, the limit comes from the container runtime's `--ulimit` setting or the pod spec instead, a different knob than either of these.)

If the count is climbing without bound, raising the limit only buys more hours before the same crash: six hours becomes thirty, not indefinitely, since the leak keeps consuming whatever ceiling you set. That case needs the code path from step 4 fixed, not a bigger number.

## What I can't verify from here

I don't have access to your server or code, so I can't confirm your actual `ulimit`/systemd configuration, your nginx keep-alive settings, your Node version, or which specific route or plugin is holding onto a handle. The "Likely sources" list above is ranked by how often each one shows up in this exact combination (Fastify, Node, nginx in front), not confirmed against your code.

Next: run steps 1 and 2 after your next restart, and see what the fd count does over that first hour, flat or climbing.
