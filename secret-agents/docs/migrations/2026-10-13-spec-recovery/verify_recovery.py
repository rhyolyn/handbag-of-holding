"""Read-only audit of the repaired library and both preserved migration snapshots."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

import markdown
import yaml

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
SKILLS = ROOT / "skills"
INITIAL = AUDIT.parent / "2026-10-13-worky-agent"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--original-checkout", type=Path, help="Optionally compare archived source files to this checkout.")
parser.add_argument("--worky-root", type=Path, help="Optionally verify a live Worky pointer after the archive audit.")
arguments = parser.parse_args()
ORIGINAL = arguments.original_checkout
WORKY = arguments.worky_root
errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


initial = json.loads((INITIAL / "manifest.json").read_text(encoding="utf-8"))
check(digest((INITIAL / "original-trees.zip").read_bytes()) == initial["archive_sha256"], "Initial ZIP hash changed")
with ZipFile(INITIAL / "original-trees.zip") as archive:
    for entry in initial["entries"]:
        check(digest(archive.read(entry["archive_member"])) == entry["sha256"], f"Initial archive: {entry['path']}")
        if entry["tree"] != "worky-Agent":
            continue

recovery = json.loads((AUDIT / "manifest.json").read_text(encoding="utf-8"))
source_count = 0
with ZipFile(AUDIT / "before-recovery.zip") as archive:
    for entry in recovery["entries"]:
        check(digest(archive.read(entry["member"])) == entry["sha256"], f"Recovery archive: {entry['member']}")
        if entry["tree"] == "git-source" and ORIGINAL is not None:
            path = ORIGINAL / entry["path"]
            if not path.is_file():
                check(False, f"Recovery source missing: {path}")
            else:
                unchanged = digest(path.read_bytes()) == entry["sha256"]
                check(unchanged, f"Recovery source changed: {path}")
                source_count += int(unchanged)

if WORKY is not None:
    check(not (WORKY / "Agent").exists(), "Worky/Agent exists")
    check(not (WORKY / "Agents").exists(), "Worky/Agents exists")
    pointer = WORKY / "AGENTS.md"
    check(
        pointer.is_file() and "../handbag-of-holding/secret-agents/AGENTS.md" in pointer.read_text(encoding="utf-8"),
        "Worky pointer missing",
    )

catalog_script = SKILLS / "skill-authoring/query-all-skills/scripts/catalog.py"
spec = importlib.util.spec_from_file_location("recovery_catalog_audit", catalog_script)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
data = json.loads((SKILLS / "catalog.json").read_text(encoding="utf-8"))
entries = {entry["name"]: entry for entry in data["entries"]}
projections = data["generated_projection"]
files = sorted(SKILLS / entry["source_path"] / "SKILL.md" for entry in entries.values())
projection_files = sorted(SKILLS / path / "SKILL.md" for path in projections.values())
# The recovery record retains the original inventory in verification.json. The
# current library may grow, so validate catalog consistency instead of freezing
# its size at the recovery snapshot.
check(bool(entries), "Catalog has no canonical workflows")
check(
    {path.relative_to(SKILLS).parent.as_posix() for path in files} == {entry["source_path"] for entry in entries.values()},
    "Unexpected or missing canonical skill directories",
)
check(set(projections) == set(entries), "Generated projection names do not match canonical entries")

before = {path: digest(path.read_bytes()) for path in [*files, *projection_files, SKILLS / "catalog.json", SKILLS / "TOC.md"]}
check(module.SkillCatalog(SKILLS, AUDIT / "catalog-cache.json").check(out=io.StringIO()) == 0, "Catalog drift")
check(all(digest(path.read_bytes()) == sha for path, sha in before.items()), "Catalog check mutated a skill artifact")
for path in files:
    text = path.read_text(encoding="utf-8")
    name = module.parse_frontmatter(text)["name"]
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    check(frontmatter.get("name") == name, f"Folder/frontmatter mismatch: {name}")
    check(isinstance(frontmatter.get("description"), str) and bool(frontmatter["description"]), f"Missing description: {name}")
    check(not ({"category", "kind", "alias_of"} & frontmatter.get("metadata", {}).keys()), f"Obsolete metadata: {name}")
    header = module.parse_skill_header(text)
    check(header.category == entries[name]["category"], f"Category mismatch: {name}")
    check(module.compute_content_hash(text) == entries[name]["content_hash"], f"Canonical content hash: {name}")
    projection = SKILLS / projections[name] / "SKILL.md"
    projection_text = projection.read_text(encoding="utf-8") if projection.is_file() else ""
    check(module.parse_frontmatter(projection_text).get("name") == name, f"Projection name mismatch: {name}")
    check(f"{entries[name]['source_path']}/SKILL.md" in projection_text, f"Projection target mismatch: {name}")

toc = (SKILLS / "TOC.md").read_text(encoding="utf-8")
readme = (SKILLS / "README.md").read_text(encoding="utf-8")
html = (SKILLS / "README.html").read_text(encoding="utf-8")
check(len(re.findall(r"^- /", toc, re.M)) == len(entries), "Compact TOC must have one entry per canonical skill")
for name, entry in entries.items():
    check(f"- /{entry['name']}:" in toc, f"TOC canonical entry missing: {name}")
    check(f"[{entry['name']}](#{name})" in readme, f"README inventory entry missing: {name}")
    check(len(re.findall(r"^### " + re.escape(name) + r"$", readme, re.M)) == 1, f"Canonical README section: {name}")
check("—" not in toc, "TOC contains an em dash")
check(markdown.markdown(readme, extensions=["tables", "toc", "fenced_code"]) in html, "README HTML is stale")

result = {
    "ok": not errors,
    "original_migration_archive_files": len(initial["entries"]),
    "recovery_archive_files": len(recovery["entries"]),
    "unchanged_recovery_source_files": source_count,
    "recovery_source_comparison": str(ORIGINAL) if ORIGINAL is not None else "not requested",
    "canonical_skills": len(entries),
    "generated_projections": len(projections),
    "worky_agent_absent": WORKY is None or not (WORKY / "Agent").exists(),
    "errors": errors,
}
print(json.dumps(result, indent=2))
raise SystemExit(0 if not errors else 1)
