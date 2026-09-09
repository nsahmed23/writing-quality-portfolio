JWT (JSON Web Token) auth works by having the server issue a signed token when you log in, and having you present that token on every later request instead of a session ID.

The flow looks like this:

1. You send credentials (username/password) to the server.
2. The server verifies them, then builds a JWT: a JSON payload (user ID, roles, an expiration timestamp, etc.) that gets encoded and cryptographically signed with a secret key (HMAC) or a private key (RSA/ECDSA).
3. The server hands you that token. You store it (cookie, localStorage, wherever your app keeps it) and send it back with every request, typically in an `Authorization: Bearer <token>` header.
4. On each request, the server checks the signature instead of looking anything up. It verifies the signature over the payload; if it's valid, it trusts the claims inside, including the expiration, and processes the request.

Worth flagging: a standard JWT is signed, not encrypted. Anyone holding the token can decode and read the payload. The signature only proves it wasn't tampered with, not that its contents are secret, so don't put anything sensitive in the claims.

Step 4 is why people call this "stateless." The server never stores "who is logged in right now" anywhere: no session table, no in-memory session map, nothing to check on each request. Everything needed to authenticate travels inside the token itself, and verifying it is pure computation (checking a signature and an expiration timestamp), not a database lookup. That's the appeal for scaling: any server instance, anywhere, can verify any token on its own, with no shared session store and no coordination between servers.

Compare that to classic session-based auth: the server generates a random session ID, stores the actual user data server-side (Redis, a database, wherever), and gives the client only the ID. Every request triggers a lookup: does this ID exist, and what does it map to? That's stateful, and logging someone out is trivial: delete that record, and the ID is now worthless.

So, to your actual question: yes, it's true, and it's the direct cost of the design above. Once a JWT is issued, it stays valid until it expires, no matter what happens afterward. There is no server-side record to delete, because the server never kept one. If you "log out" by deleting the token from the browser, you've only deleted the client's copy. Anyone else holding that token, an attacker who intercepted it, a second device that cached it, can keep using it right up until the expiration timestamp, and the server has no way to tell the difference between them and you.

In practice, nobody ships pure stateless JWTs with no way to revoke them. The common fixes all work by reintroducing a little bit of state, on purpose, in exchange for control:

- **Short expiration times.** Make the JWT valid for minutes, not days. A stolen or "logged out" token is only a live threat for that window. This is the baseline almost everyone uses.
- **Refresh tokens.** The short-lived JWT does the actual authenticating; a separate, longer-lived refresh token, which the server does track in a database, is used to mint new JWTs. Logging out means revoking the refresh token. The already-issued JWT still expires on its own shortly after, since it's short-lived.
- **A revocation list (denylist).** The server keeps a small store, often Redis, of token IDs that were explicitly invalidated before their natural expiry, with a TTL matching the token's own expiration so the list doesn't grow forever. Every request checks against it. This works, but it's a lookup on every request, exactly what stateless auth was meant to avoid. At that point you have a hybrid: mostly stateless, with one narrow stateful check bolted on.
- **A version or "security stamp" field on the user record.** Put a version number in the token, bump it in the database on logout or password change, and compare it to the current value on each request. Same tradeoff as the denylist: you're back to a database check, just against a record you were probably already loading.

So the accurate version of the claim: a genuinely stateless JWT cannot be revoked before it expires, full stop, because revocation requires the server to remember something, and by definition it isn't remembering anything. Every real system that needs reliable logout accepts a bit of statefulness back, whether that's a revocable refresh token, a denylist, or a version check, while keeping the token itself short-lived so the exposure window stays small. What you keep is that this reintroduced state is narrow (just revocations, not full session data for every user), which is most of the scalability win JWTs were chosen for in the first place.
