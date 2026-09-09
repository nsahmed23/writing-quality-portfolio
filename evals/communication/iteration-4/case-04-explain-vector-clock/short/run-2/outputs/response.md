A vector clock is a logical clock (a counter that orders events by cause and effect rather than by wall-clock time) in which each process carries not one number but one number per process. That extra width buys exactly one thing a Lamport timestamp cannot give you: the ability to tell that two events are *concurrent*, meaning neither could have influenced the other.

**What Lamport gives you, and where it stops.** Each process keeps a single integer. Bump it on every local event, send it with every message, and on receipt set it to `max(local, received) + 1`. The guarantee runs one way only: if a happened before b, then `L(a) < L(b)`. The converse fails. Seeing `L(a) = 4` on node 1 and `L(b) = 7` on node 2 tells you nothing about whether b was influenced by a; the two counters may simply have drifted apart. So Lamport can produce a consistent total order (break ties by node id), but it cannot distinguish "b came after a" from "a and b never knew about each other."

**What a vector clock does.** Process i keeps a map `V` from process id to counter, where `V[i]` counts i's own events and `V[j]` is the highest event count from j that i has heard about.

- local event: `V[i] += 1`
- send: `V[i] += 1`, then attach a copy of `V`
- receive `W`: `V = elementwise max(V, W)`, then `V[i] += 1`

Compare two vectors elementwise. If every entry of `V(a)` is less than or equal to `V(b)` and at least one is strictly smaller, then a happened before b. If each vector has an entry the other beats, the events are concurrent. That is a biconditional, so the clock *characterizes* causality instead of merely respecting it.

**The case that decides which one you want.** Two clients write the same key through different replicas. With vector clocks the versions are `[A:1]` and `[B:1]`; neither dominates, so the store can keep both as siblings or hand the conflict up to the application. With Lamport the versions are 4 and 7, 7 looks newer, and a write that nobody ever read disappears silently. If losing that write is unacceptable, you need vector clocks.

Reach for a vector clock when you must detect write-write conflicts on replicated data instead of silently resolving them (Dynamo-style stores, Riak, CRDT metadata); when you need causal delivery or causal consistency, holding a message until its dependencies have arrived; when anti-entropy needs to ask "does that replica's state already subsume mine?"; or when you are reading a distributed trace and the real question is "were these two things actually parallel?"

Lamport is enough when you only need *some* order that everyone agrees on and never need to know whether that order reflects reality: mutual-exclusion request queues, sequencing log entries where any consistent order is acceptable, generating monotonic ids. It costs one integer per message instead of N, which is not nothing.

**Costs and limits.** A vector clock is O(N) in the number of distinct writing actors, carried on every message and stored alongside every version. That is fine when the actors are a fixed handful of replicas and bad when the actors are clients, which is why Riak moved to dotted version vectors. Pruning old entries to bound the size is a correctness hazard, because a pruned entry can turn a genuine conflict into a false ordering. Detection is also not resolution: the clock tells you a conflict exists, and you still need a merge function, a CRDT, or a human to settle it. And neither clock has any relationship to real time, so neither answers "which of these happened earlier by the wall clock"; hybrid logical clocks (CockroachDB, MongoDB) are the usual compromise when you want causality and near-physical timestamps in a single value.

One terminology note, since the literature is loose here: "version vector" normally means this same mechanism applied to per-object replica versions, while "vector clock" means it applied to process events. The comparison rule is identical.
