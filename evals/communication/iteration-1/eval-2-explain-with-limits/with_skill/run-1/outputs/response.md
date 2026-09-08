## The basic flow

1. The user logs in with credentials (a password, typically) against a login endpoint, and the server checks them.
2. If they're valid, the server creates a JWT (JSON Web Token): a compact, signed string with three parts separated by dots, `header.payload.signature`. The payload carries claims, facts about the user such as an ID, a role, and an expiration time. The signature comes from hashing the header and payload with a secret or private key, so anyone holding the matching key can tell if the token was altered after it was issued.
3. The server returns the token to the client, which stores it, commonly in an HTTP-only cookie (a cookie JavaScript in the browser can't read, which blocks some theft attempts) or in browser storage (simpler to use, more exposed to those same attempts).
4. On every later request, the client attaches the token, typically as an `Authorization: Bearer <token>` header.
5. The server verifies the signature and checks the expiration claim (`exp`). If both pass, it trusts the claims inside without checking anything else, and treats the request as coming from that user.

## Why it's called "stateless"

Compare this to the older session-based approach. There, the server generates a random session ID, stores the actual user data server-side (in memory, in a fast lookup store like Redis, or in a database), and gives the client only that ID in a cookie. Every request means the server looks up the ID in that shared store to find out who's asking. That store is "state": data the server has to keep and consult on every request.

With a JWT, the token itself carries the claims, and the signature lets the server confirm they're genuine without looking anything up. Verifying a JWT is a self-contained calculation (check the signature, check the expiration), not a database or cache read. That's the stateless part: the server doesn't need to remember anything about who's logged in between one request and the next. It's why JWTs are popular in systems with many servers: any server holding the verification key can check a token without sharing a session store with every other server.

The limit of that model matters here: "stateless" describes how verification works, not the whole system. Most real deployments still keep some server-side state, for refresh tokens, rate limits, or the revocation problem below. It's a property of the token check, not a guarantee that no server-side state exists anywhere.

## Can you actually log someone out?

Partly true, and partly an oversimplification, depending on what "log out" has to mean.

If a JWT's only check is "is the signature valid and has it not expired," then no, there's no way to invalidate one specific token early. The server never keeps a list of currently valid tokens to remove one from; skipping that lookup is the entire point. Once issued, a JWT stays valid until its `exp` claim says otherwise, whether or not the user clicks "log out." That's a direct consequence of the design, not a bug: there's nowhere to record that one token is no longer good.

That's where the claim comes from, and as a description of bare JWT auth, it's accurate. But almost nobody ships bare JWT auth where real logout security matters. Common fixes, each of which puts a bit of state back on purpose:

1. **Short-lived JWTs plus a revocable refresh token.** The JWT itself expires in minutes. A separate refresh token, used only to obtain new JWTs, is stored server-side and can be revoked instantly. Logging out revokes the refresh token; the current JWT keeps working, but only for its remaining few minutes, and no new ones can be issued after that.
2. **A denylist.** The server keeps a small store, often Redis, listing the token or user IDs that have been logged out, and checks it on every request. This deliberately reintroduces a lookup to close the gap.
3. **A version check.** Each user gets a "token version" or "valid since" value in the database. That value is embedded in the JWT at login and compared against the current database value on every request. Logging out, or changing a password, bumps the stored value, which invalidates every token issued before that moment.

Each of these costs something: a lookup on every request, which is exactly what stateless verification was designed to skip. That's the actual trade-off: pure stateless JWTs verify fast but can't revoke early; anything that needs real logout buys that back by reintroducing some state, usually much less than a full session store.

One more distinction worth being precise about: a logout button that only deletes the token from the browser isn't revocation. It stops that browser from sending the token again, but a copy of the token, stolen through a compromised script, for instance, is still valid until it expires, because the server was never told to stop trusting it. Actual revocation needs one of the three mechanisms above.