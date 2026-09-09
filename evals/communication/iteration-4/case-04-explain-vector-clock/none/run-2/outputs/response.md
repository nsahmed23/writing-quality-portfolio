A Lamport timestamp is one counter per process. A vector clock is one counter per process, *per process*: every node carries a vector with a slot for every node in the system. That extra size buys exactly one thing, and it's the thing that matters: a vector clock can tell you two events were **concurrent**. A Lamport timestamp cannot.

## Lamport timestamps and the gap

Each node keeps a single integer `L`:

- On a local event: `L += 1`
- On send: `L += 1`, attach `L` to the message
- On receive of message with `m`: `L = max(L, m) + 1`

The guarantee is one-directional. If `a` happened before `b` (written `a -> b`), then `L(a) < L(b)`. The converse is **not** true. Seeing `L(a) < L(b)` is consistent with "a caused b" and equally consistent with "a and b happened on opposite sides of the cluster with no knowledge of each other."

Since concurrency is precisely what a write conflict *is*, a Lamport timestamp structurally cannot detect one. It gives you a total order that never contradicts causality, but part of that order is invented.

## Vector clocks

Node `i` keeps a vector `V` with one slot per node:

- On a local event: `V[i] += 1`
- On send: attach a copy of `V`
- On receive of `M`: `V[k] = max(V[k], M[k])` for every `k`, then `V[i] += 1`

Compare pointwise:

- `V < W` if `V[k] <= W[k]` for all `k` and `V != W` -> the first event happened before the second
- `W < V` -> the other direction
- Neither -> **concurrent**

And here it is an if-and-only-if: `V(a) < V(b)` exactly when `a -> b`. That biconditional is the whole upgrade over Lamport.

## The example that separates them

Two replicas, A and B, holding the same key.

**Sequential.**

1. A writes `v1`. Clock: `{A:1, B:0}`
2. A replicates to B, B applies it. B's clock: `{A:1, B:1}`
3. B writes `v2`. Clock: `{A:1, B:2}`

`{A:1, B:0} < {A:1, B:2}`, so `v2` supersedes `v1`. Overwriting is safe.

**Concurrent.**

1. A writes `v1` without having heard from B. `{A:1, B:0}`
2. B writes `v2` without having heard from A. `{A:0, B:1}`

Neither dominates: A's slot is higher in the first, B's is higher in the second. The system now *knows* two people edited the same shopping cart at the same time.

Run the same scenario with Lamport timestamps and both writes get `1`. You break the tie by node id, B wins, and A's write vanishes with no signal that anything was lost. That is the classic lost update. The tie-break is deterministic, but determinism is not correctness.

## Pick based on the question you need answered

| Your question | Use |
|---|---|
| "Which of these do I order first?" | Lamport (or a hybrid logical clock) |
| "Are these two actually in conflict?" | Vector clock |

**Reach for Lamport when** you need a total order consistent with causality and nothing more: distributed mutual exclusion (its original purpose), deterministic replay of an event log, monotonically increasing ids. Also when the node count is large or membership churns constantly, since one integer beats an O(N) vector. And when all writes funnel through a single ordered log, nothing can be concurrent, so there is nothing for a vector clock to detect.

**Reach for vector clocks when** any two nodes can independently accept a write to the same piece of state:

- Leaderless or multi-master replication (Dynamo, Riak, Voldemort)
- Causal broadcast, where you buffer a message until its causal dependencies have been delivered
- Anti-entropy and read repair, deciding whether replica X strictly dominates Y or whether they genuinely diverged
- Causal consistency and session guarantees ("read your writes" across replicas)
- Distributed debugging and consistent snapshots

## Costs to know before committing

**Size is O(N), and N is every node that has ever written**, not every node currently alive. If clients get their own slots, the vector grows without bound. Riak's answer was to give slots only to servers and prune by size and age. Pruning can manufacture false conflicts (you see concurrency where there was actually causality), which is the safe direction to fail, but it does mean sibling counts creep up.

**They detect conflicts, they do not resolve them.** You still need a policy: last-write-wins, a merge function (set union, a CRDT), or handing siblings back to the application. A vector clock just guarantees you find out.

**Naming.** "Version vector" is the same math applied per object per replica; "vector clock" usually means per event. The literature uses both loosely.

## Adjacent options worth knowing

- **Hybrid logical clocks (HLC)**: a Lamport clock fused with physical time. One compact value, order consistent with causality, stays within a bound of wall clock. Used for MVCC timestamps in CockroachDB. Same blind spot as Lamport: no concurrency detection.
- **Dotted version vectors**: fix vector-clock imprecision when one server writes on behalf of many clients (Riak 2.0+). They eliminate the false conflicts that pattern otherwise generates.
- **Interval tree clocks**: built for dynamic membership where nodes join and leave, avoiding the fixed-N assumption entirely.

Rule of thumb: start with Lamport or an HLC. Switch to vector clocks the moment two nodes can accept a write to the same state independently and you need to *know* when that happened.
