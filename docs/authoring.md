# Skill Authoring

Use this repository structure for new skills:

```text
skills/<skill-name>/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
├── scripts/
└── assets/
```

Only `SKILL.md` is required. Add optional folders only when the skill needs them.

## Rules

- Use lowercase hyphenated skill names.
- Make the directory name equal to the `name` frontmatter.
- Keep `SKILL.md` frontmatter to `name` and `description`.
- Put trigger conditions in `description`.
- Keep detailed long-form rules in `references/`.
- Put repeated deterministic code in `scripts/`.
- Do not add per-skill README files unless there is a strong reason.
- Run `scripts/validate-skills.sh` before committing.
