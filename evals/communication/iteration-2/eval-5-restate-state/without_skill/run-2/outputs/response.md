1 and 2 are done. Next:

3. Run `npx prisma generate` so the generated client picks up the new `status` field.
4. Backfill existing rows: `npx tsx scripts/backfill-listing-status.ts` (sets `status` from `archivedAt`).
5. Deploy: `npx prisma migrate deploy` in the Cloud Run release step.