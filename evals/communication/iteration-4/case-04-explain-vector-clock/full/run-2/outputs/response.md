A vector clock is a list of counters, one per node, attached to every message and every stored version. It answers the question a Lamport timestamp cannot: were these two events concurrent, or did one genuinely happen before the other? Use a Lamport timestamp when you only need *some* consistent order that every node agrees on. Use a vector clock when guessing the order wrong would silently lose data, which in practice means conflict detection between replicas.

Both are logical clocks: they order events by causality, not by time. Neither one tells you anything about seconds, and neither is comparable to a wall clock.

## The relation they are both trying to capture

"A happened before B" (written A → B) means one of three things: A and B happened on the same node and A came first; A is the sending of a message and B is the receipt of that same message; or a chain of those two cases connects them. If neither A → B nor B → A, the events are **concurrent**: nothing in the system's history links them, and no observer can say which came first.

Concurrent does not mean simultaneous. It means causally independent.

## Lamport timestamps: one counter

Each node keeps a single integer, starting at 0:

1. Before a local event: `C = C + 1`
2. On send: `C = C + 1`, and put `C` in the message
3. On receipt of a message stamped `t`: `C = max(C, t) + 1`

The guarantee is one-directional: if A → B, then `L(A) < L(B)`.

The converse does not hold, and that is the whole point. `L(A) < L(B)` tells you nothing about whether A influenced B. B's counter may simply have run ahead through unrelated local work. A Lamport timestamp compresses a partial order (some pairs ordered, many pairs not) into a single number, and a single number can only express a total order, so the "these two are unrelated" information is destroyed on the way in.

Pair the counter with the node ID (`(4, node-a)` versus `(4, node-b)`) and you get a deterministic total order with no ties. It is an arbitrary order, but every node computes the same one, which is often exactly what you need.

## Vector clocks: one counter per node

Node *i* keeps a vector `V` with one entry per node, all starting at zero:

1. Local event: `V[i] += 1`
2. Send: `V[i] += 1`, then attach all of `V` to the message
3. Receipt of a vector `W`: `V[k] = max(V[k], W[k])` for every `k`, then `V[i] += 1`

Compare two vectors entry by entry. `V < W` when every entry of `V` is less than or equal to the matching entry of `W` and at least one is strictly less. If neither vector dominates the other, the two events are concurrent.

The guarantee is now two-directional: `V(A) < V(B)` **if and only if** A → B. That second half is what the extra space buys. The vector keeps the partial order intact instead of flattening it.

## The example that separates them

Two replicas of a shopping cart. Alice's request lands on node A, Bob's on node B, and neither node has heard from the other yet.

- Node A writes `cart = {book}`. Its Lamport counter happens to be at 4.
- Node B writes `cart = {shoes}`. Its counter is at 9, because B has been serving unrelated traffic all morning.

Under last-writer-wins on Lamport timestamps, 4 < 9, so `{shoes}` wins and the book is dropped. A customer lost an item they added, and no error surfaced anywhere. The number 9 never meant "B had seen A's write"; it only meant "B has been busy."

Under vector clocks, A's write carries `{A:4, B:0}` and B's carries `{A:0, B:9}`. A's is larger in the A slot, B's is larger in the B slot, so neither dominates. The store now knows the two writes are concurrent and can either keep both versions as siblings for the client to resolve, or merge them at the application level into `{book, shoes}`. That is the behavior Amazon's Dynamo paper describes and that Riak inherited.

The causal case is the useful contrast. If B had received A's write before writing, B's vector would read `{A:4, B:10}`, which dominates `{A:4, B:0}` in every slot. Last-writer-wins is safe there, because B demonstrably knew about A's version when it wrote.

## When to pick which

Lamport, when a consistent but arbitrary order is enough:

- Ordering entries in a log, or sequencing requests into a queue (Lamport's original 1978 mutual-exclusion algorithm is exactly this).
- Generating monotonically increasing IDs that never contradict causality.
- Anywhere the cost of the wrong order is a slightly odd interleaving rather than a lost write.

Vector, when concurrency itself is what you need to detect:

- Conflict detection between replicas of the same key (Dynamo, Riak, Voldemort).
- Causal delivery: hold a received message until everything it causally depends on has been delivered.
- Debugging and tracing, where the question is whether two log lines could have influenced each other.

## What vector clocks cost

Space and bookkeeping, both proportional to the number of participants.

Every message and every stored version carries N counters. That is fine for a handful of storage nodes and untenable for a million clients, so real systems key the vector by replica rather than by client (a **version vector**, mechanically the same idea applied to versions of a data item rather than to process events). Dynamo capped its clock length and truncated the oldest entries, trading correctness for size: truncation can report two writes as concurrent when one really did precede the other. That is the survivable direction of error, since a false conflict costs a merge while a missed conflict costs data. Dotted version vectors were designed to control the sibling explosion this produces.

Membership churn is the second problem. Entries accumulate for nodes that are long gone, and pruning them without erasing a causal relationship something still depends on is a recurring source of subtle bugs.

## If what you actually want is time

Neither clock is comparable to wall time, so neither answers "which of these two writes was more recent?" in the human sense. If that is the real requirement, look at hybrid logical clocks, which combine a physical timestamp with a Lamport counter so values stay close to real time while still never contradicting causality. CockroachDB and MongoDB both use them.
