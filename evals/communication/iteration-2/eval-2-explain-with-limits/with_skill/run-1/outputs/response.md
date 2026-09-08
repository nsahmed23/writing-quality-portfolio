## How JWT auth works

A JWT (JSON Web Token) is a compact, signed piece of text that carries claims: facts about a user, such as their ID, role, and when the token expires. Here's the flow that creates and uses one.

The user sends credentials (username and password) to a login endpoint. The server checks them against its database, and if they're valid, it builds a JWT instead of creating a session record. The token has three parts separated by dots: a header (which signing algorithm was used), a payload (the claims themselves, written in plain readable JSON that's only base64-encoded, not encrypted, so anyone who intercepts the token can read it), and a signature (proof that the header and payload haven't been altered since signing, produced with a secret key or, for asymmetric algorithms, a private key).

The server hands this token to the client, which stores it (in a cookie, in memory, or in localStorage) and attaches it to every later request, typically in an `Authorization: Bearer <token>` header. "Bearer" means what it sounds like: whoever presents the token is treated as authenticated, no further proof required. On each request, the server recomputes the signature from the header and payload and compares it to the one on the token. If they match, the payload hasn't been tampered with, and the server can trust the claims inside it: who the user is, what they're allowed to do, and whether the token has expired (checked against the `exp` claim, a timestamp inside the payload).

That check is math the server does alone. It never has to look anything up.

## Why people call it stateless

Compare this to session-based auth, the older pattern. There, the server generates a random session ID at login, stores the session's actual data (user ID, roles, and so on) in a database or an in-memory store like Redis, and hands the client only the ID. Every request forces the server to take that ID and look up the session data behind it. The server is holding state: it has to remember, for every logged-in user, which sessions currently exist. Scale that server horizontally behind a load balancer (something that spreads incoming requests across multiple server instances), and every instance needs access to the same shared session store, or a user ends up logged out depending on which instance handles their next request.

JWT auth removes that lookup. Because the token carries its own claims and proves its own integrity through the signature, any server holding the right verification key (the shared secret, for HMAC-signed tokens, or the matching public key, for tokens signed with a private key) can check it on its own: no shared database, no session store, no coordination between servers. That's what "stateless" means here: the server keeps no record of who is logged in. Every request carries everything needed to authenticate it, and the server's only job is to verify the signature and read the claims.

## Can you actually log someone out?

What you've heard is half right, and the imprecise version of it is exactly what causes real security mistakes.

A pure JWT setup, exactly as described above, cannot revoke one specific token early. The server never stored a record of issuing it, so there's nothing to delete. If your app's idea of "logout" is just removing the token from the browser's localStorage, the token itself is still perfectly valid: signature intact, not expired. Anyone who had a copy of it before that logout, stolen through XSS (a script an attacker sneaks into your page that can read anything your page's own JavaScript can read, including a token sitting in localStorage), a leaked server log, or a compromised browser extension, can keep using it until it expires on its own, logout or not. That's the true part: deleting a token client-side feels like logging out, but it changes nothing about whether the server will still accept that token.

Where the claim overstates things is in treating this as unfixable. Production systems get real revocation back by reintroducing a bit of server-side state, using one of a few patterns:

- Short-lived access tokens plus a refresh token. The JWT itself expires in minutes, so a stolen one is only dangerous for a short window. A separate, longer-lived refresh token, stored server-side, is what mints new access tokens. Logout revokes the refresh token; the current access token keeps working until its short expiry runs out, but nothing new gets issued after that.
- A revocation list, often called a denylist or blocklist. The server keeps a small store, checked on every request, of token IDs (the `jti` claim, a unique identifier assigned to each token) that have been logged out early. This puts a database lookup back on every request, which gives up most of the "stateless" benefit you were after in the first place.
- A "valid-since" timestamp per user. Store one timestamp per user; logout, or a password change, bumps it forward. Reject any token issued before that timestamp. Cheaper than a full denylist (one row per user instead of one per token), but still a lookup.

So the two things don't fully coexist: pure, instant, cost-free logout and pure statelessness are in tension. Real logout is available, but only by adding back some of the server-side state JWTs were designed to avoid, and the more instantly you need logout to take effect, the more of that state you end up reintroducing.
