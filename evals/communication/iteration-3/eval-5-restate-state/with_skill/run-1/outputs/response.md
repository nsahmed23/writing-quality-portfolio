Steps 1 and 2 done: column added, dev migration run. Step 3 of 5 next: backfill existing rows.

Run `npx tsx scripts/backfill-listing-status.ts` (a few seconds unless `Listing` has millions of rows). It sets status to "archived" wherever `archivedAt` is set; every other row already has "active" from the migration default.

Two steps left after that: step 4 checks the counts with `npx tsx scripts/count-listing-status.ts`, and step 5 deploys with `npx prisma migrate deploy` from the Cloud Run release step, later rather than now.

Run the backfill script now.