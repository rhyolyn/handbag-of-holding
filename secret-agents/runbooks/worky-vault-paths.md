# Worky Workspace Resolution

Shared skills are portable. Worky data is selected once per invocation by the `work-tracking/v1` resolver; skills request named locations and never join vault paths themselves.

Validate before reading inputs or creating output:

```text
python -m secret_agents_work_tracking workspace check [--config PATH | --vault PATH]
```

The resolver chooses configuration in this order: explicit `--config` or `--vault`, `WORKY_WORKSPACE_CONFIG`, `WORKY_VAULT_ROOT/work-tracking.yaml`, then the sibling `../../worky` of the resolved agent root. The selected configuration must remain inside the selected vault, use schema `work-tracking/v1`, and define the `America/Los_Angeles` timezone.

Named locations are `receipts`, `daily_notes`, `perforce_checkins`, `git_checkins`, `status_reports`, `monthly_reports`, `annual_reviews`, `templates`, `imports`, and `ledgers`. Required inputs that are absent, malformed configuration, or a location outside the tracking root are actionable failures; report the named location and recovery action. Only create an output directory after validation. Never create a fallback vault in the repository.

Evidence uses the common fields `kind`, `occurred_start`, `occurred_end`, `source_system`, `source_id`, `initiatives`, `tags`, `status`, and `sources`. Equal stable identity plus normalized content is a skip; equal identity with different material is a conflict, never an overwrite. Operational ledgers remain under `ledgers` and are not accomplishment evidence.

This runbook is used by all canonical work-tracking workflows. It does not migrate Worky data, configure a scheduler, or replace Perforce or GitHub authentication.
