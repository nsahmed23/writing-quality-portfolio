JWT (JSON Web Token) authentication works by having the server issue a signed, self-contained token that the client presents on every request, instead of the server keeping a record of who's logged in.

## The flow

1. The user logs in with a username and password (or some other credential).
2. The server verifies the credentials, then builds a token containing claims about the user, things like a user ID, roles, and an expiration time, and signs it with a secret key (HMAC) or a private key (RSA/ECDSA).
3. The server sends that token to the client. The client stores it (in memory, localStorage, or a cookie) and attaches it to future requests, typically in an `Authorization: Bearer <token>` header.
4. On each request, the server recomputes the signature and compares it to the one on the token. If it matches and the token hasn't expired, the server trusts the claims inside it and treats the request as authenticated. No database lookup, no session store.

## Why it's called stateless

A JWT is three base64url-encoded pieces joined by dots: `header.payload.signature`. The header names the signing algorithm, the payload carries the claims (user ID, roles, expiration, etc.) in plain view, base64-encoded but not encrypted, so anyone can read it, and the signature is a cryptographic hash over the first two parts that only someone holding the secret or private key could have produced. Since everything the server needs to validate a request is already inside the token, verification is just a computation: recompute the signature, compare it, check the expiration. Nothing has to be remembered between requests.

Compare that to classic session-based auth, where login creates a session ID that the server stores in memory, Redis, or a database, and every request looks that ID up to figure out who's making it. That lookup is state. JWTs remove it, which is why they scale nicely across a cluster: any server can verify a token on its own, with no shared session store and no round trip to a database.

## Can you actually log someone out with a JWT?

Yes, that part is true, in the pure version of the model. Once a JWT is issued, the server has no list of "currently valid tokens" to cross an entry off of. Deleting the token on the client only logs out that one client; the token itself keeps working until it expires, and anyone else with a copy (a compromised device, a proxy that logged it, a stolen laptop) can keep using it right up to the `exp` timestamp, logout button or not.

But "you can't log out with JWTs" oversells a real limitation as if it were unsolvable, and in practice almost nobody ships pure stateless JWTs for anything that matters. The common fixes all trade a bit of statelessness back for control:

- Keep the JWT short-lived (minutes) and pair it with a longer-lived refresh token stored server-side. Logging out revokes the refresh token; the access token dies on its own shortly after, which shrinks the exposure window instead of closing it instantly.
- Keep a denylist of revoked token IDs (the `jti` claim), checked on each request until the token would have expired anyway. This works, but it's a database lookup on every request, exactly the state JWTs were meant to avoid.
- Store a single "valid since" timestamp per user and reject any token issued before it. Logging out, or changing a password, bumps the timestamp. It's one cheap lookup instead of a full session table, a middle ground between the two options above.
- For places where instant revocation genuinely matters, like banking or admin tools, use server-side sessions instead of JWTs, and accept the lookup cost outright.

So the accurate version: a pure JWT can't be individually revoked before it expires, that's real. But production systems handle it by reintroducing a small, deliberate amount of state, not by discovering JWTs are unusable.
