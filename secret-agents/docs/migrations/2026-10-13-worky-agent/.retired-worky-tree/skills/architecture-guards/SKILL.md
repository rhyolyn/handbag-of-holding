---
name: architecture-guards
description: Use when establishing an architectural rule that must survive future sessions — layer boundaries, import direction, state ownership, size tripwires — or when such a rule exists only in prose, review feedback, or comments and has no failing check in CI.
---

# Architecture Guards

## Overview

An architectural rule that is not machine-checked does not exist across sessions. This skill holds per-ecosystem recipes for turning rules into checks.

A qualifying guard has four properties:

1. Runs in CI and fails the build on violation.
2. Is named after the rule it enforces (`test_views_do_not_import_state_layers`, not `test_imports_2`).
3. Has a planted-violation test proving it fires on a synthetic offender.
4. Fails loudly when it scans nothing — an empty directory, a moved path, or a parser blind spot must break the guard, not green it.

When NOT to use: one-off style preferences (linter config), rules a compiler already enforces, or judgment calls that genuinely need a human (cohesion, naming) — those get review checklists, not guards.

## Quick reference

| Rule type | Python | Unreal C++ | TypeScript |
|---|---|---|---|
| Layer / import direction | pytest AST scanner (below) | `.Build.cs` module dependency lists | `eslint no-restricted-imports`, dependency-cruiser |
| Type-strictness ratchet | pyright `include` list, widened per migration step | — | `tsconfig` include list / project references |
| Deleted module cannot return | forbidden-import list test, grown at deletion time | remove from every `.Build.cs`; CI compile fails on reuse | dependency-cruiser `forbidden` rule |
| "No logic in X" (declarative-only files) | AST node walk (forbid `If`/`For`/`While`/`Match`/`Try`) | header-scan Automation test | eslint custom rule |
| Size tripwire | line-count test + allowlist with justification comment | CI script + allowlist | same |
| Suite actually ran | pytest exits 5 on zero collected — never mask it | assert Automation test count > 0 | ban `--passWithNoTests` |

## Python: AST import scanner (reference implementation)

Regex cannot resolve relative imports; parse the AST. One scanner serves every layer rule:

```python
import ast
from pathlib import Path

def imported_modules(source: str, module_package: str) -> set[str]:
    """Dotted module paths imported by `source`.
    `module_package` (e.g. 'myapp.views.detail') resolves relative imports."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    found.add(node.module)
            else:
                parts = module_package.split(".")
                base = ".".join(parts[: len(parts) - (node.level - 1)])
                found.add(f"{base}.{node.module}" if node.module else base)
    return found

def package_imports(package_dir: Path, root_package: str) -> dict[str, set[str]]:
    result = {}
    for path in sorted(package_dir.rglob("*.py")):
        rel = path.relative_to(package_dir.parent)
        mod = ".".join((root_package,) + rel.parts[:-1])
        result[str(rel)] = imported_modules(path.read_text(), mod)
    return result
```

A guard is then one assertion:

```python
def test_views_do_not_import_state_layers():
    forbidden = ("myapp.stores", "myapp.services", "myapp.persistence")
    for file, mods in package_imports(SRC / "views", "myapp").items():
        bad = sorted(m for m in mods if m.startswith(forbidden))
        assert not bad, f"{file} imports forbidden layers: {bad}"
```

Always ship the two safety tests alongside:

```python
def test_guard_fires_on_planted_violation(tmp_path):
    (tmp_path / "offender.py").write_text("from myapp.stores import base\n")
    mods = imported_modules((tmp_path / "offender.py").read_text(), "fake.views")
    assert "myapp.stores.base" in mods  # scanner sees it → guard would fail

def test_guards_scan_real_files():
    assert list((SRC / "views").rglob("*.py")), "guard is scanning an empty directory"
```

## Unreal C++

- **Layering is native:** a module can only include what its `.Build.cs` declares in `PublicDependencyModuleNames`/`PrivateDependencyModuleNames`. Express layer rules as dependency lists — the compiler is the guard, and CI compilation is the check. Prefer this over any scanner.
- **Deleting a module:** remove it from every `.Build.cs` in the same change; reintroduction then fails compilation, which is the forbidden-list equivalent.
- **Rules inside one module** (e.g., "gameplay code never includes editor headers"): an Automation spec that walks the module's `Public/`/`Private/` headers and fails on banned `#include` patterns. Give it a planted offender under a test fixture directory.
- **Suite-ran check:** the automation runner reports executed test counts; fail CI when the filter matched zero tests.

## TypeScript

- **Per-layer import bans:** `no-restricted-imports` in eslint overrides keyed by folder, or `eslint-plugin-boundaries` for whole-architecture element types.
- **Graph rules** (cycles, orphans, forbidden edges): dependency-cruiser with `forbidden` rules, run in CI; its `reachable`/`orphan` rules catch dead modules.
- **Hard boundaries beat lint:** tsconfig project references make an upward import unresolvable rather than merely flagged. Use references between layers, lint within them.

## CI patterns (any ecosystem)

- **Fail-on-empty selection:** a green job that ran nothing is the most expensive kind of green. pytest exits 5 on zero collected tests — let it fail the job; where the runner doesn't do this, assert on the reported count.
- **Size tripwires force a decision, not a verdict:** a trip requires an allowlist entry plus a justification comment in the same PR. A cohesive large file with a justification is a pass; splitting to duck the gate is the failure mode the tripwire exists to surface.
- **Deletion rule for migrations:** every change that deletes a superseded module also adds it to the forbidden list. Old code that "cannot creep back" is a property of the guard, not of intentions.

## Common mistakes

- **Guard greens because it scans nothing.** Moved directory, renamed package, glob typo. Fix: the scans-real-files assertion, always.
- **Regex import matching.** Misses relative imports, aliases, and multi-line imports. Parse the AST.
- **Rule lives only in AGENTS.md or a comment.** It will be violated politely and confidently. Write the check in the same change that states the rule.
- **No planted violation.** You proved the guard passes, never that it can fail — that is an untested test.
- **Count gates as verdicts.** Line/file/parameter counts are tripwires for human decisions; hard-failing on them rewards evasive splitting.
