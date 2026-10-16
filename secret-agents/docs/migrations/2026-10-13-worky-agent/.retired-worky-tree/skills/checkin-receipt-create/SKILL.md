---
name: checkin-receipt-create
description: Use when the user asks to write a checkin receipt for a single Perforce changelist, or explicitly invokes @skill checkin-receipt-create with a CL number. Examines the changelist's description, file list, and diffs (not just the submit comment) and writes a structured receipt to Checkins/perforce/.
---

# Checkin Receipt Create

Write one checkin receipt for a single Perforce changelist. The point is to examine what actually changed in the diff and summarize it, not to copy the submit comment. Output feeds `checkin-rollup` and the annual performance review.

## Input

One argument: a changelist number (e.g. `7399`). If none is given, ask for it; do not guess.

## Vault Layout

Resolve the vault root from this skill's base directory: `<skill base dir>\..\..\..` (the skill sits at `<worky root>\Agent\skills\checkin-receipt-create`).

- Output: `<vault>\Checkins\perforce\YYYY\YYYY-MM\CK-<cl>-<slug>.md`, where `YYYY`/`YYYY-MM` come from the changelist's date. Create the month folder if it does not exist.
- Template: `<vault>\Templates\Checkin Receipt Template.md`.
- Cost ledger: `<vault>\Receipts\cost-ledger.csv`.

## Perforce Access

- Confirm the client is logged in: `p4 info` must return a `User name`. If not, stop and tell the user to run `p4 login`.
- The logged-in user is the author. Do not hardcode a username.

## Procedure

1. **Fetch the summary:** `p4 describe -s <cl>`. Parse the header line `Change <cl> by <user>@<client> on YYYY/MM/DD HH:MM:SS`, the indented description block, and the `Affected files ...` list (lines of the form `... <depot-path>#<rev> <action>`).
2. **Classify noise.** Mark `noise: true` and write a stub (see Noise CLs) if the description matches a stream-creation CL (`Stream //...` as the whole comment) or a binary-archive CL (`[CL ####] Updated binaries`), OR if every affected file is a binary (`.uasset`, `.umap`, `.png`, `.jpg`, `.mp4`, `.zip`, `.dll`, `.exe`, `.pak`, `.msi`, `.dmg`, etc.). Otherwise continue.
3. **Fetch the diffs:** `p4 describe <cl>` (no `-s`) returns the description, file list, and a `Differences ...` section with per-file unified diffs for text files. Binary files show only their header, no diff.
4. **Examine the diffs.** Read each text diff and determine what actually changed. Do not rely on the submit comment alone. If a file's purpose is unclear from the diff, note it in Review Notes rather than guessing.
5. **Compute stats.** `files` = number of affected files. `lines_added` / `lines_removed` = count of diff lines beginning with `>` / `<` across all text diffs, excluding `---` separator lines and `==== <path> (text) ====` headers. Example (Git Bash): `p4 describe <cl> | grep -cE '^>'` and `grep -cE '^<'`. Set both to `0` for a noise stub.
6. **Derive frontmatter fields:**
   - `date`: the CL date as `YYYY-MM-DD`.
   - `author`: the user from the header.
   - `client`: the client from the header.
   - `stream`: the top-level stream from the depot paths (e.g. `//laika-tools/scouting-tool-main`); use `main` if there is a single obvious stream or none.
   - `tags`: pick from the competency tags **A** (Accountability), **C** (Communication), **PO** (Process Optimization), **P** (Productivity), **T** (Teamwork & Collaboration). Choose the ones the change evidences. Default to `[A]` if unsure.
   - `arc`: the initiative this CL belongs to (e.g. `ScoutingApp/Session`, `Builder2`, `MacCoverage`, `UGS`, `HeadlessMac`, `ARCM`, `AgentHarness`). Use the existing arc names from `performance-review-2026-receipts-analysis.md` where they match; otherwise coin a concise `Area/Detail`.
7. **Write the receipt** using exactly the sections and heading levels in `Templates\Checkin Receipt Template.md`. Fill every section; use `- N/A` where a section genuinely does not apply. Keep bullets concise and factual.
8. **Append a cost-ledger row** to `<vault>\Receipts\cost-ledger.csv` (create with header if missing): `date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd` with `topic_slug` = `CK-<cl>`. Never invent token figures; label estimates as estimates.

## Filename Convention

`CK-<cl>-<slug>.md` where `<slug>` is a short lowercase-hyphenated topic (max ~4 words) derived from the change, e.g. `CK-7399-unity-build-fix.md`. The CL number is the stable key; the slug is for humans.

## Idempotency

Before doing any work, check whether `CK-<cl>-*.md` already exists in the target month folder (match by CL number, not slug). If it does, print `Checkin receipt for CL <cl> already exists: <path> - skipping.` and stop. Never overwrite an existing receipt.

## Noise CLs

For a noise CL, write a minimal receipt: the full frontmatter (with `noise: true`, `files` set, `lines_added`/`lines_removed` = 0, `tags: []`, `arc` best-effort), then only:

```markdown
## Summary
- <one line: what kind of mechanical CL this is, e.g. "Stream creation for //laika-tools/simulcam-s" or "Binary archive for CL 7218">.

## Review Notes
- Noise CL (stream/binary). No substantive diff examined.
```

Omit the other sections. This keeps the record complete and cheap while letting rollups exclude or count it.

## Output

After saving, return only:
- the final file path,
- one line: `CL <cl> (<date>, <files> files, +<added>/-<removed>) - <arc>`,
- the `## Suggested Status Bullets` section verbatim (so the status bullet is immediately usable).

Do not echo the rest of the receipt body in chat - the file is the deliverable.
