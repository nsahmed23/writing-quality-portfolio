Because it is really four messages, and only two of them can be merged into one packet.

TCP is full duplex, so opening a connection means opening two independent reliable byte streams, one in each direction. Each direction needs an initial sequence number (ISN) so the receiver knows where that stream starts, and each ISN has to be *reliably* delivered, which by TCP's own rules means acknowledged. That gives four logical events:

1. Client announces its ISN.
2. Server acknowledges the client's ISN.
3. Server announces its ISN.
4. Client acknowledges the server's ISN.

Events 2 and 3 both travel server to client, so they ride in a single packet:

```
client -> server    SYN        seq=x
server -> client    SYN, ACK   seq=y      ack=x+1
client -> server    ACK        seq=x+1    ack=y+1
```

(The SYN flag itself consumes one sequence number, which is why the acknowledgements are `x+1` and `y+1` rather than `x` and `y`.)

You cannot compress it below three, because event 4 is causally after event 3. The client cannot acknowledge a number it has not seen yet, and there is no earlier packet to piggyback that acknowledgement onto. "Three-way" is a packet count, not a message count, and three is the floor for any protocol that wants both directions synchronized before data moves.

## What a two-packet handshake would actually break

Say the server declared the connection open the instant it sent SYN+ACK. Two things go wrong.

**Dead connection attempts come back to life.** Networks duplicate, delay, and reorder packets. A retransmitted SYN can get stuck in a routing loop or a congested queue and pop out minutes later, long after the client gave up. With two packets, the server answers that zombie SYN, allocates buffers, marks the connection established, and hands it to the application. It is now sitting on a half-open connection that no client believes in, and old data segments from that dead connection can arrive and be delivered to the application as if they were fresh. With three packets, the client receives a SYN+ACK for a connection it is not opening, finds no matching entry in `SYN-SENT`, and replies `RST`. The server tears the thing down. Rejecting old duplicate connection initiations is the reason the original TCP spec gives for the handshake existing at all.

Sequence number randomization is the other half of that story. Modern stacks derive the ISN from a keyed hash of the four-tuple plus a clock (RFC 6528) rather than the predictable 4-microsecond counter of the 1981 spec. That keeps a new connection's window far away from an old incarnation's, so stale data cannot land inside it, and it stops an off-path attacker from guessing sequence numbers to inject data.

**Anyone can open a connection from an address they do not own.** The third packet is weak proof that the client actually receives traffic at its claimed source IP. Without it, I forge a SYN from your address, the server opens a connection and starts sending your machine whatever the application produces. That is a reflection and amplification weapon. With three packets, the forger never sees the server's ISN, never sends a valid final ACK, and the server's exposure is capped at one retransmitted SYN+ACK.

## The handshake still does not give either side certainty

Worth being precise about the limit here, because "three packets means both sides know" is the usual oversimplification. There is no packet count that produces mutual certainty over a lossy network; this is the two generals problem. After sending the third packet, the client knows both ISNs were acknowledged, but only *hopes* its ACK arrived. The server does not know anything until that ACK lands.

TCP just accepts the residual uncertainty and cleans up lazily. If the final ACK is lost, the server sits in `SYN-RECEIVED` and retransmits SYN+ACK; meanwhile the client's first data segment carries an ACK in its header and completes the handshake anyway, so the loss is usually invisible. If a peer reboots and loses its connection table, the next segment for that unknown connection draws a `RST`.

The clearest evidence that the third packet is what counts is SYN flooding. Between packets two and three the server has committed real state (a control block per half-open connection), so attackers flood spoofed SYNs to exhaust it. SYN cookies fix this by encoding the connection state into the server's own ISN so nothing is allocated until a valid ACK returns, at the cost of squeezing negotiated options into very few bits.

## Two-packet setup does exist, it just buys the third packet somewhere else

- **TCP Fast Open** (RFC 7413): on a prior connection the server hands the client a cookie; later connections put that cookie plus request data directly in the SYN, and the server can act on it immediately. The cookie replaces the address-validation role of the third packet. It cannot replace the duplicate-rejection role, so the data in a SYN is replayable and should only carry idempotent requests. Middleboxes that drop SYNs carrying payload killed most of its deployment.
- **QUIC** (RFC 9000): folds transport and TLS 1.3 into one round trip, with 0-RTT resumption via session tickets. It still has to solve the same problems explicitly, through Retry tokens for address validation and a hard rule that a server may not send more than three times the bytes it has received from an unvalidated address.

The pattern holds: on genuine first contact, with no shared secret, you cannot get both address validation and old-duplicate rejection for free. Three packets is the price.

## A useful confirmation: closing takes four

Teardown is `FIN`, `ACK`, `FIN`, `ACK`, one FIN per direction because TCP permits a half-close where one side stops sending while the other keeps talking. The middle two often cannot be merged, since the server may still have data to flush after the client's FIN. When it has nothing left, stacks do merge them and you get a three-packet close. Same four logical events in both directions, same piggybacking rule, different outcome only because the merge is not always legal.
