---
name: agent-preflight
description: Pre-flight environment check before executing a batched prompt or complex task. Detects harness (claude/codex/copilot) and OS (win/lin/mac), runs harness-specific checks, and outputs "ready" or a tailored remediation list. No partial passes — every check must pass before you proceed.
---

# Agent Preflight

Run this skill before handing a batched prompt to any model. It takes under 10 seconds and has a binary outcome: `ready` or a remediation list. No partial passes — every check must pass before you proceed.

Treat this file as a strict output contract, not guidance. If a section says `Print:`, reproduce that block exactly in the final output for the current run.

## How to run

**Step 0 — Detect harness and OS first.** Every check that follows depends on this context. Run detection, record the result, then run each check in order. Print the result line immediately after each check. At the end, print the summary. If a harness-specific check has no known fix, leave a harness-specific placeholder instead of inventing a generic answer.

---

## Step 0 — Detect harness and OS

### 0a — Detect harness

Look for the following signals in order. Stop at the first match.

| Harness | Signal |
|---------|--------|
| **claude** | `CLAUDE_CODE_SESSION_ID` env var is set — OR — a `.claude/` directory exists in the workspace — OR — this skill was invoked via `/agent-preflight` |
| **codex** | `CODEX_HOME` or `CODEX_CLI_PATH` is set — OR — a `~/.codex/` directory exists — OR — the process environment contains `OPENAI_*` vars with no Claude signal |
| **copilot** | `GITHUB_COPILOT_*` env var is set — OR — the agent context identifies as GitHub Copilot |

If no signal matches, assume **claude** and note uncertainty in the output.

**Run (try PowerShell first; fall back to bash if PowerShell is unavailable):**

```powershell
# PowerShell (Windows/cross-platform pwsh)
$harness = if ($env:CLAUDE_CODE_SESSION_ID -or (Test-Path ".claude")) { "claude" }
           elseif ($env:CODEX_HOME -or $env:CODEX_CLI_PATH -or (Test-Path "$env:USERPROFILE\.codex")) { "codex" }
           elseif ($env:OPENAI_API_KEY -and -not $env:ANTHROPIC_API_KEY) { "codex" }
           elseif ($env:GITHUB_COPILOT_TOKEN -or $env:GITHUB_COPILOT_CHAT_CONTEXT) { "copilot" }
           else { "claude (assumed)" }
Write-Output "harness: $harness"
```

```bash
# bash (Linux/Mac fallback)
if [ -n "$CLAUDE_CODE_SESSION_ID" ] || [ -d ".claude" ]; then harness="claude"
elif [ -n "$CODEX_HOME" ] || [ -n "$CODEX_CLI_PATH" ] || [ -d "$HOME/.codex" ] || { [ -n "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; }; then harness="codex"
elif [ -n "$GITHUB_COPILOT_TOKEN" ] || [ -n "$GITHUB_COPILOT_CHAT_CONTEXT" ]; then harness="copilot"
else harness="claude (assumed)"
fi
echo "harness: $harness"
```

### 0b — Detect OS

```powershell
# PowerShell
$os = if ($env:OS -eq "Windows_NT" -or $env:WINDIR) { "win" }
      elseif ($IsLinux) { "lin" }
      elseif ($IsMacOS) { "mac" }
      else { "unknown" }
Write-Output "os: $os"
```

```bash
# bash
case "$(uname -s)" in
  Linux*)  os="lin" ;;
  Darwin*) os="mac" ;;
  *)       os="win" ;; # MINGW/Cygwin on Windows
esac
echo "os: $os"
```

### 0c — Report active model

State the model you are currently running on only if the harness exposes a trustworthy session model string. Do not guess, normalize, or infer the exact model name from unrelated env vars or product branding. If no exact model string is available, print `unknown` and mark the status as unable to verify.

Then print the recommendation for the detected harness:

| Harness | Recommended model | Reason |
|---------|-------------------|--------|
| **claude** | `claude-haiku-4-5` | mechanical checklist — no reasoning needed |
| **codex** | `o4-mini` | mechanical checklist — no reasoning needed |
| **copilot** | _(use the lightest model available)_ | same |

Print:
```
🤖 Model: claude-haiku-4-5  ✅ optimal  (or ⚠️ over-specced — restart on haiku to save tokens)
```

(Replace with your actual model and the appropriate status. If the exact model is unavailable, print `unknown` and use `⚠️ unable to verify optimal` instead of claiming optimal.)

Print:
```
🔍 Detected: harness=claude  os=win
```

(Replace values with what was detected.)

---

## Check 1 — Skill is visible

**This check passes by definition if the skill is executing.**

**If the skill is NOT executing** (you are reading this file directly because the skill command failed to load), use the fix for your harness:

### Claude
> Skills are registered in `~/.claude/AGENTS.md` (global) and/or `.claude/AGENTS.md` (project).
> Open the relevant file and verify this skill is listed. If missing, add an entry for it.
> After updating, restart the Claude Code session and re-run `/agent-preflight`.

| OS | Fix |
|----|-----|
| win | Add `agent-preflight` to `%USERPROFILE%\.claude\AGENTS.md` or `.claude\AGENTS.md`, then restart Claude Code and re-run `/agent-preflight`. |
| lin | Add `agent-preflight` to `~/.claude/AGENTS.md` or `.claude/AGENTS.md`, then restart Claude Code and re-run `/agent-preflight`. |
| mac | Add `agent-preflight` to `~/.claude/AGENTS.md` or `.claude/AGENTS.md`, then restart Claude Code and re-run `/agent-preflight`. |

### Codex
> Codex discovers skills from the shared user skills path wired to `<agent-root>/skills` or from a direct Codex skills path when configured locally.
> Verify `agent-preflight` is present as `%USERPROFILE%\.agents\skills\agent-preflight\SKILL.md`, `~/.agents/skills/agent-preflight/SKILL.md`, `~/.codex/skills/agent-preflight/SKILL.md`, or as a junction/symlink into `<agent-root>/skills/agent-preflight`.
> If missing, add the link, then restart Codex and re-run `/agent-preflight`.

| OS | Fix |
|----|-----|
| win | Add the `agent-preflight` skill link to `%USERPROFILE%\.agents\skills\agent-preflight` or `%USERPROFILE%\.codex\skills\agent-preflight`, then restart Codex and re-run `/agent-preflight`. |
| lin | Add the `agent-preflight` skill link to `~/.agents/skills/agent-preflight` or `~/.codex/skills/agent-preflight`, then restart Codex and re-run `/agent-preflight`. |
| mac | Add the `agent-preflight` skill link to `~/.agents/skills/agent-preflight` or `~/.codex/skills/agent-preflight`, then restart Codex and re-run `/agent-preflight`. |

### Copilot
> _(Placeholder - GitHub Copilot skill registration mechanism is still unknown. Verify this skill is accessible to the Copilot agent and re-run.)_

| OS | Fix |
|----|-----|
| win | Use the Copilot skill registration path or workspace setting for Windows once it is known; keep `agent-preflight` accessible, then re-run the preflight. |
| lin | Use the Copilot skill registration path or workspace setting for Linux once it is known; keep `agent-preflight` accessible, then re-run the preflight. |
| mac | Use the Copilot skill registration path or workspace setting for macOS once it is known; keep `agent-preflight` accessible, then re-run the preflight. |

Print:
```
✅ Check 1: skill is visible
```

---

## Check 2 — Execution trust covers all contexts

This check is harness-specific:

- **claude:** verify permission mode
- **codex:** verify project trust
- **copilot:** placeholder until the agent's trust/approval knob is known

**Skip the harnesses that do not apply.**

### Claude

Agents spawned in worktrees (sibling directories with no `.claude/settings.json`) fall back to global settings. Both the project and global settings must have `defaultMode: dontAsk` for fully autonomous execution.

### Windows (PowerShell)

```powershell
$proj = (Get-Content .claude/settings.json -ErrorAction SilentlyContinue | ConvertFrom-Json)
$projMode = $proj.permissions.defaultMode

$global = (Get-Content "$env:USERPROFILE\.claude\settings.json" -ErrorAction SilentlyContinue | ConvertFrom-Json)
$globalMode = $global.permissions.defaultMode

Write-Output "project defaultMode: $projMode"
Write-Output "global defaultMode:  $globalMode"
```

### Linux / Mac (bash)

```bash
proj_mode=$(python3 -c "import json,sys; d=json.load(open('.claude/settings.json')); print(d.get('permissions',{}).get('defaultMode','missing'))" 2>/dev/null || echo "missing")
global_mode=$(python3 -c "import json,sys; d=json.load(open(os.path.expanduser('~/.claude/settings.json'))); print(d.get('permissions',{}).get('defaultMode','missing'))" 2>/dev/null || echo "missing")
echo "project defaultMode: $proj_mode"
echo "global defaultMode:  $global_mode"
```

**Pass:** both values are `dontAsk`.

**On failure — project settings missing or wrong:**

| OS | Fix |
|----|-----|
| win | Add `"defaultMode": "dontAsk"` to `.claude\settings.json` under the `permissions` key. |
| lin | Add `"defaultMode": "dontAsk"` to `.claude/settings.json` under `permissions`. |
| mac | Add `"defaultMode": "dontAsk"` to `.claude/settings.json` under `permissions`. |

**On failure — global settings missing or wrong:**

| OS | Fix |
|----|-----|
| win | Add `"defaultMode": "dontAsk"` to `%USERPROFILE%\.claude\settings.json` under `permissions`. Required for worktree agents. |
| lin | Add `"defaultMode": "dontAsk"` to `~/.claude/settings.json` under `permissions`. Required for worktree agents. |
| mac | Add `"defaultMode": "dontAsk"` to `~/.claude/settings.json` under `permissions`. Required for worktree agents. |

Print:
```
✅ Check 2: permission mode is dontAsk (project ✓, global ✓)
```
or
```
❌ Check 2: [describe what is missing]
```
or
```
⏭️ Check 2: skipped (harness=codex — not applicable)
```

### Codex

Codex should trust the current project explicitly so the session does not stop on approval prompts. Check `~/.codex/config.toml` for a matching `[projects.'<current path>']` entry with `trust_level = "trusted"`.

**Windows (PowerShell):**

```powershell
$project = (Get-Location).Path.ToLowerInvariant()
$config = Get-Content "$env:USERPROFILE\.codex\config.toml" -Raw -ErrorAction SilentlyContinue
$pattern = "(?ms)\[projects\.'$([regex]::Escape($project))'\]\s*trust_level\s*=\s*""trusted"""
$trusted = $config -and ($config.ToLowerInvariant() -match $pattern)
Write-Output "project path: $project"
Write-Output ("trust level: " + ($(if ($trusted) { "trusted" } else { "missing or not trusted" })))
```

**Linux / Mac (bash):**

```bash
project=$(pwd | tr '[:upper:]' '[:lower:]')
trusted=$(python3 - <<'PY'
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    print("missing")
    raise SystemExit(0)
cfg_path = Path.home() / ".codex" / "config.toml"
if not cfg_path.exists():
    print("missing")
    raise SystemExit(0)
cfg = tomllib.loads(cfg_path.read_text())
projects = cfg.get("projects", {})
current = str(Path.cwd()).lower()
for key, value in projects.items():
    if key.lower() == current:
        print(value.get("trust_level", "missing"))
        break
else:
    print("missing")
PY
)
echo "project path: $project"
echo "trust level: $trusted"
```

**Pass:** the current project is trusted.

**Failure fix:**

| OS | Fix |
|----|-----|
| win | Add `[projects.'<current project path>'] trust_level = "trusted"` to `%USERPROFILE%\.codex\config.toml`, or trust the project in Codex and restart the session. |
| lin | Add `[projects.'<current project path>'] trust_level = "trusted"` to `~/.codex/config.toml`, or trust the project in Codex and restart the session. |
| mac | Add `[projects.'<current project path>'] trust_level = "trusted"` to `~/.codex/config.toml`, or trust the project in Codex and restart the session. |

Print:
```
✅ Check 2: project is trusted
```
or
```
❌ Check 2: current project is not trusted in ~/.codex/config.toml
```
or
```
⏭️ Check 2: skipped (harness=copilot — not applicable)
```

---

## Check 3 — uv health and no locked build artifacts

Both sub-checks must pass.

### 3a — uv resolves

**All harnesses and OSes.**

```powershell
# PowerShell
uv run python -c "print('uv ok')"
```

```bash
# bash
uv run python -c "print('uv ok')"
```

Pass: exits 0 and prints `uv ok`.

**Failure fix:**

| OS | Fix |
|----|-----|
| win | Run `uv self update`. Verify uv is on PATH: `(Get-Command uv).Source`. If missing, install from `https://docs.astral.sh/uv/`. |
| lin | Run `uv self update`. Verify with `which uv`. If missing: `curl -LsSf https://astral.sh/uv/install.sh \| sh` then restart shell. |
| mac | Run `uv self update`. Verify with `which uv`. If missing: `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh`. |

### 3b — No locked build executable

Derive the project exe name from the current directory name (e.g., `ugs` from `c:\git\ugs`). Override if the project's build artifact has a different name.

**Windows (PowerShell):**
```powershell
$PROJECT_EXE = Split-Path (Get-Location) -Leaf
$locked = Get-Process | Where-Object { $_.Name -like "$PROJECT_EXE*" } | Select-Object Name, Id
if ($locked) { $locked | Format-Table }
```

**Linux / Mac (bash):**
```bash
PROJECT_EXE=$(basename "$PWD")
locked=$(pgrep -a "$PROJECT_EXE" 2>/dev/null)
[ -n "$locked" ] && echo "$locked"
```

Pass: no output (no matching processes).

**Failure fix:**

| OS | Fix |
|----|-----|
| win | `Stop-Process -Name $PROJECT_EXE -Force` — or use `python -m pytest` instead of `uv run pytest` to skip the uv build step. |
| lin | `pkill -f "$PROJECT_EXE"` — or use `python -m pytest` to bypass the uv build step. |
| mac | `pkill -f "$PROJECT_EXE"` — or use `python -m pytest` to bypass the uv build step. |

Print:
```
✅ Check 3: uv resolves, no locked executables
```
or
```
❌ Check 3: [describe what failed — uv broken / exe locked with name and PID]
```

---

## Optional prep steps

These are not readiness gates, but they cut down on preventable thrash before a long prompt or build:

- Confirm the repo root with `pwd` or `Get-Location` before starting.
- Run `git status --short` to spot unrelated dirt, untracked files, or accidental worktree drift.
- Verify the active branch if the task could touch release or review-sensitive files.
- Check the project runtime once up front when the task depends on it, for example `python --version`, `node --version`, or `dotnet --info`.
- If the task will build or launch an editor, confirm stale processes are not already holding locks before the first retry.
- On Windows, check `core.longpaths` and path length issues early if the repo has deep output trees or generated assets.

---

## Summary output

The runner must print one of the two templates below exactly, with no extra commentary.

Use the active session model string only if the harness exposes one. If no model string is exposed, print `unknown` and do not claim optimality. Do not infer, rename, or normalize it.

If all applicable checks pass:

```
🤖 Model: <MODEL>  ✅ optimal
🔍 Detected: harness=<harness>  os=<os>

✅ Check 1: skill is visible
✅ Check 2: permission mode is dontAsk (project ✓, global ✓)
✅ Check 3: uv resolves, no locked executables

ready
```

If the exact model string is unavailable, replace the first line with:

```
🤖 Model: unknown  ⚠️ unable to verify optimal
```

If any check fails, print `NOT READY` and a numbered list of required actions — one action per failed check, in order. Be specific: include file paths, exact keys to add, and exact commands to run. Tailor each action to the detected OS and harness.

Example (claude / win, global settings missing):

```
🤖 Model: <MODEL>  ✅ optimal
🔍 Detected: harness=<harness>  os=<os>

✅ Check 1: skill is visible
❌ Check 2: global %USERPROFILE%\.claude\settings.json missing defaultMode:dontAsk — worktree agents will prompt for permissions
✅ Check 3: uv resolves, no locked executables

NOT READY — 1 issue to resolve:

1. Add "defaultMode": "dontAsk" to %USERPROFILE%\.claude\settings.json under "permissions".
   Required so agents spawned in git worktrees inherit auto-approve mode.
   After editing, re-run /agent-preflight to confirm.
```

Example (codex / lin):

```
🤖 Model: <MODEL>  ✅ optimal
🔍 Detected: harness=<harness>  os=<os>

✅ Check 1: skill is visible
✅ Check 2: project is trusted
❌ Check 3: uv not found on PATH

NOT READY — 1 issue to resolve:

1. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh
   Then restart your shell and re-run the preflight.
```

Do not proceed with the batched prompt until the output is `ready`.
