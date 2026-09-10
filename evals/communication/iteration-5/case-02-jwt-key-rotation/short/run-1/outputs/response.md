Rotating without logging anyone out works because signing and verification are separable: you accept both the old and the new secret for a window at least as long as your longest-lived token, but you sign only with the new one. Swapping the value of `JWT_SECRET` in place invalidates every outstanding token the moment the process restarts, which is exactly the logout you want to avoid. `jsonwebtoken` has no built-in key set, so the first code change is adding one, indexed by the `kid` ("key ID") field that a JWT header can carry for precisely this purpose.

One condition before you start: this only holds if the old secret is not compromised. If you are rotating because it leaked, was committed to git, or was pasted somewhere, then keeping it valid for another 24 hours keeps the exposure open for another 24 hours. In that case forcing re-authentication is the goal, not the problem, and you skip straight to step 7.

## 1. Generate the new secret

```bash
node -e "console.log(require('crypto').randomBytes(64).toString('base64url'))"
```

32 bytes is the floor for HS256; 64 bytes matches the HMAC-SHA256 block size, so use 64. Do not derive it from the old value.

## 2. Put both secrets in the environment, plus an explicit "which one signs" pointer

```
# the value that is in JWT_SECRET today, copied verbatim
JWT_SECRET_K1=<current secret>
# the value from step 1
JWT_SECRET_K2=<new secret>
# which key signs new tokens; stays k1 for now
JWT_ACTIVE_KID=k1
# leave the original var in place for now: it verifies tokens issued before this change
JWT_SECRET=<current secret>
```

`JWT_SECRET` is kept only because every token currently in a user's browser was signed without a `kid` header, so verification needs a fallback for headerless tokens. It signs nothing from here on.

## 3. Add the key set, signer, and verifier

```js
// auth/keys.js
const KEYS = Object.freeze({
  k1: process.env.JWT_SECRET_K1,
  k2: process.env.JWT_SECRET_K2,
});

const ACTIVE_KID = process.env.JWT_ACTIVE_KID;
const LEGACY_SECRET = process.env.JWT_SECRET; // verify-only, for kid-less tokens

// fail at boot, not on the first 401
for (const [kid, secret] of Object.entries(KEYS)) {
  if (!secret) throw new Error(`missing JWT_SECRET_${kid.toUpperCase()}`);
}
if (!KEYS[ACTIVE_KID]) {
  throw new Error(`JWT_ACTIVE_KID=${ACTIVE_KID} has no matching secret`);
}

module.exports = { KEYS, ACTIVE_KID, LEGACY_SECRET };
```

```js
// auth/tokens.js
const jwt = require('jsonwebtoken');
const { KEYS, ACTIVE_KID, LEGACY_SECRET } = require('./keys');

// count what is actually still being presented, so step 6 is a measurement
const verifyCounts = { legacy: 0, k1: 0, k2: 0 };

function signAccessToken(payload) {
  return jwt.sign(payload, KEYS[ACTIVE_KID], {
    algorithm: 'HS256',
    expiresIn: '24h',
    keyid: ACTIVE_KID, // sets the `kid` header
  });
}

function secretFor(kid) {
  if (!kid) return LEGACY_SECRET; // issued before this deploy
  // kid comes from an unverified header, so it may only index a frozen allowlist
  return Object.prototype.hasOwnProperty.call(KEYS, kid) ? KEYS[kid] : null;
}

function verifyAccessToken(token) {
  const decoded = jwt.decode(token, { complete: true }); // decode does NOT verify
  if (!decoded) throw new jwt.JsonWebTokenError('malformed token');

  const kid = decoded.header.kid;
  const secret = secretFor(kid);
  if (!secret) throw new jwt.JsonWebTokenError('unknown key id');

  // pin the algorithm; never let the token's own header choose it
  const claims = jwt.verify(token, secret, { algorithms: ['HS256'] });
  verifyCounts[kid ?? 'legacy'] += 1;
  return claims;
}

module.exports = { signAccessToken, verifyAccessToken, verifyCounts };
```

Then replace every call site. Find them all first, because one missed `jwt.verify(token, process.env.JWT_SECRET)` in a second middleware or a websocket handshake is the usual way this breaks:

```bash
grep -rn "JWT_SECRET\|jwt.verify\|jwt.sign" --include="*.js" --include="*.ts" . | grep -v node_modules
```

Every verify path becomes `verifyAccessToken(token)`; every issue path becomes `signAccessToken(payload)`.

## 4. Deploy the verifier while still signing with the old key

Ship step 3 with `JWT_ACTIVE_KID=k1`. Users see no change, and new tokens start carrying `kid: "k1"`.

This phase exists on its own for a reason. During a rolling deploy, instances running the previous build know only the old secret, so if new instances started signing with `k2` immediately, any request that landed on a not-yet-replaced instance would 401. Splitting the deploy means every process can verify both keys before any process starts producing tokens with the new one. If you run exactly one process and restart it in place, the two phases collapse into one, but the split costs you nothing.

Confirm before moving on: hit a protected route with a token minted before the deploy (expect 200), and check the header of a freshly issued one.

```bash
node -e "console.log(require('jsonwebtoken').decode(process.argv[1],{complete:true}).header)" "$TOKEN"
```

## 5. Flip the signing key

Set `JWT_ACTIVE_KID=k2` and restart. `dotenv` reads `.env` once at boot, so a restart or redeploy is required for the change to take effect; nothing picks it up live.

Whatever holds these values (a `.env` file per host, a secret manager, CI variables) must already have both `JWT_SECRET_K1` and `JWT_SECRET_K2` on every instance before this step. If any instance is missing `k2` when it becomes active, that instance fails at boot from the check in step 3, which is the behavior you want.

Rollback for this step is flipping the pointer back to `k1` and restarting. Tokens already signed with `k2` keep working, because `k2` stays in the verification map either way.

## 6. Wait out the overlap, then confirm it drained

The old key must stay verifiable until the last token signed with it has expired. That is 24 hours after the final `k1` signature, meaning 24 hours after step 5 finished on the last instance, plus a margin for clock skew between your servers and any cached token. Use 26 hours as a minimum.

Take the longest `expiresIn` in your codebase, not the 24h access-token figure, if anything else is signed with the same secret: refresh tokens, "remember me" cookies, password-reset or email-verification links, and machine API tokens all commonly reuse `JWT_SECRET` and often live for weeks. The overlap window has to cover the longest of them.

Then verify rather than assume. Log or expose `verifyCounts` (an internal route, or a periodic log line) and retire the old key only once `legacy` and `k1` have both been flat at zero for a full token lifetime. That counter is what turns "it should be safe by now" into evidence.

## 7. Retire the old key

Remove `JWT_SECRET` and `JWT_SECRET_K1` from `.env` and from your secret store, delete the `k1` entry from `KEYS`, delete the `LEGACY_SECRET` fallback branch in `secretFor` so a kid-less token is rejected outright, and redeploy. Any token still presenting `kid: "k1"` now gets a 401, which is the intended end state.

Your next rotation is then only steps 1, 2, 5, 6, 7: add `k3`, flip the pointer, wait, drop `k1`. No code change.

## Tests worth writing before step 4

Cover these with both keys loaded: a token signed with `k1` verifies; a token signed with `k2` verifies; a kid-less token signed with the old `JWT_SECRET` verifies; a token with `kid: "k9"` is rejected; a token signed with `k1` but whose header claims `kid: "k2"` is rejected on signature; a token with an `alg` of `none` or `RS256` is rejected by the `algorithms` pin; an expired token is rejected. The last two are the ones that catch a regression if someone later "simplifies" the verifier.

## What I could not check

I cannot see your code or deployment, so four things are assumptions rather than verified facts. Whether the 24h access token is the only thing signed with `JWT_SECRET`, which decides your step 6 window. How many processes serve the API, which decides whether steps 4 and 5 must genuinely be separate deploys. How many verify call sites exist, since I could not run the grep for you. And how `.env` reaches production, which is where the "both values present everywhere before the flip" requirement actually gets satisfied or quietly missed. Run the grep in step 3 and read off the largest `expiresIn` it turns up before you pick the overlap window.
