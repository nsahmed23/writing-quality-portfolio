Steps 1 and 2 of 5 done (schema field added, dev migration applied). Next: run `npx prisma generate` so the generated client includes the new `status` field.

Two steps remain after that:
4. Backfill existing rows: `npx tsx scripts/backfill-listing-status.ts` (sets `status` from `archivedAt`)
5. Deploy: `npx prisma migrate deploy` in the Cloud Run release step
