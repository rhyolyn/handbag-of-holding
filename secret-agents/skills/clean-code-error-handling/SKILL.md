---
name: clean-code-error-handling
description: Use when designing or changing error handling, or when a repository has inline messages, generic exceptions, duplicate logging, string-parsed failures, scattered error types, or unclear error ownership.
---

# Clean Code: Error Handling

## Overview

Turn ad hoc failures into a small, semantic error model without changing public behavior accidentally. Error identity represents a condition a consumer can act on; prose alone never earns a type.

## Workflow

1. Read repository guidance and identify the language's native error mechanism: exceptions, typed errors, result values, error codes, or framework responses. Do not impose an exception hierarchy where the ecosystem uses another model.
2. Inventory error creation, wrapping, catching, logging, retrying, suppression, and presentation. Search for generic throws, inline messages, catch-all handlers, log-and-rethrow, message matching, status/exit translation, and lost causes.
3. Build a failure matrix before editing:

| Failure | Classification | Consumer reaction | Current public contract | Owner |
|---|---|---|---|---|
| condition | invariant / expected / infrastructure / cancellation / capability | retry, map, refuse, abort, none | message, status, exit code, type | domain or boundary |

4. Derive types from semantics. Create a distinct type only when callers, tests, retry policy, presentation, or diagnostics need to distinguish that condition without parsing text. Keep programmer errors and standard cancellation types native unless the repository has a demonstrated contract requiring translation.
5. Choose the shallowest useful hierarchy. Add a common base only when a real boundary catches the family. Prefer `DomainError -> ConcreteCondition`; add intermediate categories only for an existing shared consumer.
6. Assign ownership:
   - The semantic error type owns its stable diagnostic construction and structured context.
   - A lower-level boundary wraps only to add domain meaning and preserves the original cause.
   - The presentation boundary owns user-safe messages, HTTP responses, CLI output, and exit codes.
   - The boundary that terminates propagation or converts the failure into an outcome logs it once. Wrapping layers do not log-and-rethrow.
7. Place one or two small types beside their behavior. Extract a family when it obscures the owning module's core flow or serves several peer modules. Name the module for the domain (`catalog_errors`, `payment_failures`), not globally (`exceptions`, `errors`) unless the entire package is one cohesive domain. Add an `errors/` package only after several domain modules justify it.
8. Characterize externally visible behavior before migration. Preserve public import paths, error identity, causes, message text, status codes, headers, output streams, and exit codes unless the request explicitly changes them.
9. Migrate one domain slice at a time. Run focused tests after each slice and the repository's complete quality gate at the end.
10. When the new boundary must persist, add the repository's native lint or architecture check for mechanically detectable violations such as thrown strings, generic throws, message parsing, forbidden framework imports, or log-and-rethrow. Prose alone does not enforce the rule.

## Decision Rules

| Situation | Action |
|---|---|
| Same message, different caller reactions | Use distinct semantic errors. |
| Different messages, same condition and reaction | Use one error with contextual values. |
| No caller distinguishes the condition | Keep native error/wrapping; do not add a type. |
| Catch parses message text | Replace parsing with stable identity or structured fields. |
| Layer adds no meaning | Propagate unchanged and do not log. |
| Public behavior should change | Treat it as a separate contract change. |

## Example

```python
# catalog_errors.py
class CatalogError(Exception):
    pass


class MissingSkillName(CatalogError):
    def __init__(self, skill_file: Path) -> None:
        self.skill_file = skill_file
        super().__init__(f"{skill_file}: frontmatter is missing 'name'")


# catalog.py
if name is None:
    raise MissingSkillName(skill_file)
```

Keep `CatalogError` only if a real catalog boundary catches it. In Go, Rust, or result-oriented code, preserve native wrapping and matching semantics instead of copying this class shape.

## Common Mistakes

- Creating one type per message template: identity becomes coupled to wording.
- Moving every type into one repository-wide dumping ground: ownership disappears.
- Mirroring every implementation file with an error file: file layout drives design.
- Catching and wrapping everything: programmer defects and cancellation lose their semantics.
- Logging at every layer: one failure becomes several misleading incidents.
- Refactoring messages, status mapping, and hierarchy simultaneously: regressions become impossible to localize.
- Testing private taxonomy instead of observable contracts: tests resist harmless redesigns.
