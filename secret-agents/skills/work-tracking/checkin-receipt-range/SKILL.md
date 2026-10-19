---
name: checkin-receipt-range
description: "Use when the user asks to backfill or generate checkin receipts for every Perforce changelist in a date range, or explicitly invokes @skill checkin-receipt-range with start and end dates. Drives checkin-receipt-create across all submitted CLs in the window, idempotently."
---

# Checkin Receipt Range

**Category:** Reporting · **Updated:** 2026-10-16

Generate checkin receipts for every submitted changelist the logged-in user made within a date range, by driving `checkin-receipt-create` for each CL. This is the mass-populate engine for backfilling `Checkins/perforce/`.

## Input

Two required date arguments: `start YYYY/MM/DD` and `end YYYY/MM/DD` (inclusive). Example: `@skill checkin-receipt-range start 2026/01/01 end 2026/10/12`. If either is missing or malformed, print usage and stop; do not guess.

## Vault Layout

Resolve `<vault>` using [Worky data vault paths](../../../runbooks/worky-vault-paths.md) before reading inputs or creating outputs. Pass the same resolved vault to each `checkin-receipt-create` invocation.

## Perforce Access

- Confirm `p4 info` returns a `User name`; if not, stop and tell the user to `p4 login`.
- The author is the logged-in user.

## Listing Changelists

The `p4 changes` spec-form date filter is unreliable on this server. Use the reliable pattern:

1. Run `p4 changes -u <user>` (no `-t`, no spec). This returns every CL for the user, newest first, one per line:
   `Change <cl> on YYYY/MM/DD by <user>@<client> [*pending*] '<comment>'`
2. Parse each line into: `cl` (number), `date` (YYYY/MM/DD), `status` (pending if the line contains `*pending*`, else submitted), `client`, `comment`.
3. Keep only lines where `status` is **submitted** AND `start <= date <= end`. (Pending CLs are excluded from backfill by default; mention how many pending CLs were skipped.)
4. Sort the kept CLs ascending by CL number (oldest first) so receipts are produced in chronological order.

## Execution

- For each CL in order, invoke `checkin-receipt-create` for that CL number. Follow that skill fully (it handles noise classification, diffs, stats, idempotency, and the cost-ledger row).
- **Idempotency is the resume mechanism.** `checkin-receipt-create` skips any CL that already has a receipt, so an interrupted run can be re-invoked over the same range and will only do the remaining CLs. Do not pre-check for existence here; let the single-CL skill own that.
- **Chunking:** if the range spans more than ~40 CLs, process in monthly sub-batches and report progress after each batch (e.g. `2026/03: 34 done, 2 noise, 0 skipped-existing`). This keeps long backfills resumable and gives the user visibility.
- **Error handling:** if `p4 describe` fails for a CL (e.g. it was deleted), log `CL <cl>: describe failed (<reason>) - skipping`, continue with the next CL, and list all failures in the final summary. Never abort the whole run on one bad CL.

## Cost Guidance

This is the expensive path (full diffs per CL). Recommend a mid-tier model (Sonnet-class) for months with substantive code CLs. For a month that is mostly mechanical (stream/binary) CLs, a low-tier model is sufficient. State the recommended model before starting a large run so the user can choose.

## Output

After the run, print a summary:
- the date range processed,
- total submitted CLs in range,
- receipts written (new), receipts skipped (already existed), noise stubs written, and failures,
- the output folder(s) under `Checkins/perforce/`.

Do not echo individual receipt bodies.
