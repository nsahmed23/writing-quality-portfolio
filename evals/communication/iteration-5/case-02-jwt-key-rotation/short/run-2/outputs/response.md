"Rotate the key" and "keep everyone logged in" only conflict if your API knows one key at a time. Split the two roles: sign with exactly one key, verify against a *set* of keys, and retire the old key only after every token it signed has expired.

The ordering rule that carries the whole plan: **deploy the ability to verify the new key before anything signs with it.** Flip signing first and any process still running the old code rejects the new tokens with `invalid signature`, which looks exactly like the mass logout you're avoiding.

One premise check before the steps. If you're rotating because the secret may have leaked, this is the wrong plan: a 24h overlap window that keeps old tokens valid also keeps an attacker's forged tokens valid for 24h. In that case, cut the old key immediately and accept the logouts, or add a per-user `tokensValidAfter` timestamp and reject tokens whose `iat` is earlier. Everything below assumes routine rotation.

## 1. Generate the new secret

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

32 bytes is the right size for HS256, which is HMAC-SHA256. `jsonwebtoken` will sign happily with a 12-character passphrase and never warn you, so if that's what `JWT_SECRET` currently holds, this rotation is also the fix for it.

Add it to production config *alongside* the existing value, and keep the current variable name so you aren't editing a working deploy path:

```
JWT_SECRET=<existing value>      # key id k1
JWT_SECRET_NEXT=<new value>      # key id k2
JWT_ACTIVE_KID=k1
```

## 2. Put both keys behind a single `kid` lookup

`kid` (key id) is a standard JWT header field naming which key signed the token. Signing with it is what lets verification pick the right key instead of guessing.

```js
// src/auth/keys.js
const KEYS = {
  k1: process.env.JWT_SECRET,
  k2: process.env.JWT_SECRET_NEXT,
};

const ACTIVE_KID = process.env.JWT_ACTIVE_KID;
const LEGACY_KID = 'k1'; // tokens minted before kid existed

for (const [kid, secret] of Object.entries(KEYS)) {
  if (!secret) throw new Error(`JWT key ${kid} is missing from env`);
}
if (!KEYS[ACTIVE_KID]) throw new Error(`JWT_ACTIVE_KID=${ACTIVE_KID} has no secret`);

module.exports = { KEYS, ACTIVE_KID, LEGACY_KID };
```

Throwing at startup is deliberate. A missing second key should fail the deploy, not fail one request at a time in production.

## 3. Rewrite sign and verify against that map, still signing with k1

```js
const jwt = require('jsonwebtoken');
const { KEYS, ACTIVE_KID, LEGACY_KID } = require('./keys');

function signToken(payload) {
  return jwt.sign(payload, KEYS[ACTIVE_KID], {
    algorithm: 'HS256',
    expiresIn: '24h',
    keyid: ACTIVE_KID, // jsonwebtoken writes this into header.kid
  });
}

function verifyToken(token) {
  const decoded = jwt.decode(token, { complete: true });
  if (!decoded) throw new jwt.JsonWebTokenError('malformed token');

  const kid = decoded.header.kid ?? LEGACY_KID;
  const secret = KEYS[kid];
  if (!secret) throw new jwt.JsonWebTokenError('unknown key id');

  const payload = jwt.verify(token, secret, { algorithms: ['HS256'] });
  metrics.increment('jwt.verified', { kid }); // or a log line; step 6 needs this
  return payload;
}
```

Two things in there are load-bearing. `jwt.decode` does not check the signature, so the header is unauthenticated attacker-controlled input; it is only ever used to index a fixed server-side map, and anything not in the map is a 401. And `algorithms: ['HS256']` gets pinned in every verify call: recent `jsonwebtoken` versions block the worst algorithm-confusion cases on their own, but pinning is one line and removes the question.

The `LEGACY_KID` fallback is what protects the tokens already in your users' browsers. They have no `kid` header at all, so they resolve to k1 and keep working.

Smaller-diff alternative if you'd rather not add `kid`: try `jwt.verify` with the new secret, catch, retry with the old one. It works, with one trap. `jsonwebtoken` checks the signature before expiry, so an old-key token first throws `JsonWebTokenError: invalid signature` against the new key, and only the retry surfaces `TokenExpiredError`. If your error handler collapses both attempts into a generic 401, any client that watches for "expired" to trigger a refresh breaks. You also lose the per-key counter that gates step 6.

## 4. Deploy step 3 with signing unchanged

`JWT_ACTIVE_KID` is still `k1`. Confirm on the deployed version that an existing token from before this deploy still authenticates, and that a freshly issued token carries `kid: k1`:

```bash
node -e "console.log(require('jsonwebtoken').decode(process.argv[1],{complete:true}).header)" "$TOKEN"
```

## 5. Flip signing to k2, as its own deploy

Set `JWT_ACTIVE_KID=k2` and change nothing else. Do this only after step 4 is live on *every* process that verifies these tokens, not just the first one to roll.

Then check both directions: new logins mint `kid: k2`, and a k1 token issued before the flip still passes. Rollback here is reverting one variable, and tokens already signed with k2 keep verifying because k2 stays in the map either way. That property is the reason to keep steps 4 and 5 as separate deploys even on a single instance.

## 6. Wait out the overlap, using the counter rather than the clock

The last k1 token was minted the moment step 5 finished on the final instance, and it dies 24h later. So hold k1 in the map for at least 24h from that point, plus margin for clock skew.

Better gate: watch the `jwt.verified{kid=k1}` counter from step 3. When it has been flat at zero for a few hours past the 24h mark, nothing in the wild is still presenting a k1 token, and removal is provably safe. If the counter is still nonzero after 24h, something is signing with k1 that you didn't know about, and that is worth finding before you break it.

## 7. Retire k1

Delete `k1` from `KEYS`, delete the `LEGACY_KID` fallback and its `?? LEGACY_KID`, deploy, then remove `JWT_SECRET` from your config store. Last, rename `JWT_SECRET_NEXT` to a `k2`/`k3` shape so the next rotation is the same seven steps and not a special case. If the retired value was ever committed to git, that is a separate cleanup.

## What I couldn't verify

I can't see your code or your deployment, so check these four things; each one can turn the plan above into an outage at step 5.

- **How many places call `jwt.verify`.** The plan assumes one middleware. Run `grep -rn "jwt.verify\|jwt.sign" src/` and route every hit through the new module. A missed call site keeps its single-key verify and starts 401-ing the instant you flip the active kid.
- **What else touches `JWT_SECRET`.** A background worker, a second service, a websocket handshake, a client that decodes locally, test fixtures. Anything that verifies these tokens needs step 3 deployed before step 5.
- **Refresh tokens.** If they're signed with the same secret and live longer than 24h, the overlap in step 6 is the longest lifetime ever signed with k1, not 24h.
- **How production env is actually set.** A `.env` on a box, Cloud Run env vars, a secret manager: whichever it is, confirm both variables are present in the same revision before the active kid flips, and that a rolling restart can't hand one process the new kid while another lacks the key.
