# HUMANS.md — Getting More From Claude for Fewer Tokens

Practical instructions for working with Claude Code efficiently, written from the analysis of the 2026-07-10 UGS session (see `Receipts/WR-2026-07-10_ugs-ui-v1-review-remediation-session.md`). Everything here is a thing *you* control from the prompt or config — no agent goodwill required.

---

## The cheat sheet

| You want | Say / do this |
|---|---|
| Stop it reading a whole huge file | "Grep for X in `<file>`, then read only that section" |
| Cheap model for a discrete chunk of work | "Dispatch that to a **sonnet/haiku subagent**" (not `/model`) |
| No babysitting between phases | Put model choices *in the plan doc*; batch instructions; grant autonomy up front |
| Fewer round-trips | One message = goal + constraints + definition of done + "then commit and stop" |
| A cheap next session | Ask for an artifact (plan/README/receipt) at the milestone, then start fresh |
| Zero-token automation | Hooks in `settings.json` (formatting, test-on-save) — the harness runs them, no model involved |
| Long task without waiting | "Run it in the background; meanwhile do <other thing>" |
| A recurring workflow captured once | Make it a skill (loads only when used — unlike `CLAUDE.md`, which taxes every turn) |
| Catch misdirection early | "Plan first; don't touch code until I approve" |

The two facts that explain most of this document:

1. **Context is rented, artifacts are owned.** Every turn re-sends the whole conversation. A long session makes *every* future instruction expensive. A committed document costs once and makes any future session (on any model) cheap.
2. **The prompt cache is a prefix match with a ~5-minute TTL, and it is per-model.** Rapid follow-up turns are ~10% price. A gap over ~5 minutes, or a model switch, means re-reading the entire history at full price.

---

## 1. Controlling what gets read (your biggest single lever)

The most expensive mistake in the analyzed session was one unbounded file read: a 3,565-line plan file cost ~25K tokens when the needed section was ~90 lines (~2–3K with a targeted read). That's a 10× overspend from one ambiguous instruction.

Claude's Read tool takes an offset and a line limit, and Grep can locate a section first. You can direct this explicitly:

**Instead of:**
> review task 15 against the plan

**Say:**
> Review task 15 against the plan — read only the Task 15 section of the plan file (grep for the header, don't open the whole file; it's 3,500 lines).

More patterns that work verbatim:

- *"Read only lines 200–300 of `foo.py`."*
- *"Find where `sync_latest` is defined and read just that function and its callers."*
- *"Don't read the test files; trust the summary in the receipt."*
- *"Before reading anything, tell me which files you plan to open and how much of each."* (use sparingly — it adds a round trip, but it's good for auditing habits)

And the standing version, once in `CLAUDE.md` so you never have to say it again:

```markdown
- Never open a file >500 lines without a line range. Grep/locate first, then ranged Read.
- Reference docs (plans, specs): read only the section relevant to the current task.
```

Related: screenshots and images cost ~1–1.5K tokens each. "Compare against the reference screenshot **once** and reuse your conclusions" is a legitimate instruction.

---

## 2. Model switching without babysitting

### The counterintuitive part first

**Switching the main session's model to something cheap "just for the commit" usually costs more than staying put.** The prompt cache is per-model. Worked example with a 100K-token session history:

| Action | Cost |
|---|---|
| Commit turn on Fable 5, warm cache | 100K × $10/M × ~0.1 (cache read) ≈ **$0.10** + a few cents of output |
| Same turn after `/model haiku` | 100K × $1/M **uncached** = $0.10, *plus* the switch back to Fable re-reads 100K at $10/M = **$1.00+** |

The commit itself is ~100 output tokens — half a cent on any model. The expensive thing is never the commit; it's the history the commit rides on. So:

- **Don't** switch the main-thread model per-action. It's the worst of both worlds.
- **Do** switch at *phase boundaries* — `/model` is the right tool when you're starting a new stretch of mechanical work and the old context is no longer needed (better yet, new session, next point).

### The three mechanisms that actually work

**A. Subagents with a model override (zero interaction once instructed).**
The Agent tool accepts `model: "haiku" | "sonnet" | "opus" | "fable"`. Subagents start with a *fresh, small* context, so a cheap model there is pure savings — no cache penalty, because nothing is being switched. This is the official pattern (Anthropic's own docs: "spawn a subagent with the cheaper model for the sub-task; keep the main loop on one model").

Say it once per session — or once forever in `CLAUDE.md`:

> Dispatch plan-conformance reviews and mechanical verification to **sonnet** subagents. Reserve the session model (or opus) for architecture reviews and anything adversarial.

In the analyzed session, the Task 15 review subagent burned ~45K tokens at top-tier pricing on what was mostly "run the tests and diff against the plan" — a sonnet override would have cut that cost ~70% with little quality risk.

**B. Model recommendations baked into the plan document.**
This is what the UGS plans do, and it's the full answer to "I don't want to babysit every phase": each task in the plan carries its own model recommendation, tiered by *residual ambiguity* (how likely the plan needs on-the-spot revision), not by importance. Then execution — whether subagent-per-task or a human kicking off sessions — inherits the routing decision with zero further interaction. You made the model decisions once, at planning time, when you had the most information.

Rule of thumb for writing those recommendations:
- **Top tier** (opus/fable): the plan itself might need revising mid-task — threading/lifecycle, breaking API migrations, visual judgment.
- **Mid tier** (sonnet): fully specified tasks; the model transcribes and verifies.
- **Bottom tier** (haiku): copy-in guard tests, checkbox flips, mechanical reruns.

**C. Separate cheap sessions for cheap phases.**
Doc chores, batched commits, changelog updates: start a *new* session on a cheap model, point it at the artifact ("read the receipt, then do X"). Cold-start on 3K tokens of receipt beats warm-continuation on 100K tokens of history whenever the history isn't actually needed.

**Decision rule:** follow-up within minutes and needs the context → stay in-session (cache is warm, even on the expensive model). Work is discrete and self-describing → subagent with model override. New phase, old context not needed → new session, cheapest adequate model, fed by an artifact.

### What needs no model at all

Deterministic post-work — format on save, run tests after edits, append commit trailers — belongs in **hooks** (`settings.json`). The harness executes hooks directly; zero tokens, perfect reliability. If you find yourself telling the agent "always run ruff after editing," that's a hook, not an instruction.

---

## 3. Being less conversational (batching and autonomy)

Every message you send re-reads the whole history (cached or not, it's latency and money) and every question the agent asks you back doubles that. Two fixes:

### Batch the whole intent into one message

**Instead of** (4 turns, 4 context re-reads):
> review task 16
> *(review arrives)* ok have codex fix it
> *(fix lands)* re-review
> looks good, commit

**Say** (1 turn):
> Review task 16 against the plan. If there are Critical/Important findings, list them as a punch list and stop. If only minors, note them and commit. Don't ask me anything a reasonable senior engineer would decide themselves.

The template that covers most tasks:

```
<goal — one sentence>
<constraints — what not to touch, what conventions apply>
<definition of done — tests pass? committed? doc updated?>
<autonomy grant — "decide X yourself", "don't ask unless destructive">
<stop condition — "then stop", "then give me the TLDR only">
```

### Kill the permission round-trips

Claude ends turns with "Want me to…?" when it isn't sure it has authority. Grant it in advance, narrowly:

- *"Commit after each green test run without asking."*
- *"Fix any lint fallout from this change without checking in."*
- *"If the reviewer's finding is a one-liner, apply it; only stop for design-level findings."*

And the standing version for `CLAUDE.md`:

```markdown
- Proceed without asking for reversible actions within the stated task. Ask only for
  destructive/irreversible actions or genuine scope changes.
- End responses with the outcome, not an offer. No "Shall I...?" for work already implied.
```

### The 5-minute rule

Consecutive quick messages ride the prompt cache (~10% input price). If you know you'll have three follow-ups, send them promptly or — better — anticipate them in one message. A "resume" after lunch is a full-price re-read of everything; that's the moment to consider whether a fresh session + artifact is cheaper than resuming.

---

## 4. Session lifecycle: when to cut and run

Long multi-day sessions (like the analyzed one) accrue a tax: every turn pays for all prior turns, and summarization/compaction degrades detail. The pattern that works:

1. **End every milestone with an artifact.** "Write the receipt / update the plan / commit the README" — that *is* the handoff. The analyzed session did this well: the 1,800-line remediation plan makes every future executor session cheap and model-agnostic.
2. **Start the next phase fresh**, pointing at the artifact: *"Read `docs/plans/<plan>.md` and execute Task 3."* A fresh session that reads 5K tokens of plan beats a continued session dragging 150K of history it no longer needs.
3. Natural cut points: after a review lands, after a plan is written, after a milestone commits. If you're about to say "now for something different" — new session.
4. Use memory/`CLAUDE.md` for durable *preferences*, artifacts for durable *state*. Don't use conversation history as a database.

---

## 5. Prompting for quality (same tokens, better output)

Two findings from this session worth stealing:

**Frame reviewers against parroting.** The principal review was told the known issues *and* instructed to "assess severity fresh, don't parrot." Result: a known "polish item" got correctly re-graded to Critical with a reproduction. If you feed context to a reviewer, always add the independence clause — otherwise you get your own opinions back, formatted.

**Give the reason, not just the request.** *"I'm the principal engineer testing you blind; this code must be readable/maintainable/expandable by a wider team"* produced a materially different review than "review this" would have. One sentence of intent buys targeting that no amount of instruction detail replicates.

**Ask for the verdict shape you want.** "Ready to proceed: Yes/No/With-fixes, plus reasoning" forces a decision instead of a hedge. Same for "TLDR first, detail after."

**For large or ambiguous work, ask for the plan before the work.** "Plan first, don't touch code until I approve" (or plan mode) costs one round-trip and is the cheapest possible place to catch misdirection — redirecting a plan costs hundreds of tokens; redirecting a half-built implementation costs the whole implementation.

---

## 6. Where should a standing instruction live?

You have five places to put durable knowledge, and they have very different cost profiles. Picking the right one is the difference between paying for an instruction once and paying for it every single turn.

| Mechanism | Loaded | Costs tokens | Right for |
|---|---|---|---|
| **`CLAUDE.md`** | Every session, every turn | **Yes, always** — it's part of the rented context | Short, universal rules (the block in §7). Keep it lean; every line here taxes every future turn. |
| **Skill** (`SKILL.md`) | Only when invoked / triggered | Only on use | Multi-step recurring *workflows* (like `work-receipt-create`). Long content belongs here, not in CLAUDE.md — progressive disclosure is the point. |
| **Hook** (`settings.json`) | Never touches the model | **Zero** | Deterministic if-this-then-that: format after edit, run tests after save, commit trailers. If it needs no judgment, it needs no model. |
| **Memory** | Recalled when relevant | Small | Facts about *you* and standing preferences ("prefers tables", "works across two machines"). |
| **Committed artifact** (plan/receipt/README) | When pointed at | Only on use | Project *state* and decisions. The handoff currency between sessions. |

Rules of thumb:
- Said it twice in prompts → promote to `CLAUDE.md` (if one line) or a skill (if a procedure).
- Watching the agent do the same mechanical follow-up every time → hook.
- Explaining project history to a new session → you needed an artifact; write one now.
- **Skill hygiene** (today's lesson): never hardcode machine-specific absolute paths in a skill — resolve relative to the skill's own base directory, or from an env var. A skill shared across machines with a `D:\` path in it fails silently on the machine without a `D:`.

---

## 7. Parallel and background work

Serial round-trips are the slowest and most conversational shape. Three ways to overlap:

- **Background agents.** Long, self-contained work (a whole-codebase review, a big research task) can run as a background agent while the main session keeps working — this session's principal review (~8 minutes, 93K tokens) ran in the background while the README was written in parallel. Say: *"Run the review in the background; meanwhile, write the docs."*
- **Batch independent asks in one message.** Independent tool calls execute in parallel within a turn, and independent deliverables ("review X, and separately draft Y") let the agent overlap them. Dependent asks, state the dependency: *"Plan first from the review findings, so wait for it."*
- **Worktrees for parallel code changes.** Two agents editing one checkout collide; isolation (git worktree / the Agent tool's worktree option) makes parallel implementation tasks safe. Use for genuinely independent tasks only — shared-file tasks should stay serial.

---

## 8. Anti-patterns (the money-wasters, named)

- **Drip-feeding** — one instruction per message when you already know the next three steps. Each message re-pays the history. (§3 has the fix.)
- **The ambiguous "fix it"** — pronouns without referents force a clarifying round-trip or, worse, a guess. Name the file, the finding, the behavior.
- **Pasting what you could point at** — a 500-line log pasted into chat sits in the context *forever, every turn*. Point at the file path instead; the agent can grep it and read only the relevant lines.
- **Problem statement vs. change request, unlabeled** — "the header looks wrong" might mean *diagnose* or *fix*. Say which: "diagnose only, don't change anything yet" vs. "find and fix."
- **Re-explaining what's already written down** — if it's in the plan/receipt/README, say "per the receipt" instead of re-typing it. Re-explanations also drift from the source and cause contradictions.
- **Using conversation as a database** — "remember from earlier that…" across a long session relies on unsummarized history surviving. Facts that matter → artifact or memory, at the moment they're established.
- **Defaulting to the top-tier model for everything** — for well-specified tasks, start at the cheapest plausible tier and escalate *on failure* (one retry max, then jump tiers). The reverse — top tier for a checkbox flip — is the common silent overspend. Exception: genuinely ambiguous or architecture-shaping work should start at the top; a failed cheap attempt there costs more than it saves.
- **Letting stale scaffolding linger** — an outdated todo list, a plan section that no longer matches reality, a skill with a dead path. Stale context doesn't just waste tokens; it actively misleads. Fix the source the moment you notice.

---

## 9. Reference: current pricing (verified 2026-07-10)

| Model | Input $/M | Output $/M | Right tier for |
|---|---|---|---|
| Fable 5 | $10 | $50 | Frontier reasoning, plans that may need mid-flight revision |
| Opus 4.8 | $5 | $25 | Architecture reviews, hard agentic work |
| Sonnet 4.6 | $3 | $15 | Well-specified execution, conformance reviews — the workhorse |
| Haiku 4.5 | $1 | $5 | Mechanical edits, guard tests, classification-grade tasks |

Cache economics: reads ≈ 0.1× input price; writes ≈ 1.25× (5-min TTL). Cache is a byte-exact **prefix** match, **per model** — model switches and long gaps start over.

---

## 10. Paste-ready `CLAUDE.md` block

```markdown
## Efficiency rules
- Files >500 lines: locate with Grep first, then ranged Read. Never unbounded Read.
- Reference docs: read only the section relevant to the current task.
- Dispatch mechanical/conformance reviews to subagents with model: "sonnet";
  keep architecture/adversarial reviews on the session model.
- Never switch the main-session model mid-phase (per-model cache).
- Proceed without asking for reversible actions within the stated task; ask only
  for destructive actions or scope changes. No "Shall I...?" closers.
- End every milestone with a durable artifact (plan/receipt/README) so the next
  session can cold-start from it.
- Compare reference screenshots once; reuse conclusions.
```

---

*Maintenance note: pricing and cache figures verified against the claude-api reference on 2026-07-10 — re-verify before trusting them in 2027. (The work-receipt skill's formerly hardcoded `D:` output path was fixed 2026-07-10 to resolve relative to the skill's own location, so it now works on both the work machine (`D:\git\worky`) and this one (`C:\git\worky`).)*
