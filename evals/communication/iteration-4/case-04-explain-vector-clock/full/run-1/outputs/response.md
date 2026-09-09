A vector clock is one counter per process, carried around as a list, updated so that comparing two lists tells you whether one event definitely happened before the other or whether the two are genuinely independent. A Lamport timestamp is a single counter: it guarantees that causes get smaller numbers than their effects, but a smaller number does not mean a cause. Reach for a vector clock the moment your code needs to distinguish "B overwrote A" from "A and B diverged."

## Lamport timestamps

Each process keeps one integer, starting at 0.

1. Increment it before every local event.
2. When sending a message, increment it and attach the value to the message.
3. When receiving a message carrying value `T`, set your counter to `max(yours, T) + 1`.

"Happened before" (written `a → b`) means `a` could have influenced `b`: the two are on the same process with `a` first, or `a` is a send and `b` is the matching receive, or there is a chain of those links between them.

The guarantee is one-directional: if `a → b`, then `C(a) < C(b)`. Effects always carry bigger numbers than their causes.

What is missing is the converse. `C(a) < C(b)` does not mean `a → b`. It only means `b` is not a cause of `a`. Two events on machines that have never exchanged a message still land on some pair of numbers, and one of them will be smaller. A single integer cannot record who knew what; it flattens the whole system to one dimension, and that flattening is lossy.

## Vector clocks

Each process keeps a list with one slot per process. Process `i` owns slot `i`.

1. Increment your own slot before every local event.
2. When sending, increment your own slot and attach the entire vector.
3. When receiving vector `T`, take the element-wise maximum of yours and `T`, then increment your own slot.

To compare two vectors, `V(a) < V(b)` when every slot in `V(a)` is less than or equal to the matching slot in `V(b)`, and at least one slot is strictly less.

Now the relation runs both ways: `V(a) < V(b)` if and only if `a → b`. Because the "if and only if" holds, a comparison has three outcomes instead of two: `a` before `b`, `b` before `a`, or neither, which means concurrent. That third outcome is the entire reason vector clocks exist.

## The trace where they differ

Three processes; vectors written `[A, B, C]`.

| # | event | Lamport | vector |
|---|---|---|---|
| 1 | A writes locally | 1 | `[1,0,0]` |
| 2 | A sends `m` to B | 2 | `[2,0,0]` |
| 3 | C writes locally | 1 | `[0,0,1]` |
| 4 | C writes locally again | 2 | `[0,0,2]` |
| 5 | B receives `m` | 3 | `[2,1,0]` |

Compare event 4 (C's second write) against event 5 (B's receive). C sits at 2, B at 3. Sort by Lamport timestamp and C's write comes first, which reads as "C's write already happened, so B's state is the newer one." It is not. C and B have never communicated at all.

The vectors say so directly. `[0,0,2]` against `[2,1,0]`: C's slot is higher in the first, A's and B's slots are higher in the second, so neither is less than the other. Concurrent.

Lamport is not lying in that comparison. It never promised that 2 < 3 implies causality. The damage comes from code that treats "smaller timestamp" as "older, safe to discard," which is exactly what last-write-wins does. The result is a silently lost write.

## When a Lamport timestamp is enough

Use one when you need some consistent order and never need to ask whether two events are independent:

1. Sequencing entries in a log or audit trail where any deterministic order is acceptable (break ties between equal timestamps by process id to get a strict total order).
2. Classic algorithms built on total order: Lamport's distributed mutual exclusion, request queues, fencing tokens.
3. Last-write-wins conflict resolution, where you have already accepted that one write disappears. LWW is defined by picking a winner, not by noticing a conflict.
4. Space-constrained paths: one integer per event, whatever the cluster size.
5. Open or anonymous membership, where you can never enumerate the participants.

## When you need a vector clock

Use one when the answer to "are these two versions in conflict?" changes what the code does:

1. Replicated stores that must surface siblings rather than drop a write, so the application or the user can merge them (the Dynamo and Riak lineage).
2. Causal delivery: hold an incoming update until everything it depends on has arrived. That requires knowing exactly which updates the sender had already seen, which a scalar cannot express.
3. Session guarantees across replicas, read-your-writes and monotonic reads: the client carries a vector, and a replica serves the read only once its own vector dominates.
4. Consistent snapshots and distributed debugging: deciding which events could possibly have influenced a failure and which are unrelated noise.
5. Merge logic that must separate "newer version of the same lineage" from "divergent branch."

## What vector clocks cost

Size is O(N) per version, where N is the number of independent writers, not the number of machines. This is the failure mode that shows up in production. If clients are the actors, N is your user population and the vectors grow without bound. The standard fix is to make server-side replicas the actors and keep client identity out of the vector; Riak is the best-known example, since early versions let clients become vector entries and later moved actor identity server-side.

You also need stable identities and a plan for retiring actors that are gone for good. Trimming entries to bound the size is tempting and unsafe. `[A:5, B:3]` dominates `[A:5, B:2]`, so the first event happened after the second. Drop B's entry from the first and it reads as `[A:5, B:0]`, which is now dominated by `[A:5, B:2]`. The comparison flipped, and you are back to overwriting a newer version with an older one. Bound the size by controlling who counts as an actor, not by deleting entries after the fact.

One more limit worth knowing before it surprises you: a vector clock yields a partial order, not a total one. If you also need a single ordering for display or for a deterministic tie-break, you still have to choose one. The vector's job is to tell you when that choice is arbitrary.

## The test

Does anything in your system behave differently when two updates are concurrent rather than ordered? If yes, use a vector clock and pay the O(N). If no, use a Lamport timestamp and take the single integer.

Separately: if you want timestamps that also track wall-clock time (for TTLs, retention windows, or human-readable ordering), hybrid logical clocks are Lamport clocks with a physical-time component attached, used by CockroachDB and MongoDB among others. They still cannot detect concurrency. Want me to cover those?
