Both done. Next is step 3, the backfill script:

```
npx tsx scripts/backfill-listing-status.ts
```

It sets `status` to `"archived"` on rows where `archivedAt` is set; every other row already has `"active"` from the migration's default, so those are untouched.

After that, step 4 verifies it:

```
npx tsx scripts/count-listing-status.ts
```

That prints row counts per status, so you can check the split before moving on to the Cloud Run deploy step.