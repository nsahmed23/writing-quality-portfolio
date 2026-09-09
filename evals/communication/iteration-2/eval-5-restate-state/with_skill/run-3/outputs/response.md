Steps 1 and 2 done (2 of 5): schema updated, dev migration applied. Next: run `npx prisma generate`. `migrate dev` already triggers `generate` at the end, so this may already be satisfied; running it again is safe and confirms `status` shows up on the `Listing` type.

After that, two steps left:
4. Backfill existing rows: `npx tsx scripts/backfill-listing-status.ts` (sets `status` from `archivedAt`).
5. Deploy: `npx prisma migrate deploy` in the Cloud Run release step.