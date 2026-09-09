EMFILE isn't a separate effect of running out of file descriptors; it's the kernel's direct report of that exact condition. Every socket, open file, and pipe your process holds occupies one slot in its file descriptor table, a list the kernel caps per process (what `ulimit -n` shows you, though the number actually enforced on a running process is more reliably read from `/proc/<PID>/limits`). When Fastify's server tries to `accept()` a new connection from nginx, or your code tries to open a file or an outbound socket, and that table is already full, the syscall fails and Node wraps the failure as `Error: EMFILE: too many open files`. (The system-wide version of this, when the whole machine's descriptor table fills up rather than just your process's allowance, is a different error, `ENFILE`; what you're seeing is the per-process one.)

So the real question underneath yours is what's holding descriptors instead of releasing them. A fixed cap that gets hit under a fixed load fails immediately and stays failed. A cap you only hit after about six hours under load is the signature of something leaking at a roughly constant rate until it eats the whole allowance.

## Why six hours, not immediately

Two different mechanisms produce a fixed time-to-crash, and they point in different directions:

- If the six-hour mark tracks request volume (busier stretches crash sooner), something leaks a small fixed number of descriptors per request. At a steady request rate, allowance divided by leak-per-request gives a roughly constant time to crash, which is what you're seeing.
- If six hours holds regardless of traffic, look for something on a schedule around that interval instead: a cron job, a health check, a cache warm, anything that opens resources on a timer without closing the previous round.

I can't tell which from the message alone. The checks below will.

## Find out what's actually leaking

1. Get the PID: `pgrep -f node` (or your process manager's own status command, e.g. `systemctl status <service>`, `pm2 list`).
2. Read the limit actually applied to that process, not just your shell's `ulimit -n`, which may not match it: `cat /proc/<PID>/limits | grep "open files"`.
3. Watch the count climb: `watch -n 5 'ls /proc/<PID>/fd | wc -l'`. Let it run under normal traffic for 15 to 30 minutes. A steady climb confirms a leak; a number that rises and falls with traffic does not.
4. See what kind of descriptor is piling up: `sudo ls -l /proc/<PID>/fd` lists what each one points to (socket, regular file, pipe). For sockets specifically, `sudo ss -tnp state close-wait` shows connections where the remote side closed but your process never closed its own end, one of the most common leak patterns for a server sitting behind a proxy.
5. On the Node side, the undocumented but reliable `process._getActiveHandles()`, or the `wtfnode` package, will list what libuv handles are actually still open.

## Likely causes for this stack

I haven't seen your code, so treat this as the ranked set of usual suspects for this exact symptom, not a diagnosis; step 4 above tells you which of these to chase.

1. An outbound call (`fetch`/undici, `axios`) whose response body is never fully read or cancelled on an error or early-return path. The keep-alive pool holds the socket open expecting to reuse it. Signature: sockets in `CLOSE_WAIT` or `ESTABLISHED` toward the downstream service's port.
2. A database client created fresh per request instead of one shared pool, or a pool client never released back with `.release()` in a `finally` block. Signature: a climbing count of sockets to the database's port.
3. A route handler with no timeout on a slow downstream call. The request's socket to nginx sits open until nginx's own `proxy_read_timeout` gives up on it; if Node never notices the client is gone, that socket lingers on Node's side. Signature: `CLOSE_WAIT` on the nginx-facing connections.
4. `fs.createReadStream` or `createWriteStream` (uploads, downloads, log writes) without an `error` handler, so a client disconnecting mid-transfer leaves the stream, and its descriptor, open indefinitely. Signature: regular-file descriptors accumulating, often pointing into a temp or upload directory.
5. Multipart file parts (`@fastify/multipart` or similar) started but not fully drained when a request gets rejected mid-upload. Same signature as #4.

## Stopgap vs. the actual fix

Raising the limit buys time; it does not fix a leak, only moves the six-hour mark to a later one at the same leak rate. If the process runs under systemd, add to the unit:

```
[Service]
LimitNOFILE=65536
Restart=always
```

then `sudo systemctl daemon-reload && sudo systemctl restart <service>`. `Restart=always` limits the damage of the next crash while you're still hunting the leak. Under pm2 instead, the equivalent is PAM limits (per-user caps set in `/etc/security/limits.conf`) for the user pm2 runs as; under Docker, it's `--ulimit nofile=65536:65536` on the container.

Next: get the PID and start the step-3 `watch` command now. A climbing number over the next 15 to 30 minutes confirms the leak and tells you, from step 4, whether you're chasing sockets or files before you dig into the code.
