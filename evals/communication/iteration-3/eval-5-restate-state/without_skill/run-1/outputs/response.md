Steps 1 and 2 are done, so the schema has the `status` column and the dev database has the migration applied (Prisma client regenerated).

Next is step 3, the backfill: run `npx tsx scripts/backfill-listing-status.ts`. It sets `status` to `"archived"` on rows where `archivedAt` is set; every other row already got the `"active"` default from the migration, so this is a one-time catch-up for existing archived listings.

After that, step 4 verifies it: `npx tsx scripts/count-listing-status.ts` prints row counts per status, worth checking that the archived count looks right before you move to step 5, deploying with `npx prisma migrate deploy` in the Cloud Run release step.