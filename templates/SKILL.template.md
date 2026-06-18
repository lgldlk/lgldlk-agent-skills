---
name: skill-name
description: Describe what this skill does and include concrete user requests or contexts that should trigger it.
---

# Skill Name

## Workflow

1. Inspect the user's request and available inputs.
2. Load bundled references only when relevant.
3. Run bundled scripts only when deterministic execution is useful.
4. Produce the requested artifact.
5. Validate the result before final response.

## Rules

- Keep the skill concise.
- Mark uncertain facts clearly.
- Do not expose secrets, private URLs, or local-only paths.

## Resources

- Read `references/example.md` only when the task requires detailed domain rules.
- Run `scripts/example.py --help` before first use if a script exists.
