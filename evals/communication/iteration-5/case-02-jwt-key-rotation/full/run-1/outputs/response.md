Accept both secrets for one full token lifetime, sign only with the new one, then retire the old. Nobody gets logged out because every token already in circulation still verifies against a key the server holds. One condition before you start: a graceful rotation keeps the old secret usable for another 24 hours by design, so if you are rotating because the old secret leaked, use the "If the old secret leaked" section instead.

## Do now

**1. Generate the new secret, and capture a token signed with the old one.**

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

32 random bytes is 256 bits, the minimum size HS256 should use. Leave the current `JWT_SECRET` value exactly as it is; you need it for another day. Then log in once against production and save that access token as `TOKEN_OLD`. It is signed with the current secret, and it is your evidence in step 5 that no session broke.

Steps 1 to 5 are roughly 30 minutes of work if `jwt.sign` and `jwt.verify` appear in only one or two files, plus however long your two deploys take.

**2. Put both keys behind one module.**

```js
// src/auth/keys.js
const jwt = require('jsonwebtoken');

// PRIMARY signs and verifies. SECONDARY only verifies.
const SECRETS = [
  process.env.JWT_SECRET_PRIMARY,
  process.env.JWT_SECRET_SECONDARY,
].filter(Boolean);

if (SECRETS.length === 0) {
  throw new Error('JWT_SECRET_PRIMARY is not set');
}

function signToken(payload, options = {}) {
  return jwt.sign(payload, SECRETS[0], {
    algorithm: 'HS256',
    expiresIn: '24h',
    ...options,
  });
}

function verifyToken(token) {
  let lastError;
  for (const secret of SECRETS) {
    try {
      return jwt.verify(token, secret, { algorithms: ['HS256'] });
    } catch (err) {
      // Only a bad signature is worth retrying against the next key.
      if (err.name !== 'JsonWebTokenError') throw err;
      lastError = err;
    }
  }
  throw lastError;
}

module.exports = { signToken, verifyToken };
```

Find the call sites with `grep -rn "jwt\.sign\|jwt\.verify\|JWT_SECRET" src/`, then replace each `jwt.verify(token, process.env.JWT_SECRET, ...)` with `verifyToken(token)` and each `jwt.sign(payload, process.env.JWT_SECRET, ...)` with `signToken(payload)`. On TypeScript or ESM the logic is identical; only `require`/`module.exports` become `import`/`export`.

Two lines in that file carry weight. `algorithms: ['HS256']` stops a token whose header names some other algorithm from being accepted. The `err.name` check keeps an expired token reported as expired: jsonwebtoken checks the signature before it looks at `exp`, so a `TokenExpiredError` means the signature already passed under that key and trying the other key would only turn a clean "expired" into a confusing "invalid signature".

If your test suite imports this module, set `JWT_SECRET_PRIMARY` in the test environment too, or the tests throw at import.

**3. Deploy with both keys loaded, still signing with the old one.**

```
JWT_SECRET_PRIMARY=<current JWT_SECRET value, unchanged>
JWT_SECRET_SECONDARY=<new secret from step 1>
```

Set these wherever your production environment variables actually come from, deploy, then confirm nothing broke:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN_OLD" https://your-api/me
```

Expect `200`.

Do not collapse this into step 4. During a rolling restart, instances running the old config and the new config serve traffic at the same time, and an instance that has never heard of the new secret rejects every token signed with it. This deploy is what closes that gap: afterwards every instance accepts both keys, in either direction. The same reasoning points outward. If another service, a worker, or a second API verifies these tokens with the same secret, it needs both keys now as well.

**4. Swap the two values. This is the rotation.**

```
JWT_SECRET_PRIMARY=<new secret>
JWT_SECRET_SECONDARY=<old secret>
```

Restart. No code changes here, so rolling back means swapping them again. From this point new logins receive new-key tokens and every old token still verifies against the secondary. The 24-hour clock starts when the last old-config instance stops serving, because that is the last moment an old-key token can be issued.

**5. Prove both halves.**

Re-run the `curl` from step 3 with `TOKEN_OLD` and expect `200` again: that is "nobody was logged out". Then log in to get a fresh token and check which key signed it:

```bash
TOKEN=<fresh token> node -e "const j=require('jsonwebtoken');for(const k of ['JWT_SECRET_PRIMARY','JWT_SECRET_SECONDARY']){try{j.verify(process.env.TOKEN,process.env[k],{algorithms:['HS256']});console.log(k,'verifies')}catch(e){console.log(k,'rejects:',e.message)}}"
```

Run it from the project directory in a shell that already has both variables set, so the secrets never appear in your shell history. Expect `JWT_SECRET_PRIMARY verifies` and `JWT_SECRET_SECONDARY rejects: invalid signature`. Reversed output means that instance is still running the step 3 config and did not pick up the swap.

## 24 hours after step 4 finishes

**6. Remove the old key.** Set `JWT_SECRET_PRIMARY` to the new secret, delete `JWT_SECRET_SECONDARY`, restart. Then destroy the old value everywhere it lives: the production secret store, CI variables, `.env` on developer machines, any password manager entry.

Wait longer than 24 hours in two cases: if you pass `clockTolerance` to verify, add that on top, and if refresh tokens are signed with the same secret, the window is the lifetime of the longest-lived token signed with the old key, not the 24-hour access token.

## If the old secret leaked

You cannot keep existing sessions and stop honoring the leaked secret at the same time, because they are the same key. Pick one:

- **Hard cut**, which is the right answer for a leak: set `JWT_SECRET_PRIMARY` to the new secret with no secondary at all, restart. Everyone signs in once more and the leaked secret is dead immediately.
- **Keep sessions and revoke selectively**: store a per-user cutoff timestamp and compare it against each token's `iat` claim (the issued-at time), rejecting anything older. A bare HS256 token carries nothing else to revoke on. That is a session-invalidation feature and a considerably bigger job than the six steps above.

## What I could not check

I cannot see your repository or your deployment, so three things are assumptions rather than verified facts:

- Where `jwt.sign` and `jwt.verify` are actually called, and whether `src/auth/keys.js` fits your layout. The grep in step 2 settles both.
- Whether `.env` is the real source of production environment variables or only your local one. If production reads from a secret store or CI variables, steps 3, 4, and 6 happen there and `.env` is only the development copy.
- Whether anything besides this API's login path signs or verifies with `JWT_SECRET`: refresh tokens, a second service, a worker, a mobile client on a longer expiry. Each one needs both keys during the window, and the longest expiry among them sets the real wait before step 6.

Separately: pass `keyid` to `jwt.sign` from now on so tokens carry a `kid` header, and the next rotation can select the key by id instead of trying each one. That is a second job, not part of this one.

The single result that proves the rotation was invisible: `TOKEN_OLD`, minted before step 3, still returns `200` after step 4.
