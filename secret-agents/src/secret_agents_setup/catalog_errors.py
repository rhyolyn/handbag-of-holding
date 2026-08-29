"""Errors raised while discovering and validating the skill catalog."""

from pathlib import Path


class SkillCatalogError(Exception):
    """Raised when the skills directory or a SKILL.md fails validation."""


class SkillsDirectoryNotFound(SkillCatalogError):
    def __init__(self, skills_root: Path) -> None:
        super().__init__(f"{skills_root}: skills directory not found")


class SkillDirectoryNameMismatch(SkillCatalogError):
    def __init__(self, directory: Path, declared_name: str) -> None:
        super().__init__(
            f"{directory}: declared name {declared_name!r} does not match directory name {directory.name!r}"
        )


class MissingSkillFile(SkillCatalogError):
    def __init__(self, directory: Path) -> None:
        super().__init__(f"{directory}: missing SKILL.md")


class MissingSkillName(SkillCatalogError):
    def __init__(self, skill_md: Path) -> None:
        super().__init__(f"{skill_md}: frontmatter is missing 'name'")


class MissingSkillDescription(SkillCatalogError):
    def __init__(self, skill_md: Path) -> None:
        super().__init__(f"{skill_md}: frontmatter is missing 'description'")


class InvalidSkillName(SkillCatalogError):
    def __init__(self, skill_md: Path, name: str) -> None:
        super().__init__(f"{skill_md}: name {name!r} must be lowercase and hyphenated")


class MissingFrontmatter(SkillCatalogError):
    def __init__(self, skill_md: Path) -> None:
        super().__init__(f"{skill_md}: missing frontmatter delimiters")


class UnterminatedFrontmatter(SkillCatalogError):
    def __init__(self, skill_md: Path) -> None:
        super().__init__(f"{skill_md}: unterminated frontmatter block")


class DuplicateSkillNames(SkillCatalogError):
    def __init__(self, duplicates: list[str]) -> None:
        super().__init__(f"duplicate declared skill names: {', '.join(duplicates)}")
