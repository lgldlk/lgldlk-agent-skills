# Install

List available skills:

```bash
npx skills add lgldlk/lgldlk-agent-skills --list
```

Install one skill:

```bash
npx skills add lgldlk/lgldlk-agent-skills --skill api-data-research -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill ai-news-digest -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill agent-pipeline-orchestration -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill miniapp-figma-alignment -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill markdown-platform-pack -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill social-content-parser -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill video-to-text -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill weijincha-content-check -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill grok-x-search -g -a codex -y
```

Install the social parse + transcribe pair together:

```bash
npx skills add lgldlk/lgldlk-agent-skills --skill social-content-parser -g -a codex -y
npx skills add lgldlk/lgldlk-agent-skills --skill video-to-text -g -a codex -y
```

Manual install:

```bash
mkdir -p ~/.codex/skills
cp -R skills/api-data-research ~/.codex/skills/
cp -R skills/ai-news-digest ~/.codex/skills/
cp -R skills/agent-pipeline-orchestration ~/.codex/skills/
cp -R skills/miniapp-figma-alignment ~/.codex/skills/
cp -R skills/markdown-platform-pack ~/.codex/skills/
cp -R skills/social-content-parser ~/.codex/skills/
cp -R skills/video-to-text ~/.codex/skills/
cp -R skills/weijincha-content-check ~/.codex/skills/
cp -R skills/grok-x-search ~/.codex/skills/
```

Then start a new Codex session so the skill metadata is reloaded.

For share-link transcription, install both `social-content-parser` and `video-to-text`, then keep Tencent credentials outside the skill directory. See the README recommended flow.
