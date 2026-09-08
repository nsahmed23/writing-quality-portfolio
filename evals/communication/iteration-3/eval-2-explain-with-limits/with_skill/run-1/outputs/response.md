A JWT (JSON Web Token) is a signed, self-contained credential: the server packs proof of identity directly into the token instead of keeping a record of who's logged in.

## How it works

A JWT is three pieces of text joined by dots, `header.payload.signature`, each piece encoded (not encrypted) so it's safe to put in a URL or an HTTP header.

1. Header: which algorithm signed the token, commonly HMAC-SHA256 (one shared secret both sides know) or RSA/ECDSA (a private key that signs, a matching public key that verifies).
2. Payload: the claims, meaning statements about the user, such as `sub` (subject, usually the user ID), `exp` (expiration time), and whatever custom fields the app needs, like roles or permission levels.
3. Signature: the header and payload run through the algorithm from step 1, using a secret or private key that only the server holds. Anyone can read the payload, since it's just encoded, not encrypted, but only whoever holds that key could have produced a signature that matches it.

The login flow:

1. The user submits credentials.
2. The server verifies them, builds a payload with the user's identity, and signs it.
3. The server hands the resulting JWT to the client, which stores it (memory, a cookie, localStorage) and sends it back on every request, typically in a header: `Authorization: Bearer <token>` (bearer meaning whoever presents the token is treated as authorized, no further proof required).
4. The server recomputes the signature over the header and payload it received and checks it against the signature on the token. If they match and `exp` hasn't passed, the request is authenticated. No database call involved.

## Why people call it stateless

Compare that to the older session-cookie model. There, the server generates a random session ID, stores a row somewhere (memory, Redis, a database) mapping that ID to "this is user X, logged in at this time, with these permissions," and gives the browser only the ID. Every request means a lookup: take the ID from the cookie, fetch the matching row, confirm it's still valid.

That lookup is the "state": server-side data that has to exist for the credential to mean anything. A JWT skips it. The payload already carries the identity, and the signature proves nobody tampered with it since the server issued it, so verifying a JWT is pure computation, no storage read required. That's the stateless part: any server holding the signing key (or the matching public key, for RSA/ECDSA) can verify any token on its own, without a shared session store. That is also why JWTs are popular for systems running many backend instances: no server needs to share session data with any other server.

Worth being precise about: it's the authentication check that's stateless, not the whole system. Nothing stops the app from also querying a database for other reasons, like loading the user's profile. "Stateless" describes how identity gets verified, not a rule against the server ever looking anything up.

## Can you actually log someone out?

Partly true, and the true part is the important part.

A JWT stays valid, as far as any server checking it is concerned, until its signature stops matching (it won't; nothing altered it) or its `exp` claim passes. Nothing in that check asks whether the issuer still endorses the token. So with nothing more than what's described above, "log out" can only mean the client deletes its local copy and stops sending it. If a copy exists anywhere else, a second browser tab, a token stolen through an XSS bug, one sitting in a server log, it keeps working exactly as before until it expires, regardless of whether the user thinks they are logged out.

That is the real substance behind "you can't log out with JWTs": there is no built-in, free way to kill one specific already-issued token early. It is a direct consequence of skipping the server-side lookup, not an exaggeration.

Where the claim overreaches is the word "can't." Production systems handle this routinely, by putting back a small, deliberate amount of the state that JWTs were designed to avoid:

- Short-lived access tokens (5 to 15 minutes is typical) paired with a refresh token: a separate, longer-lived token that the server does store, precisely so it can be revoked. Logout deletes that stored record; the current access token expires naturally within minutes, and no new one can be issued after that. This access-plus-refresh pattern is the standard shape of JWT-based auth in production today.
- A denylist (also called a blocklist): the server records the ID of any token that has been explicitly revoked, usually the `jti` claim (a unique ID assigned to each token), in a fast store like Redis, with a TTL (time-to-live, how long the entry stays before it auto-expires) matching the token's remaining lifetime. Every request checks that list first. This brings a lookup back, so it is not purely stateless anymore, but it is a cheap one.
- A "valid since" timestamp per user: logging out, or changing a password, bumps a stored timestamp; any token issued before that timestamp is rejected the next time it is presented.

None of these three approaches keeps the system purely stateless; each trades a small, deliberate piece of server-side state for the ability to revoke a token early. That trade-off is inherent: guaranteed instant revocation requires checking something the server stores, and skipping that stored check is exactly what makes plain JWT verification stateless. Choose plain JWTs and accept that logout means the client stops sending the token while the token itself stays technically valid until it expires. Choose one of the mitigations above and accept one small, cheap lookup per request in exchange for real revocation.

Default to short-lived access tokens plus a revocable refresh token, unless there is a specific reason to need an immediate way to invalidate a single session, such as a compromised account or an admin-forced logout. That combination covers ordinary logout expectations without giving up JWTs' main advantage.