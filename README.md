# lgldlk Agent Skills

[中文说明](README.zh-CN.md)

A public collection of reusable agent skills maintained by `lgldlk`.

These skills come from recurring real workflows: researching API data access, following AI news, aligning mini-program UI with Figma, packaging Markdown for platform import, parsing public social links, transcribing media, and orchestrating multi-agent work. The repository is designed as a personal skill library, while keeping every skill inspectable and installable on its own.

## Skills

| Skill | Purpose | Main output |
|---|---|---|
| [`api-data-research`](skills/api-data-research/SKILL.md) | Compare official and third-party API data access from docs, response examples, pricing pages, and stability signals. | Cited research notes, field-level capability matrices, PNG table exports. |
| [`ai-news-digest`](skills/ai-news-digest/SKILL.md) | Fetch current AI news from RSS/Atom feeds, optional X and non-RSS sources, and GitHub AI trending. | Dated AI news digest with links, source window, and trend notes. |
| [`agent-pipeline-orchestration`](skills/agent-pipeline-orchestration/SKILL.md) | Manage work as a non-blocking multi-agent pipeline with bounded implementation, review, QA, and mapping lanes. | Lane planning, worker prompts, and integration guidance. |
| [`miniapp-figma-alignment`](skills/miniapp-figma-alignment/SKILL.md) | Implement or fix mini-program, uni-app, or Taro screens so they match Figma dimensions and platform behavior. | Unit conversion decisions, implementation guidance, visual QA checklist. |
| [`markdown-platform-pack`](skills/markdown-platform-pack/SKILL.md) | Convert Markdown into import-safe Word output by rasterizing unsupported tables and code blocks first. | `*.tmp.md`, PNG block images, `*.docx` import files. |
| [`social-content-parser`](skills/social-content-parser/SKILL.md) | Parse public short-video and social share URLs with a 20+ platform fallback layer, including Xiaohongshu, Douyin, and Bilibili, into local reports and media packages. | `report.md`, `normalized.json`, `raw.json`, local media, and optional transcripts. |
| [`video-to-text`](skills/video-to-text/SKILL.md) | Transcribe local video/audio files or public media download URLs with Tencent Cloud ASR. Credentials stay outside the skill. | `transcript.txt`, `.json`, `.srt`, or `.md`. |
| [`weijincha-content-check`](skills/weijincha-content-check/SKILL.md) | Check Chinese copy and text-like files for platform, advertising, prohibited, and industry-specific risk terms. | Normalized JSON with pass status, matched words, scopes, and source locations. |

## Quick Install

List available skills:

```bash
npx skills add lgldlk/lgldlk-agent-skills --list
```

Install a specific skill:

```bash
npx skills add lgldlk/lgldlk-agent-skills --skill api-data-research -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill ai-news-digest -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill agent-pipeline-orchestration -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill miniapp-figma-alignment -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill markdown-platform-pack -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill social-content-parser -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill video-to-text -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill weijincha-content-check -g -y
```

Manual install:

```bash
mkdir -p ~/.skills
cp -R skills/api-data-research ~/.skills/
cp -R skills/ai-news-digest ~/.skills/
cp -R skills/agent-pipeline-orchestration ~/.skills/
cp -R skills/miniapp-figma-alignment ~/.skills/
cp -R skills/markdown-platform-pack ~/.skills/
cp -R skills/social-content-parser ~/.skills/
cp -R skills/video-to-text ~/.skills/
cp -R skills/weijincha-content-check ~/.skills/
```

Restart your agent after installation so the skill metadata is loaded.

## Output Examples

### API Data Research

This skill produces evidence-backed API comparisons instead of relying on vendor claims or SEO visibility. A typical result includes a concise conclusion, a capability matrix, field-level alignment, pricing/access notes, and confidence labels.

![API Data Research capability matrix](assets/screenshots/api-data-research-matrix.png)

Source example: [`examples/api-data-research-example.md`](examples/api-data-research-example.md)

### AI News Digest

This skill fetches current AI news before writing a digest, instead of relying on memory. It defaults to the past 24 hours, but can use any requested window such as today, this week, or the past 72 hours.

Command:

```bash
python3 skills/ai-news-digest/scripts/fetch_ai_news.py \
  --since 24h --limit 0 --max-per-source 0 --format md --output ./ai-news.md
```

Optional GitHub AI trending:

```bash
python3 skills/ai-news-digest/scripts/fetch_github_ai_trending.py \
  --since daily --limit 0 --format md --output ./github-ai.md
```

Result shape:

```text
AI News Digest (<date range>)
- item title, source, date, link
- what happened and why it matters

Trends and recommendations
```

### Miniapp Figma Alignment

This skill helps reason from the actual Figma frame width and the target mini-program unit pipeline.

Minimal result shape:

```text
Figma frame width: 390px
Target design width: 750rpx
Scale: 750 / 390 = 1.9231

Example conversion:
- 16px padding -> 30.77rpx
- 338px card width -> 650.00rpx
- 14px font size -> 26.92rpx

Checks:
- Do not redraw native status bar or capsule.
- Keep safe-area padding for fixed bottom actions.
- Do not mix final rpx values with Taro pxtransform in the same layout region.
```

Source example: [`examples/miniapp-figma-alignment-example.md`](examples/miniapp-figma-alignment-example.md)

### Markdown Platform Pack

This skill converts Markdown articles into import-safe Word packages by rasterizing unsupported tables and code blocks first.

Minimal result shape:

```text
article.xiaohongshu.tmp.md
assets/
  article-table-1.png
  article-code-1.png
article.xiaohongshu.docx
```

Source example: use the local `markdown-platform-pack` skill directory.

### Social Content Parser

This skill turns public short-video and social share URLs into local note packages. Its broad fallback layer covers 20+ platforms, including Douyin, Kuaishou, Xiaohongshu, Bilibili, YouTube, TikTok, Xigua, Haokan, Weishi, Pear Video, AcFun, Zhihu, Oasis, Meipai, Quanmin, Huya, X/Twitter, Instagram, Doubao, Jimeng AI, and WeChat Channels. It normalizes noisy share links by keeping the content path, routes Douyin profile and work links separately, and falls back to the aggregated parser when the platform-specific parser misses content.

Command:

```bash
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://www.xiaohongshu.com/explore/..."
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://v.douyin.com/..."
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://www.douyin.com/user/..." --kind profile --count 10
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://b23.tv/..."
```

Result shape:

```text
social-notes/
└── <platform>-<title>-<YYYY-MM-DD>-<id>/
    ├── report.md
    ├── normalized.json
    ├── raw.json
    ├── transcript.md
    └── media/
        ├── author-avatar.jpg
        ├── cover.jpg
        └── image-01.jpg
```

Example summary:

```text
Platform: xiaohongshu
Title: Demo note title
Author: Demo Author
Images: 1
Downloads: 3
Report: social-notes/xiaohongshu-demo-note-2026-06-19-demoid/report.md
```

Sample API responses:

- [`examples/social-content-parser-xhs-sample.json`](examples/social-content-parser-xhs-sample.json)
- [`examples/social-content-parser-douyin-sample.json`](examples/social-content-parser-douyin-sample.json)
- [`examples/social-content-parser-douyin-profile-sample.json`](examples/social-content-parser-douyin-profile-sample.json)
- [`examples/social-content-parser-bilibili-sample.json`](examples/social-content-parser-bilibili-sample.json)

### Video To Text

This skill transcribes a local media file or a public media download URL with Tencent Cloud ASR. It does not accept a Douyin/Xiaohongshu/Bilibili share page as `--url`. Keep SecretId/SecretKey in `~/.config/video-to-text/config.json`, an ignored `.video-to-text.json`, or environment variables. Copy `skills/video-to-text/config.example.json` as a starting point.

```bash
python3 skills/video-to-text/scripts/transcribe_media.py \
  --input ./video.mp4 --output ./transcript.md
python3 skills/video-to-text/scripts/transcribe_media.py \
  --url "https://example.com/video.mp4" --output ./subtitle.srt --sentence-max-length 20
```

### Recommended flow: share link → local package → transcript

Use the two skills as a pair. Parsing is free and should run first. Transcription is a paid Tencent ASR call and should run only when the user asks.

1. Install both skills as siblings:

```bash
npx skills add lgldlk/lgldlk-agent-skills --skill social-content-parser -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill video-to-text -g -y
```

2. Put Tencent credentials outside the skill directory. Preferred: `credentialFile` in `~/.config/video-to-text/config.json`, or `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY`.
3. Parse the share URL first. Do not pass `--transcribe` yet:

```bash
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://v.douyin.com/..."
```

4. If a transcript is needed, rerun the same URL with `--transcribe`. Default `direct` mode sends `normalized.primaryVideo` to Tencent and does not require `--download-video`:

```bash
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://v.douyin.com/..." --transcribe --transcript-format md
```

5. Use `--transcription-mode local` plus `--download-video` only when the CDN URL needs local headers or expires quickly.
6. Douyin profile results contain many works. Parse the profile, then transcribe a single work URL. Do not transcribe the profile itself.
7. For an already-local file, skip the parser and call `video-to-text` directly.

The parser discovers `video-to-text/scripts/transcribe_media.py` as a sibling skill. Override with `--video-to-text-script` or `VIDEO_TO_TEXT_SCRIPT` when the two skills are not installed next to each other.

## Repository Layout

```text
lgldlk-agent-skills/
├── assets/
│   └── screenshots/
├── docs/
├── examples/
├── scripts/
│   └── validate-skills.sh
├── skills/
│   ├── index.json
│   ├── api-data-research/
│   ├── ai-news-digest/
│   ├── agent-pipeline-orchestration/
│   ├── markdown-platform-pack/
│   ├── miniapp-figma-alignment/
│   ├── social-content-parser/
│   ├── video-to-text/
│   └── weijincha-content-check/
└── templates/
```

## Quality Rules

- Each skill lives at `skills/<skill-name>/SKILL.md`.
- `SKILL.md` frontmatter contains only `name` and `description`.
- The frontmatter `name` must match the skill directory.
- Long reference material goes in `references/`.
- Repeatable deterministic logic goes in `scripts/`.
- Public skills must not contain API keys, tokens, cookies, private URLs, or local-only absolute paths.

Validate the repository:

```bash
scripts/validate-skills.sh
```

## License

MIT
