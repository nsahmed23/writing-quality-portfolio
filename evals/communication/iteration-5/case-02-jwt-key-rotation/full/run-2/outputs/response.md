Keep both keys valid for one token lifetime: verify against the old and the new key, sign with the new one, drop the old one 24 hours later. A straight swap of `JWT_SECRET` logs everyone out because HS256 is symmetric, so the secret that signed a token is the only thing that can verify it, and every token already in a browser was signed with the old value.

If you are rotating because the old secret leaked, this plan is the wrong one: for the whole 24 hour overlap, anyone holding that secret can still mint tokens your API accepts. In that case swap in one step and accept the logouts.

## Do now

1. Find every place the secret is used. Point this at your source root:

```bash
grep -rn "jwt.sign\|jwt.verify\|JWT_SECRET" src/
```

   This sets how long the overlap has to last. If anything besides the 24 hour access token is signed with `JWT_SECRET` (refresh tokens, password reset links, email verification links, service-to-service tokens), the window is the longest of those expiries, not 24 hours. Budget about 30 minutes for steps 1 to 5 if there is a single signing site, then a day of waiting before step 6.

2. Generate the new key, 32 bytes for HS256:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

   Add three variables wherever your app reads config (`.env` locally, your platform's environment or secret store in production). Leave the existing `JWT_SECRET` line alone for now so a rollback has something to fall back on.

```
JWT_SECRET_V1=<the current JWT_SECRET value, copied exactly>
JWT_SECRET_V2=<the value you just generated>
JWT_SIGNING_KID=v1
```

3. Put key selection in one file, `src/auth/jwt-keys.js` or wherever your token code lives (adjust the import style if the project is TypeScript or ESM):

```js
const jwt = require('jsonwebtoken');

const KEYS = {
  v1: process.env.JWT_SECRET_V1,
  v2: process.env.JWT_SECRET_V2,
};
const SIGNING_KID = process.env.JWT_SIGNING_KID || 'v1';
const LEGACY_KID = 'v1'; // tokens issued before today carry no kid header

for (const [kid, secret] of Object.entries(KEYS)) {
  if (!secret) throw new Error(`JWT key ${kid} is missing from the environment`);
}
if (!KEYS[SIGNING_KID]) throw new Error(`JWT_SIGNING_KID=${SIGNING_KID} has no matching key`);

function signToken(payload) {
  return jwt.sign(payload, KEYS[SIGNING_KID], {
    algorithm: 'HS256',
    expiresIn: '24h',
    keyid: SIGNING_KID, // jsonwebtoken writes this into the token's `kid` header
  });
}

function verifyToken(token) {
  const decoded = jwt.decode(token, { complete: true });
  if (!decoded) throw new jwt.JsonWebTokenError('jwt malformed');
  const kid = decoded.header.kid || LEGACY_KID;
  const secret = KEYS[kid];
  if (!secret) throw new jwt.JsonWebTokenError('unknown key id');
  return jwt.verify(token, secret, { algorithms: ['HS256'] });
}

module.exports = { signToken, verifyToken };
```

   Then replace every `jwt.sign` and `jwt.verify` you found in step 1 with `signToken` and `verifyToken`, so no route or middleware reads a secret directly. If your current calls pass `issuer`, `audience`, `subject`, or a different `expiresIn`, carry those options through; the snippet only shows the ones you described.

   Three details in that file are load-bearing. `keyid` stamps a `kid` (key id) into the token header, which is how verification later knows which key to try, and tokens issued before this change have no `kid` at all, hence the `LEGACY_KID` fallback. `jwt.decode` verifies nothing and the `kid` it returns is attacker-controlled; that is safe here only because it picks between two of your own keys and the signature still has to check out. `algorithms: ['HS256']` stops the token's own header from choosing the algorithm.

4. Deploy with `JWT_SIGNING_KID=v1` unchanged. Nothing changes for users: tokens are still signed with the old key, and both keys now verify. Confirm a token issued before this deploy still returns 200 on an authenticated route before going further.

5. Flip signing: set `JWT_SIGNING_KID=v2` and restart. Note the wall-clock time, call it T. New logins get v2 tokens; tokens issued before T keep working until they expire. Rollback is setting the variable back to `v1`, with no code change and no logouts in either direction.

Steps 4 and 5 are two separate deploys because during a rolling deploy the old and new instances serve traffic at the same time, and an old instance that has never heard of v2 answers a v2 token with a 401. If your API is a single process that stops before the replacement starts (one container, `pm2 restart`, `systemctl restart`), you can do 4 and 5 together.

## After the overlap window

6. At T plus 26 hours or later (the 24 hour expiry, plus margin for clock skew and for a token handed out a second before the flip), delete `JWT_SECRET_V1` and the leftover `JWT_SECRET` from the environment, remove `v1` from `KEYS`, drop the `LEGACY_KID` fallback, and deploy.

7. Scrub the old value everywhere else it lives: `.env` files on other machines, older secret manager versions, CI variables, shell history. If any other system used that same string, rotate that too.

Separately: if step 1 turns up no refresh token flow, every future rotation costs you a full day of dual verification, and short access tokens with refresh tokens would shrink that to minutes. That is a second job.

What I could not check: your repo, your `.env`, and how you deploy. Step 1 is where you find out whether 24 hours really is your longest token lifetime, and step 5 assumes instances overlap during a deploy; either answer coming out differently changes the plan above.

After the flip, call one authenticated endpoint twice, once with a token minted before T and once with a token from a fresh login. Both should return 200.
