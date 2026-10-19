# Handbag of Holding — Agentic Skills & Harness Wiring

The vocabulary for this repo: a single canonical home for authored agent skills and guidance, distributed to every machine by Obsidian sync and wired into each AI coding harness by links. Terms below are used by the skills, runbooks, and specs; keep them exact.

## Language

**Vault**:
This repository as an Obsidian-synced directory — the canonical home of authored skills and guidance, present on every machine.
_Avoid_: canonical root, shared repo, worky

**Agent Root**:
The `secret-agents/` directory inside the vault, marked by `.agent-root.json`; the directory harness adapters point at.
_Avoid_: skills repo, shared-agent directory

**Pointer File**:
The one-line per-machine file `~/.agents/root` holding the vault's local absolute path. The only per-machine configuration; every other path derives from it.

**Harness**:
An AI coding agent environment that discovers and runs skills — Claude Code, Codex, or Copilot.
_Avoid_: platform, IDE, agent (ambiguous)

**Adapter**:
A harness-owned file or link that points back at the agent root (instruction links, skill links). Adapters are per machine and per harness; content is never copied into them.

**Mixing Directory**:
A harness skills directory that must hold authored skills and foreign packs side by side. Always a real directory containing per-skill links — never a whole-directory junction into the vault.

**Write-Through**:
The failure where a whole-directory junction lets a third-party installer write foreign files into the vault. The mixing-directory rule exists to prevent it; the vault-purity check detects it.

**Pack**:
A named group of skills with one origin and one install mechanism: `mine` (authored, lives in the vault) or a foreign pack (superpowers, mattpocock-skills) installed per machine via its official mechanism.
_Avoid_: skill glob, bundle

**Official Install**:
Installing a foreign pack through the mechanism its author publishes (plugin marketplace, `npx skills`), giving it native version metadata. The only permitted way foreign skills reach a machine.
_Avoid_: vendoring, copying skills

**Manifest**:
`secret-agents/packs.json` — the declaration of every expected pack, its install mechanism per harness, and the skill names it must provide. What "all skills ready" is diffed against.

**Preflight**:
The `ready-player-one` check run before an expensive batched prompt. Offline, deterministic, binary verdict.

**Ready**:
The preflight verdict meaning every applicable check passed after autofix; the batched prompt may run. There are no partial passes.

**Autofix**:
A repair the preflight applies itself because it is safe: create-only links, additive settings, writing the pointer file. Never overwrites, deletes, elevates, or touches the network.

**Remediation**:
A numbered instruction the preflight emits for anything it must not fix itself — exact command, exact path, tailored to the detected harness and OS.

**Session-Visible Skills**:
The skill list a harness snapshotted at session start. Diverges from the filesystem when skills change mid-session; only a fresh session re-registers, though a skill file can be read into the current session as a stopgap.

**Version Cache**:
`~/.agents/versions.json`, written by `update-agent-stack` (the only network-touching skill), read by the preflight to report installed versions and freshness offline.
