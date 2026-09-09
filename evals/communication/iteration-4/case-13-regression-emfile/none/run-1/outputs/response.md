Running out of file descriptors doesn't *cause* `EMFILE`. `EMFILE` **is** running out of file descriptors. The kernel returns that errno from `open()`, `accept()`, `socket()`, or `pipe()` when your process already holds `RLIMIT_NOFILE` descriptors and asks for one more. A file descriptor is the small integer the kernel hands back for every open file, socket, pipe, epoll instance, inotify watch, and timer, so despite the wording "too many open files" covers sockets, which is what usually bites a web server. The message restates the condition; it doesn't explain it.

The question worth answering is what is holding descriptors open and why the count only goes up. Your "dies after ~6 hours under load" already narrows it. A limit that is merely too low fails fast at peak concurrency and recovers when traffic drops. A count that climbs steadily for six hours until it hits a wall is a leak: something gets opened per request and never closed on at least one code path. Raising the limit converts a 6 hour crash into a 12 hour crash.

That also explains why the crash log is useless here. Whichever call happens to need the descriptor that crosses the limit is the one that throws, so the stack trace names the victim, not the culprit. You have to watch the curve instead.

## 1. Confirm it's a leak

Get the pid and log the count on an interval:

```bash
PID=$(systemctl show -p MainPID --value your-service)   # or: pgrep -f 'node.*server'
while sleep 60; do echo "$(date +%s) $(ls /proc/$PID/fd | wc -l)"; done >> /tmp/fdcount.log
```

(Run as root or as the service user, otherwise `/proc/$PID/fd` is not readable.)

Monotonic rise that never falls back during a traffic lull is a leak. A count that tracks concurrency up and down and just peaks too high is a genuine limit problem, which is a different fix.

## 2. Find which class of descriptor is growing

This one command usually names the bug's neighborhood. It normalizes the numeric parts so descriptors group by kind:

```bash
ls -l /proc/$PID/fd | awk '{print $NF}' | sed -E 's/[0-9]+/N/g' | sort | uniq -c | sort -rn
```

Run it twice an hour apart and diff. Whatever bucket grew is the leak.

**`socket:[N]` growing.** Cross-reference the TCP state:

```bash
ss -tanp | grep "pid=$PID" | awk '{print $1}' | sort | uniq -c
```

A pile of `CLOSE_WAIT` (remote closed, your side never did) means outbound connections you opened and abandoned. The classic cause is an HTTP response whose body you never read: `undici`, `fetch`, and `node-fetch` all hold the socket until the body is consumed or dumped, so an early `return` after checking `res.status` leaks one socket per request. A pile of `ESTABLISHED` to one remote host and port means a connection pool or agent constructed per request instead of once at boot (Postgres client, Redis client, `new Agent()`, `new Pool()`). If the growing sockets are *inbound* instead (local address = your Fastify port, peer = nginx on 127.0.0.1), check the `keepAliveTimeout` you pass to Fastify; `0` disables the idle timeout entirely and idle sockets then live forever.

Heavy `TIME_WAIT` is a red herring for this symptom. Those sockets are already closed from your process's point of view and cost you no descriptor; they cause ephemeral port exhaustion (`EADDRNOTAVAIL`), not `EMFILE`.

**Real file paths growing** (`/tmp/...`, `/var/log/...`, upload dirs). A `fs.createReadStream` that is created but never read to end and never `.destroy()`ed keeps its descriptor. Same for `fs.promises.open` handles on an error path. Multipart upload temp files are a frequent offender when the `unlink`/`close` only lives in the success branch. Client disconnects mid-download are the usual trigger, which fits "under load."

**`anon_inode:[eventpoll]` or `pipe:[N]` growing.** You're constructing something per request that owns event loop resources: a `Worker`, a child process, a watcher, a new client library instance.

**`anon_inode:inotify` growing.** `fs.watch` or chokidar left running, often from a config-reload helper.

## 3. Get the same signal from inside the process

`/proc` gives you the type; Node can give you the handle mix, which narrows it further:

```js
app.get('/_handles', async () => {
  const byType = {};
  for (const h of process.report.getReport().libuv) {
    byType[h.type] = (byType[h.type] ?? 0) + 1;
  }
  return byType;
});
```

Scrape that once a minute and bind it to localhost or put it behind auth. `getReport()` walks the whole loop, so it is fine at 1/min and not fine per request. Growth in `tcp` versus `fs_event` versus `pipe` here lines up with the `/proc` buckets and confirms the leak is yours and not something below Node.

## 4. Raise the limit, but as a shock absorber, not the fix

On Ubuntu 22.04 the two places people usually edit do nothing for a systemd service. `ulimit -n` in your shell applies to your shell, and `/etc/security/limits.conf` is applied by PAM, which systemd services don't go through. Check the value that is actually in effect:

```bash
grep 'open files' /proc/$PID/limits
```

Set it on the unit with `systemctl edit your-service`:

```ini
[Service]
LimitNOFILE=65535
```

Then `systemctl daemon-reload && systemctl restart your-service`. Under Docker it's `--ulimit nofile=65535:65535` (or the compose equivalent); under PM2 it's inherited from whatever started the PM2 daemon, so restarting PM2 itself is required for a change to take.

nginx has its own separate budget (`worker_rlimit_nofile`). If nginx were the one starving you'd see "too many open files" in `/var/log/nginx/error.log` and 5xx served by nginx, not a dying Node process, so your symptom points at the app.

## What I could not verify

I can't see your server, so none of this is confirmed against your system. I don't know your effective `LimitNOFILE`, your fd curve, your Fastify plugin list, whether the app makes outbound HTTP calls, or what the `/proc/$PID/fd` breakdown looks like. What I'm confident about is the reasoning from the symptom shape: a steady six hour climb under load is a leak, not an undersized limit, and step 2 identifies which kind within one load cycle. The bucket counts and the `ss` state histogram are the two outputs worth capturing before changing anything.
