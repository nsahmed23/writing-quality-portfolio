## How JWT auth works

A JWT (JSON Web Token) is a compact, signed string that carries a set of claims (key-value facts about the user, such as their ID, roles, and an expiration time). The flow:

1. The user logs in with a username and password.
2. The server verifies the credentials, then builds a JWT: it packages the claims into a payload and signs the whole thing, either with a shared secret key (HMAC, labeled `HS256`) or a private/public key pair (RSA or ECDSA, labeled `RS256` or `ES256`). The result is three base64url-encoded parts joined by dots: `header.payload.signature`.
3. The server sends that token to the client, which stores it (a cookie, `localStorage`, wherever) and attaches it to every later request, usually in an `Authorization: Bearer <token>` header (the standard way to hand a server a token instead of a password).
4. On each request, the server recomputes the signature from the payload and its key, and compares it to the signature on the token. If they match, and the token hasn't expired (checked via the `exp` claim), the server trusts the claims inside it; no further lookup is needed.

One detail that's easy to miss: the payload is encoded, not encrypted. Anyone holding the token can decode and read the claims (base64 is not a cipher); the signature only proves the claims haven't been tampered with since the server issued them. Don't put secrets in a JWT payload.

## Why people call it stateless

Step 4 above is the whole reason for the label. To validate a request, the server only needs the key it signs with and math; it never has to ask a database or session store whether this is still a valid session. Every fact the server needs (who the user is, what they're allowed to do, when this expires) travels inside the token itself.

Compare that to classic session-based auth: login generates a random session ID, the server stores the session's data in memory, a database, or Redis, and hands the client that ID as a cookie. Every request after that requires a lookup: does this session ID exist, and what's attached to it? The server is holding state on behalf of every logged-in user. That lookup is also what makes instant, precise logout trivial: delete the row, and the session is dead.

JWTs trade that lookup away. That's genuinely useful: any server in a cluster can verify a token with no shared session store and no session affinity, which is why JWTs are common in distributed and microservice systems. But the trade means the server has also given up its per-request check for whether this specific token is still good, which is exactly what logout needs.

## Is it true you can't log someone out?

Partly, and the part that's true is the important part.

For a pure JWT setup, meaning the server only checks the signature and the expiration, the claim is accurate: there is no revoke operation. The server never recorded that it issued this token, so it has nothing to delete. If a client-side logout just clears the token from local storage, the token itself is still perfectly valid, and anyone else holding a copy (stolen via XSS, a browser history sync, a logged request, a shared machine) can keep using it until it expires on its own. That's the mechanism behind the folklore, not a myth.

Where the claim overreaches is treating this as an unsolvable limit of JWTs as a technology. It's a solved problem in practice; it just costs you some of the statelessness:

- **Short-lived access tokens plus a server-side refresh token.** Issue JWTs with a short life (5 to 15 minutes), paired with a separate refresh token that the server does store (database or Redis) and can revoke. Logout revokes the refresh token; the already-issued access token still works until it expires, so this bounds the damage to minutes rather than eliminating it.
- **A revocation list.** Store revoked token IDs (the `jti` claim) in a fast store like Redis and check it on every request. This gives real, immediate logout, but it puts a lookup back on every request, the same cost that statelessness was avoiding.
- **A "valid since" timestamp per user.** Store one timestamp per user (e.g. `valid_after`) in the database; set it to now on logout or password change; reject any token issued before it. Cheaper than a growing revocation list, but still needs a lookup or a cached copy of that field.
- **Rotate the signing key.** Invalidates every token for every user at once: a blunt, global logout switch, not one for logging out a single person.

So the narrow claim, that a bare JWT checking only signature and expiry has no logout, is correct. The broad claim, that you can't log someone out with JWTs at all, is not; teams solve this routinely by deliberately giving back a slice of the statelessness that made JWTs attractive in the first place.
