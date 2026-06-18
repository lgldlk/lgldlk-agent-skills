# Personal Agent Skills

A small public collection of agent skills maintained by lgldlk. The first version contains one self-owned skill: `api-data-research`.

## Skills

| Skill | Category | Use When |
|---|---|---|
| `api-data-research` | Research | Compare official and third-party API data-access options, verify exact fields from docs, and produce cited capability matrices. |

## Install

Install the skill with an Agent Skills compatible installer:

```bash
npx skills add lgldlk/personal-agent-skills --skill api-data-research -g -a codex -y
```

Or copy the skill folder manually:

```bash
cp -R skills/api-data-research ~/.codex/skills/
```

## Repository Layout

```text
personal-agent-skills/
├── skills/
│   ├── index.json
│   └── api-data-research/
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       └── scripts/
│           └── render_markdown_table_png.py
├── scripts/
│   └── validate-skills.sh
├── docs/
│   ├── authoring.md
│   ├── install.md
│   └── release-checklist.md
└── templates/
    └── SKILL.template.md
```

## Quality Standard

- Every skill lives at `skills/<skill-name>/SKILL.md`.
- `SKILL.md` frontmatter contains only `name` and `description`.
- `name` must match the skill directory.
- Long references belong in `references/`.
- Repeatable deterministic logic belongs in `scripts/`.
- Public skills must not contain API keys, tokens, cookies, private URLs, or local-only absolute paths.

Run:

```bash
scripts/validate-skills.sh
```

## License

MIT
