#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3 is required"

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path.cwd()
skills_dir = root / "skills"
index_path = skills_dir / "index.json"

if not index_path.exists():
    raise SystemExit("skills/index.json is missing")

index = json.loads(index_path.read_text(encoding="utf-8"))
if not isinstance(index, list):
    raise SystemExit("skills/index.json must be a list")

indexed = {item.get("name"): item for item in index}
skill_dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir())

for skill_dir in skill_dirs:
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SystemExit(f"{skill_name}: SKILL.md is missing")

    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"{skill_name}: missing YAML frontmatter")

    try:
        _, frontmatter, _ = text.split("---", 2)
    except ValueError as exc:
        raise SystemExit(f"{skill_name}: invalid frontmatter") from exc

    fields = {}
    for line in frontmatter.strip().splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise SystemExit(f"{skill_name}: invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')

    allowed = {"name", "description"}
    extra = set(fields) - allowed
    missing = allowed - set(fields)
    if extra:
        raise SystemExit(f"{skill_name}: extra frontmatter fields: {sorted(extra)}")
    if missing:
        raise SystemExit(f"{skill_name}: missing frontmatter fields: {sorted(missing)}")
    if fields["name"] != skill_name:
        raise SystemExit(f"{skill_name}: frontmatter name must match directory")
    if len(fields["description"]) < 40:
        raise SystemExit(f"{skill_name}: description is too short")
    if skill_name not in indexed:
        raise SystemExit(f"{skill_name}: missing from skills/index.json")
    if indexed[skill_name].get("path") != f"skills/{skill_name}":
        raise SystemExit(f"{skill_name}: index path is incorrect")

for name, item in indexed.items():
    if not name:
        raise SystemExit("skills/index.json contains item without name")
    path = item.get("path")
    if not path or not (root / path).exists():
        raise SystemExit(f"{name}: indexed path does not exist: {path}")

sensitive_patterns = [
    r"api[_-]?key\s*[:=]",
    r"token\s*[:=]",
    r"cookie\s*[:=]",
    r"Authorization:\s*Bearer\s+",
    r"gho_[A-Za-z0-9_]+",
    r"sk-[A-Za-z0-9_-]{20,}",
]

for path in root.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern in sensitive_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise SystemExit(f"possible secret pattern in {path.relative_to(root)}: {pattern}")

print(f"OK: validated {len(skill_dirs)} skill(s)")
PY
