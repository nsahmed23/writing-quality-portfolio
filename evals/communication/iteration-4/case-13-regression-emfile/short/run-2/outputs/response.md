Running out of file descriptors doesn't *cause* EMFILE; EMFILE is the name the kernel gives to that condition. When your process asks for a descriptor beyond its `RLIMIT_NOFILE` soft limit, the syscall fails with errno 24, and Node surfaces it as `Error: EMFILE: too many open files`. There's no intermediate mechanism to explain between the two. The question worth answering is what's consuming descriptors in your process, and the ~6 hour pattern narrows that considerably.

(Related error, worth telling apart: `ENFILE`, "too many open files in system", means the whole machine ran out. If you see that one instead, look at `/proc/sys/fs/file-nr`, not at your service.)

## What counts as a descriptor

Every accepted client socket, every outbound socket (HTTP calls, Postgres, Redis), every open file and log handle, every pipe to a child process, every `fs.watch`/inotify handle, and the epoll instance libuv uses. TLS connections count once, at the socket layer, not twice.

## What the 6-hour interval tells you

A steady climb to a hard ceiling at a roughly fixed *elapsed time* is the signature of a leak, not of legitimate concurrency. Genuine load would put you at the ceiling during your traffic peak and let the count fall back when traffic drops, so the crash would track request volume rather than uptime. I can't confirm this on your box, but a fixed interval strongly suggests something opens a descriptor per request (or per N requests) and never closes it.

## Measure this first

Run these as the service user or with `sudo`; `/proc/<pid>/fd` and `ss -p` hide process detail from other users.

**1. Get the pid and the limit the process actually received.**

```
pid=$(pgrep -f 'node.*your-app' | head -1)
grep 'open files' /proc/$pid/limits
```

`ulimit -n` in your shell is not what the service got. systemd applies its own `LimitNOFILE`; on Ubuntu 22.04 the default is typically 1024 soft and 524288 hard unless the unit overrides it. Node does not raise its own soft limit on Linux.

**2. Compare current usage to that limit.**

```
ls /proc/$pid/fd | wc -l
```

**3. Break the descriptors down by type.** This is the single observation that decides everything below.

```
ls -l /proc/$pid/fd | awk '{print $NF}' | cut -d'[' -f1 | sort | uniq -c | sort -rn | head -20
```

**4. Trend it, so you can tell monotonic growth from a sawtooth.** Start this right after a restart and leave it running an hour or two:

```
while sleep 60; do echo "$(date +%s) $(ls /proc/$pid/fd | wc -l)"; done >> /tmp/fdcount.log
```

A line that only goes up is a leak. A sawtooth that occasionally spikes past the ceiling is real concurrency against a limit that's too low, which is a different fix (step "raise the ceiling" below becomes the actual fix, not a stopgap).

Alongside that, check socket states:

```
ss -tanp | awk -v p="pid=$pid" '$0 ~ p {print $1}' | sort | uniq -c
```

Note that `ss` prints `CLOSE-WAIT` with a hyphen while `netstat` prints `CLOSE_WAIT`. Grepping for the wrong one returns nothing and looks like a clean result.

## Reading the breakdown

These are candidates matched to evidence, not a diagnosis, since I can't see your process.

- **Mostly `socket:` with a growing CLOSE-WAIT pile.** The peer closed and your process never called close. Usual Fastify-app sources: outbound calls whose response bodies are never read or aborted (undici and `fetch` hold the socket until the body is consumed or destroyed), a DB or Redis client constructed per request instead of pooled, or an `http.Agent` with `keepAlive: true` and no `maxSockets` cap.
- **Mostly `socket:` in ESTABLISHED, CLOSE-WAIT flat.** Connections that are alive but never time out. Check Fastify's `connectionTimeout` (0, meaning no limit, in v4), `keepAliveTimeout` (72s), and `requestTimeout`. If nginx has upstream keepalive enabled (`proxy_http_version 1.1`, `proxy_set_header Connection ""`, and a `keepalive N` line in the upstream block), those connections are long-lived by design; in that case you want the app's `keepAliveTimeout` *longer* than nginx's idle timeout, otherwise you trade EMFILE for intermittent 502s.
- **Repeating real file paths.** Streams not closed on error paths (a `createReadStream` whose error handler doesn't destroy it), upload temp files, or a log file held open across rotation. `lsof -p $pid | grep deleted` catches the rotation case, where the old inode is gone but still counted.
- **`anon_inode:[inotify]` growing.** `fs.watch` or chokidar watchers created per request or per reload.
- **`pipe:` growing.** `child_process` spawns whose stdio is never closed.

## Raise the ceiling, and know what that buys

Worth doing regardless, since 1024 is low for a production HTTP server, but be clear about the effect: against a leak it moves the crash from 6 hours to some longer interval, it does not remove it.

```
sudo systemctl edit your-app.service
```

Add:

```
[Service]
LimitNOFILE=65535
```

Then:

```
sudo systemctl daemon-reload
sudo systemctl restart your-app.service
grep 'open files' /proc/$(pgrep -f 'node.*your-app' | head -1)/limits
```

Verify from `/proc`, not from `ulimit`, so you're reading the value the process actually got. If you run under pm2 or Docker rather than a plain unit, the knob is elsewhere (`--ulimit nofile=65535:65535` on `docker run`, or `LimitNOFILE` on the docker daemon's unit, or pm2's launcher environment), and I can't tell from here which applies to you.

## One operational note

At the ceiling the process often can't open anything at all, including a log file, which is why these crashes usually leave no useful tail. Log the count from inside the app on an interval so the postmortem has a curve:

```js
setInterval(() => {
  app.log.info({ fds: fs.readdirSync('/proc/self/fd').length }, 'fd count');
}, 30_000).unref();
```

It counts its own directory handle, so it's off by one, which doesn't matter for a trend.

## What I could not verify

I have no access to your server. I haven't seen your unit file, your Fastify version and server options, your nginx upstream block, or what your handlers do per request, so the section above narrows candidates rather than identifying the leak.

Send back the step 3 breakdown taken twice, once shortly after a restart and once two or three hours in, plus the `open files` line from step 1. Those two snapshots against the limit will identify which subsystem is leaking, and usually point at the call site.
