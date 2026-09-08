Steps 1 and 2 are done, so the `status` column is in the schema with its `"active"` default, and the dev database and Prisma client are current.

Next is step 3, the backfill: run `npx tsx scripts/backfill-listing-status.ts`. It sets `status` to `"archived"` wherever `archivedAt` is set, since the migration left every existing row on the `"active"` default.

After that, step 4 checks the result with `npx tsx scripts/count-listing-status.ts` (row counts per status), and step 5 deploys with `npx prisma migrate deploy` in the Cloud Run release step.
