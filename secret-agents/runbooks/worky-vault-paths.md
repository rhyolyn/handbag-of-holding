# Worky Data Vault Paths

Shared skills live in `handbag-of-holding/secret-agents/skills`. Worky's reports, receipts, checkins, templates, and ledgers remain in the Worky data vault. Moving a skill does not move its inputs or outputs.

Resolve `<vault>` once per invocation, using this precedence:

1. The vault path explicitly supplied by the user.
2. `WORKY_VAULT_ROOT`, if configured.
3. The sibling `worky` vault: from `<agent-root>` resolve `../../worky`. For this workspace that is `C:\Users\rhyol\obsidian\worky`.

Verify that the selected directory exists and contains the workflow's required input directories or templates. If it does not, report the missing path and ask for the data-vault location; do not create a replacement data vault inside handbag-of-holding or search unrelated directories. Create output month folders only after resolving the intended vault.

This reference is used by `report-receipt`, `report-cost-analysis`, `report-status`, `report-rollup`, `checkin-receipt-create`, `checkin-receipt-range`, `checkin-rollup`, and `jira-human-ticket-create`. It does not migrate any Worky data or configure harness integrations.
