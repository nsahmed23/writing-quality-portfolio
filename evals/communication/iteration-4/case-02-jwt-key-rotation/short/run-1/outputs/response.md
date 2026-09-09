You can rotate without logging anyone out, but only by making verification accept two keys for one full token lifetime before you retire the old one. The sequence matters: deploy the code that verifies against both keys everywhere first, flip signing second, delete the old key last. Doing those in any other order is exactly what produces the mass logout.

One premise worth checking before you start. If you are rotating because the secret leaked, an overlap window is the wrong move: anyone holding the old secret can mint valid tokens for as long as you keep accepting it. In a compromise, skip the overlap, cut straight to the new key, and accept that everyone logs out. The plan below is for routine or scheduled rotation.

### 1. Generate the new secret and put both keys in the environment

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

32 bytes is the floor for HS256 (HMAC-SHA256). A short human-chosen passphrase can be brute-forced offline against any token you have ever issued, so do not hand-write this value.

Do not overwrite `JWT_SECRET` in place. Add names alongside it:

```
JWT_ACTIVE_KID=2026-09
JWT_KEY_CURRENT=<the new 32-byte value>
JWT_KEY_LEGACY=<your existing JWT_SECRET value, unchanged>
```

`kid` ("key ID") is a standard JWT header field naming which key signed a token, so the verifier can select the right key instead of guessing. Your existing tokens have no `kid`, which is fine; the code below handles that case.

### 2. Deploy verify-both, sign-old

This deploy changes verification only. Signing still uses the old key, so nothing user-visible happens.

```js
// auth/keys.js
const ACTIVE_KID = process.env.JWT_ACTIVE_KID;
const KEYS = {
  [ACTIVE_KID]: process.env.JWT_KEY_CURRENT,
  legacy: process.env.JWT_KEY_LEGACY,   // verify-only during the overlap
};
for (const [kid, secret] of Object.entries(KEYS)) {
  if (!secret) throw new Error(`missing JWT secret for kid "${kid}"`);  // fail at boot, not under load
}
module.exports = { KEYS, ACTIVE_KID };
```

```js
// auth/verify.js
const jwt = require('jsonwebtoken');
const { KEYS } = require('./keys');

function verifyToken(token) {
  // The header is unsigned, so treat kid as a hint for picking a candidate key,
  // never as proof of anything. Every path below still runs a real verify.
  const kid = jwt.decode(token, { complete: true })?.header?.kid;
  const candidates = kid && KEYS[kid] ? [KEYS[kid]] : Object.values(KEYS);

  let lastErr;
  for (const secret of candidates) {
    try {
      return jwt.verify(token, secret, { algorithms: ['HS256'], clockTolerance: 5 });
    } catch (err) {
      if (err.name === 'TokenExpiredError') throw err;  // another key will not un-expire it
      lastErr = err;
    }
  }
  throw lastErr;
}

module.exports = { verifyToken };
```

Two notes on that snippet. Pin `algorithms: ['HS256']` explicitly rather than relying on library defaults, which have changed across `jsonwebtoken` major versions. And `jwt.verify` only accepts a key-lookup function in its async callback form, which is why this uses a synchronous try-each-candidate loop; it is a maximum of two HMAC operations and not worth optimizing.

Before you go anywhere near step 3, confirm every instance is running this build. On a rolling deploy behind a load balancer, some replicas will still be single-key mid-rollout, and flipping the signer while any of them are live will 401 a random slice of requests. Check your replica count and image digests, do not assume the deploy finished.

Then verify with a real token that was issued before this deploy:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $OLD_TOKEN" https://your-api/some-protected-route
```

Expect 200. If you get 401 here, stop and fix it; the old key is not wired into the verify path correctly, and continuing will log everyone out.

### 3. Flip signing to the new key

Change the sign call site, keeping the expiry you have:

```js
const { KEYS, ACTIVE_KID } = require('./auth/keys');

jwt.sign(payload, KEYS[ACTIVE_KID], {
  algorithm: 'HS256',
  expiresIn: '24h',
  keyid: ACTIVE_KID,   // jsonwebtoken writes this into the `kid` header
});
```

Deploy, then log in once and inspect the header of the token you get back:

```bash
node -e "console.log(require('jsonwebtoken').decode(process.argv[1], {complete:true}).header)" "$NEW_TOKEN"
```

Expect `{ alg: 'HS256', typ: 'JWT', kid: '2026-09' }`.

Record the UTC time the rollout finished. That is the moment the last old-key token could have been issued, and it starts the clock in step 4.

### 4. Wait out the old tokens

The last old-key token expires 24h after that recorded timestamp. Add margin for clock skew between whatever signs and whatever verifies, plus any deploy tail. Treat 26h as a reasonable working figure.

Do not trust the arithmetic alone. Add a counter to `verifyToken` tagged with the key that succeeded (`legacy` versus the active kid) and watch it. Retire the old key when legacy verifications have been at zero for a few hours, not merely when the clock says they should be. That counter also tells you if some client you forgot about is holding a long-lived token.

### 5. Remove the legacy key

Delete the `legacy` entry from `KEYS`, remove `JWT_KEY_LEGACY` from the environment, and deploy. Then purge the old value everywhere it lives: `.env` files on each host, your secret store, CI/CD variables, staging, any password manager entry, and the shell history of whoever last set it.

**Rollback rule.** Rolling back step 3 is safe: the build still verifies both keys, so tokens from either era keep working. Rolling back step 2 after step 3 has shipped is not: it logs out everyone who signed in since the flip. So if something breaks after the flip, revert the signing change, not the verification change.

### What I could not verify

I have not seen your code, so the snippets above are patterns rather than a diff. Your actual sign and verify call sites, auth middleware, and error mapping will differ, and the file names are invented.

Three things I would want confirmed against your repo:

- **Refresh tokens.** If you issue JWT refresh tokens signed with the same secret, their lifetime, not 24h, sets the step 4 wait. If refresh tokens are opaque database rows, 24h is correct as written.
- **Other verifiers.** Anything else reading `JWT_SECRET` has to get the step 2 change before you do step 3: a second service, a background worker, a websocket handler, a gateway plugin, a test fixture, staging. Run `grep -rn "JWT_SECRET" --include='*.js' --include='*.ts' --include='*.yml' --include='*.yaml' .` plus a check of your deployment configs, and confirm the list is empty besides the API.
- **Your deploy topology.** Whether the step 2 "every instance first" checkpoint is trivial (single process) or the riskiest part of this (many replicas, rolling update) depends on how you run the API, which I do not know.

Last thing worth naming: rotation does not revoke anything. If part of the goal is being able to kick a specific user or session immediately, that needs a separate mechanism, either short access tokens with a refresh endpoint that checks a revocation list, or a `jti` denylist consulted on verify.
