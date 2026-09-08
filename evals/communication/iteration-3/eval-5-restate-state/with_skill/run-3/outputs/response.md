Steps 1 and 2 done. Three steps left:

3. Run `npx tsx scripts/backfill-listing-status.ts`: sets `status` to "archived" wherever `archivedAt` is set, since the migration defaulted every row to "active". Seconds to run unless `Listing` has tens of thousands of rows.
4. Check the result with `npx tsx scripts/count-listing-status.ts` (prints row counts per status).
5. Deploy with `npx prisma migrate deploy` in the Cloud Run release step.

Next: run step 3, the backfill script.