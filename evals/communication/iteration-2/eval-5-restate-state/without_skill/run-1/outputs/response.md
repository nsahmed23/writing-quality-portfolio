Step 3 next: run `npx prisma generate` so the generated client picks up the new `status` field.

Then two more:
4. Backfill existing rows: `npx tsx scripts/backfill-listing-status.ts` (sets status from `archivedAt`).
5. Deploy: `npx prisma migrate deploy` in the Cloud Run release step.