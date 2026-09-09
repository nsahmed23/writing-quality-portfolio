A vector clock is a list of counters, one slot per process in the system, attached to every event and every message. It buys you one thing a Lamport timestamp cannot give you: the ability to look at two events and say "these two are concurrent" (neither influenced the other) instead of just "this number is smaller than that one."

## Lamport timestamps: a single counter

Each process keeps one integer `L`:

1. Increment `L` before each local event.
2. Send the current `L` with every outgoing message.
3. On receiving a message stamped `Lm`, set `L = max(L, Lm) + 1`.

The guarantee is a one-way implication. If `a` happened-before `b` (written `a -> b`, meaning they are on the same process in that order, or a chain of messages connects them), then `L(a) < L(b)`. The converse does not hold, and that is the entire limitation. Seeing `L(a) < L(b)` means either `a` influenced `b`, or the two events are causally unrelated and the counters just happened to land that way. You cannot tell which.

Add the process id as a tiebreak and you get `(L, pid)`, a deterministic total order that every node agrees on and that never contradicts causality. That is genuinely useful, but it is an order imposed on top of the truth, not a description of it.

## Vector clocks: one counter per process

Process `i` keeps an array `V` of length N (one slot per process):

1. On a local event, `V[i]++`.
2. Attach the whole vector to outgoing messages.
3. On receiving vector `W`, take the elementwise max (`V[k] = max(V[k], W[k])` for all k), then `V[i]++`.

Define `V(a) < V(b)` to mean: every component of `V(a)` is less than or equal to the matching component of `V(b)`, and at least one is strictly less. Then:

- `V(a) < V(b)` if and only if `a -> b`
- `V(b) < V(a)` if and only if `b -> a`
- vectors equal: same event
- none of the above: `a` and `b` are **concurrent**

The "if and only if" is what you are paying for. Vector clocks characterize happens-before exactly, so concurrency stops being invisible.

One caveat on the word concurrent: it means no information flowed between the two events, not that they occurred at the same instant of wall-clock time. Happens-before is a partial order over causality, and neither clock knows anything about real time.

## A trace where the difference bites

Three processes A, B, C. Vectors are written `(A,B,C)`.

| event | what happens | Lamport | vector |
|---|---|---|---|
| a1 | A does local work | 1 | (1,0,0) |
| a2 | A sends m1 to B | 2 | (2,0,0) |
| c1, c2, c3 | C does three local events | 1, 2, 3 | (0,0,1), (0,0,2), (0,0,3) |
| b1 | B receives m1 | 3 | (2,1,0) |
| c4 | C sends m2 to B | 4 | (0,0,4) |
| b2 | B receives m2 | 5 | (2,2,4) |

Compare `a2` and `c3`. Lamport says 2 < 3, which reads like `a2` came first. The vectors say `(2,0,0)` versus `(0,0,3)`: the first component goes one way, the third goes the other, so neither dominates. The events are concurrent, and A and C have never heard of each other. Lamport gave you a plausible-looking ordering that corresponds to nothing.

Meanwhile `b2` at `(2,2,4)` dominates both `(2,0,0)` and `(0,0,4)`, correctly recording that B's state now depends on everything A sent and everything C sent.

## The comparison, in code

```go
type VC map[string]uint64 // node id -> counter; missing key reads as 0

type Ord int

const (
    Equal Ord = iota
    Before
    After
    Concurrent
)

func Compare(a, b VC) Ord {
    aLess, bLess := false, false
    for _, k := range unionOfKeys(a, b) {
        if a[k] < b[k] {
            aLess = true
        } else if a[k] > b[k] {
            bLess = true
        }
    }
    switch {
    case aLess && bLess:
        return Concurrent // this is the branch Lamport timestamps cannot produce
    case aLess:
        return Before
    case bLess:
        return After
    default:
        return Equal
    }
}
```

Map lookups returning zero for absent nodes is the right semantics here: a node you have never heard from has contributed nothing.

## Which one to reach for

Use a **Lamport timestamp** when you need a cheap, consistent ordering and any causally-valid order will do. Distributed mutual exclusion (Ricart-Agrawala style request queues), assigning monotonic ids, ordering entries in a log where you only need determinism, deciding who wins a lock request. It is one integer, it is O(1) to ship and store, and it never grows with cluster size.

Use a **vector clock** when the question is "did these two writes actually conflict?" rather than "what order should I apply them in?" The canonical case is a multi-master or leaderless replicated store where two clients update the same key without seeing each other. With Lamport timestamps you silently apply last-write-wins and drop one update. With vector clocks you detect the concurrency, surface both siblings, and merge them (application logic, a CRDT, or a user prompt). Dynamo, Riak, and CouchDB revision trees all sit here. The other big use is causal consistency and causal message delivery: hold a message until its dependencies have arrived, which requires knowing what those dependencies are.

The blunt version: any consistent order is fine, use Lamport. Need to detect conflicts or enforce causal delivery, use vectors.

## What vector clocks cost you

Size is the real problem. A vector is O(N) in the number of participating processes, and it has to be stored with each value and shipped with each message. If N is your replica count (a handful of servers) that is fine. If N is your client count it is a disaster, which is why the entries should be keyed by replica, not by client.

Membership churn is the second problem. Nodes join and leave, so entries need adding and eventually garbage collecting, and pruning is where the correctness bugs live. Dynamo capped clock length (10 entries in the paper) and evicted the oldest entry, which can destroy the descendant relationship and produce spurious conflicts. Dotted version vectors are the modern fix for the many-clients-per-replica case; interval tree clocks handle dynamic membership more gracefully.

Terminology worth keeping straight: version vectors track updates to a replicated object per replica, vector clocks track events per process. The math is the same, the granularity differs, and the two names get used interchangeably in practice.

Finally, if what you actually wanted was ordering that roughly tracks wall-clock time (for TTLs, debugging, or human-readable logs) look at hybrid logical clocks. An HLC is scalar-sized, stays close to physical time, and preserves the Lamport property, but it still cannot tell you two events were concurrent. That capability only comes from carrying per-process state.
