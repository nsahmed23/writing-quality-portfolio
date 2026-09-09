A vector clock is a timestamp made of a list of counters, one per process in the system, instead of a single number. That one change buys you something a Lamport timestamp cannot give you: the ability to tell "a caused b" apart from "a and b happened independently."

## Lamport timestamps, briefly

Each process keeps one integer and follows three rules: increment it before each local event; attach it to every message sent; on receiving a message, set the counter to `max(local, received) + 1` before handling the message.

The guarantee runs in one direction only. If a happened before b, then L(a) < L(b). "Happened before" is Lamport's potential-causality relation: either the two events are on the same process in order, or there is a chain of sends and receives linking them. The converse fails. Seeing L(a) < L(b) tells you nothing, because two events that never influenced each other still get different numbers, and nothing in the number says which case you are in.

## Vector clocks

Each process i keeps a vector V of length N, one entry per process, all starting at zero:

- local event: `V[i] += 1`
- send: `V[i] += 1`, then attach a copy of V to the message
- receive of a message carrying W: `V[k] = max(V[k], W[k])` for every k, then `V[i] += 1`

Compare two vectors element-wise. Say V(a) < V(b) when every entry of a is less than or equal to the corresponding entry of b, and at least one is strictly smaller. Then:

- V(a) < V(b): a happened before b
- V(b) < V(a): b happened before a
- neither holds: a and b are **concurrent**, meaning neither could have influenced the other

That third case is the whole point. The relationship is now an if-and-only-if rather than one direction, so incomparable vectors are a positive detection of concurrency, not an absence of information.

## Worked example

Two processes, both starting at [0,0].

P1 does a local event e1, giving [1,0], then sends message m at e2, giving [2,0].
P2 does three local events, f1 [0,1], f2 [0,2], f3 [0,3], then receives m at f4: take the element-wise max of [0,3] and [2,0] to get [2,3], then bump its own entry to [2,4].

The Lamport numbers are e1=1, e2=2, f1=1, f2=2, f3=3, f4=4.

By Lamport, L(e2)=2 < L(f3)=3, which reads as though e2 preceded f3. The vectors say otherwise: [2,0] and [0,3] are incomparable, since 2 > 0 in the first slot but 0 < 3 in the second. They are concurrent, and correctly so, because P2 did f3 with no knowledge of e2. Contrast e1 and f4: [1,0] is less than or equal to [2,4] with at least one strict inequality, so e1 really did happen before f4.

## Choosing between them

Reach for a Lamport timestamp when you need a consistent order and any consistent order will do. Break ties by process ID and you get a deterministic total order over all events that never contradicts causality. That is enough for replicated state machines that must apply operations in the same sequence, for Lamport's mutual exclusion algorithm, and for any log where the ordering only has to be agreed upon rather than true. It costs one integer per event regardless of cluster size.

Reach for a vector clock when correctness depends on knowing whether two events were concurrent. The archetype is conflict detection in a replicated store: two replicas each accept a write to the same key, and you must decide whether one supersedes the other or whether they genuinely conflict and need to be kept as siblings or merged. With Lamport numbers you would pick a winner and silently discard the other write. The same reasoning covers causal delivery (hold a message until its dependencies have arrived), session guarantees such as read-your-writes, and debugging tools that need to show which events actually ran in parallel.

The short test: if arbitrarily picking a winner is fine because any consistent answer works, Lamport is enough. If picking a winner would silently destroy someone's data, you need the vector.

## Costs and limits

Space is the main cost. A vector clock is O(N) integers where N is the number of tracked processes, and it rides on every message and is stored alongside every version of the data. That is fine for a handful of replicas and painful for a large or constantly changing set of clients. The usual responses are to track per-replica rather than per-client (server-side version vectors, as Dynamo-style stores do), use dotted version vectors when clients genuinely need their own entries, use interval tree clocks when membership grows and shrinks, or prune stale entries and accept some false conflicts.

Two accuracy limits are worth knowing before you rely on the output. First, a vector clock only sees causality that flows through the messages it instruments; if two processes coordinate through a side channel such as a shared database, a human, or an uninstrumented RPC, the clock will report concurrency even though one event really did influence the other. Second, "concurrent" means "neither could have affected the other through tracked messages," not "at the same moment." Neither scheme gives you real time, so if you need the actual wall-clock winner you are looking at hybrid logical clocks or a bounded-uncertainty clock like Spanner's TrueTime, which is a different tool with different assumptions.

One naming note, since you will meet both terms: replication literature says "version vector" and distributed-events literature says "vector clock." The mechanism is the same; the difference is whether the entries count events at processes or versions of a replicated object.
