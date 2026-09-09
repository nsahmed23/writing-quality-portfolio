2 of 5 done: schema updated, dev migration applied. Next:

3. Run `npx prisma generate` so the generated client includes the new `status` field.
4. Backfill existing rows: `npx tsx scripts/backfill-listing-status.ts` (sets `status` from `archivedAt`).
5. Deploy: `npx prisma migrate deploy` in the Cloud Run release step.
