Steps 1 and 2 done: schema updated, dev database migrated, Prisma client regenerated. Next: step 3 of 5, backfill existing rows.

Run `npx tsx scripts/backfill-listing-status.ts` (seconds, unless `Listing` has an unusually large number of rows). It sets `status` to "archived" wherever `archivedAt` is set; every other row already carries the "active" default the migration gave it.

Steps 4 (verify counts) and 5 (deploy) come after that. Run the backfill script now.