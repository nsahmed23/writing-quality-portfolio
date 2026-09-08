Good, steps 1 and 2 are done. Next is step 3: regenerate the Prisma client so it picks up the new field.

```
npx prisma generate
```

Two steps left after that: backfill existing rows with `npx tsx scripts/backfill-listing-status.ts` (sets `status` from `archivedAt`), then deploy with `npx prisma migrate deploy` in the Cloud Run release step.
