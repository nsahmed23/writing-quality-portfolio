A JWT (JSON Web Token) is a signed piece of text a server hands a client at login, which the client then sends back on every later request to prove who it is.

## How it works

The token is three parts joined by dots: `header.payload.signature`.

- The header names the signing algorithm.
- The payload holds claims: statements about the user, such as their ID, role, and an expiration time (`exp`). This part is only encoded, not encrypted, so anyone holding the token can read it.
- The signature is a cryptographic check computed over the header and payload, using either a secret key both sides share, or a private key on the server that pairs with a public key others can use to verify. Change one character of the payload and the signature stops matching, which is what makes the token tamper evident.

The flow:

1. User logs in with a password; the server checks it.
2. Server builds a token containing claims about that user, signs it, and sends it to the client.
3. Client stores the token and attaches it to later requests, typically in an `Authorization: Bearer <token>` header.
4. Server checks the signature and the expiration on each request; if both are good, it trusts the claims inside directly, with no further lookup.

## Why people call it "stateless"

Compare this to the older session-cookie model: at login, the server creates a session record in its own storage (memory, Redis, a database) and hands the client only a random-looking ID that carries no information by itself. On every request, the server looks that ID up in its storage to find out who is asking. The server is holding state on the user's behalf.

A JWT moves that information into the token itself, protected by the signature instead of by a lookup. The server stores nothing about the login; it just re-verifies the signature each time a request arrives. Any server holding the verification key can check the token on its own, without querying a shared session store. That is the specific meaning of "stateless" here: the server needs no session storage to validate a request. It does not mean the token is empty, or that the server remembers nothing useful; it means validation does not depend on server-side memory of that particular login.

## Can you actually log someone out?

Partly true, and there is a real mechanism behind it, but "can't" overstates it.

What is true: in the plain version of this design (check the signature and the expiration, nothing else), the server keeps no record of the token, so there is nothing on the server to mark as revoked. Deleting the token on the client only removes that one copy. If a copy exists anywhere else, cached in a browser, sitting in a log, taken by an attacker, the server keeps accepting it until it expires, because expiration is the only exit the token itself carries.

What is false: that this is a fixed, unfixable property of JWTs as a technology. Three fixes people actually use:

1. Keep the JWT short-lived (minutes) and pair it with a separate refresh token stored server-side; logout revokes the refresh token, so no new JWT can be issued, and the last one already out there expires within minutes.
2. Keep a list of revoked token IDs in a fast store like Redis, checked on every request before the token is trusted; this gives immediate logout.
3. Store a "valid since" timestamp per user and reject any token issued before it; this is what powers a "log out of all devices" button.

Each of these adds back a server-side check that the original design was built to avoid. So the precise version of the claim is narrower than what usually gets repeated: a bare JWT, verified by signature and expiration alone, cannot be revoked early. JWT-based auth as a whole can support logout; it just has to give up some of the statelessness to do it. Which of the three fixes is worth using depends on how long an exposure window you can accept between someone clicking logout and the token actually stopping.