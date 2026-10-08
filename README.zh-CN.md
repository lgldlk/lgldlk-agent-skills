# lgldlk Agent Skills

[English](README.md)

这是 `lgldlk` 维护的公开个人 Agent Skills 仓库。

这些技能来自真实、反复出现的工作流：API 数据能力调研、AI 新闻追踪、小程序 UI 对齐 Figma、Markdown 打包导出、公开社交链接解析、音视频转写，以及多 agent 流水线协作。这个仓库可以作为个人技能库安装，也可以单独查看和复制某一个技能。

## 技能列表

| 技能 | 用途 | 主要产物 |
|---|---|---|
| [`api-data-research`](skills/api-data-research/SKILL.md) | 从文档、响应样例、价格页、稳定性和社区信号中对比官方及第三方 API 数据能力。 | 带引用的调研笔记、字段级能力矩阵、PNG 表格导出。 |
| [`ai-news-digest`](skills/ai-news-digest/SKILL.md) | 从 RSS/Atom、可选 X 和非 RSS 来源、GitHub AI Trending 抓取最新 AI 动态。 | 带日期范围、来源链接和趋势建议的 AI 新闻简报。 |
| [`agent-pipeline-orchestration`](skills/agent-pipeline-orchestration/SKILL.md) | 把工作拆成非阻塞的多 agent 流水线，包含实现、评审、QA 和下一阶段映射。 | 流水线分工、worker 提示词和集成说明。 |
| [`miniapp-figma-alignment`](skills/miniapp-figma-alignment/SKILL.md) | 修正或实现小程序、uni-app、Taro 页面，让它们和 Figma 尺寸及平台行为对齐。 | 单位换算判断、实现建议、视觉 QA 清单。 |
| [`markdown-platform-pack`](skills/markdown-platform-pack/SKILL.md) | 把 Markdown 转成适合导入的 Word 包，先把表格和代码块转成图片。 | `*.tmp.md`、PNG 块图片、`*.docx` 导入文件。 |
| [`social-content-parser`](skills/social-content-parser/SKILL.md) | 解析公开短视频和社交分享链接，提供 20+ 平台兜底层，包括小红书、抖音、哔哩哔哩，生成本地报告和媒体包。 | `report.md`、`normalized.json`、`raw.json`、本地媒体和可选转写。 |
| [`video-to-text`](skills/video-to-text/SKILL.md) | 用腾讯云 ASR 转写本地音视频或可公开下载的媒体 URL。密钥放在技能目录外。 | `transcript.txt`、`.json`、`.srt` 或 `.md`。 |
| [`weijincha-content-check`](skills/weijincha-content-check/SKILL.md) | 检查中文文案和文本类文件中的平台、广告、违禁及行业风险词。 | 包含通过状态、命中词、检测范围和来源位置的标准化 JSON。 |

## 快速安装

查看可安装技能：

```bash
npx skills add lgldlk/lgldlk-agent-skills --list
```

安装单个技能：

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

手动安装：

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

安装后重启你的 agent，让技能元数据重新加载。

## 结果示例

### API Data Research

这个技能用于做有证据链的 API 横向对比，而不是只看厂商宣传或 SEO 排名。典型结果包括简短结论、能力矩阵、字段对齐、价格/访问范围和信度标注。

![API Data Research 能力矩阵](assets/screenshots/api-data-research-matrix.png)

源示例：[`examples/api-data-research-example.md`](examples/api-data-research-example.md)

### AI News Digest

这个技能会先抓取最新 AI 新闻，再生成简报，避免凭记忆写“最新动态”。默认抓取过去 24 小时；如果用户指定今天、本周或过去 72 小时，也可以调整时间窗口。

命令：

```bash
python3 skills/ai-news-digest/scripts/fetch_ai_news.py \
  --since 24h --limit 0 --max-per-source 0 --format md --output ./ai-news.md
```

可选抓取 GitHub AI Trending：

```bash
python3 skills/ai-news-digest/scripts/fetch_github_ai_trending.py \
  --since daily --limit 0 --format md --output ./github-ai.md
```

结果结构：

```text
AI News Digest (<日期范围>)
- 新闻标题、来源、日期、链接
- 发生了什么，以及为什么重要

趋势与建议
```

### Miniapp Figma Alignment

这个技能会从真实 Figma 画布宽度和目标小程序单位体系出发，给出可落地的换算和检查项。

最小结果形态：

```text
Figma frame width: 390px
Target design width: 750rpx
Scale: 750 / 390 = 1.9231

Example conversion:
- 16px padding -> 30.77rpx
- 338px card width -> 650.00rpx
- 14px font size -> 26.92rpx

Checks:
- 不要重画原生状态栏或胶囊。
- 固定底部按钮要保留 safe-area padding。
- 同一布局区域不要混用最终 rpx 和 Taro pxtransform。
```

源示例：[`examples/miniapp-figma-alignment-example.md`](examples/miniapp-figma-alignment-example.md)

### Social Content Parser

这个技能把公开短视频和社交分享链接转成本地笔记包。它的兜底层覆盖 20+ 平台，包括抖音、快手、小红书、bilibili、油管、TikTok、西瓜视频、好看视频、微视、梨视频、a站（acfun）、知乎、绿洲、美拍、全民、虎牙、推特、ins、豆包、即梦ai、视频号等。它会先清理分享链接里的跟踪参数，抖音主页和作品会分开处理；当平台专用解析器漏掉内容时，还会用聚合解析做兜底。

命令：

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

结果结构：

```text
social-notes/
└── <平台>-<标题>-<YYYY-MM-DD>-<ID>/
    ├── report.md
    ├── normalized.json
    ├── raw.json
    ├── transcript.md
    └── media/
        ├── author-avatar.jpg
        ├── cover.jpg
        └── image-01.jpg
```

示例摘要：

```text
Platform: xiaohongshu
Title: Demo note title
Author: Demo Author
Images: 1
Downloads: 3
Report: social-notes/xiaohongshu-demo-note-2026-06-19-demoid/report.md
```

接口样例：

- [`examples/social-content-parser-xhs-sample.json`](examples/social-content-parser-xhs-sample.json)
- [`examples/social-content-parser-douyin-sample.json`](examples/social-content-parser-douyin-sample.json)
- [`examples/social-content-parser-douyin-profile-sample.json`](examples/social-content-parser-douyin-profile-sample.json)
- [`examples/social-content-parser-bilibili-sample.json`](examples/social-content-parser-bilibili-sample.json)

### Video To Text

这个技能用腾讯云 ASR 转写本地音视频，或可公开下载的媒体 URL。不要把抖音 / 小红书 / B 站分享页直接传给 `--url`。把 SecretId/SecretKey 放在 `~/.config/video-to-text/config.json`、被忽略的 `.video-to-text.json`，或环境变量里。可从 `skills/video-to-text/config.example.json` 复制一份起步配置。

```bash
python3 skills/video-to-text/scripts/transcribe_media.py \
  --input ./video.mp4 --output ./transcript.md
python3 skills/video-to-text/scripts/transcribe_media.py \
  --url "https://example.com/video.mp4" --output ./subtitle.srt --sentence-max-length 20
```

### 推荐调用流程：分享链接 → 本地包 → 转写

这两个技能按配对使用。解析免费，应先跑。转写会走付费的腾讯 ASR，只在用户明确要求时再调用。

1. 把两个技能装成兄弟目录：

```bash
npx skills add lgldlk/lgldlk-agent-skills --skill social-content-parser -g -y
npx skills add lgldlk/lgldlk-agent-skills --skill video-to-text -g -y
```

2. 密钥放在技能目录外。优先用 `~/.config/video-to-text/config.json` 里的 `credentialFile`，或 `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY`。
3. 先解析分享链接，先不要加 `--transcribe`：

```bash
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://v.douyin.com/..."
```

4. 需要转写时，对同一条 URL 加上 `--transcribe`。默认 `direct` 模式会把 `normalized.primaryVideo` 交给腾讯，不必先 `--download-video`：

```bash
node skills/social-content-parser/scripts/parse_social.mjs \
  --url "https://v.douyin.com/..." --transcribe --transcript-format md
```

5. 只有 CDN 需要请求头或链接很快过期时，才用 `--transcription-mode local` 并加上 `--download-video`。
6. 抖音主页结果包含多条作品。先解析主页，再对单条作品 URL 转写，不要直接转写主页。
7. 如果手里已经是本地文件，跳过解析器，直接调用 `video-to-text`。

解析器会把 `video-to-text/scripts/transcribe_media.py` 当成兄弟技能自动发现。如果两个技能没有装在一起，用 `--video-to-text-script` 或 `VIDEO_TO_TEXT_SCRIPT` 指定路径。

## 仓库结构

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

## 质量规则

- 每个技能放在 `skills/<skill-name>/SKILL.md`。
- `SKILL.md` frontmatter 只保留 `name` 和 `description`。
- `name` 必须和技能目录名一致。
- 长参考资料放到 `references/`。
- 可重复执行的确定性逻辑放到 `scripts/`。
- 公开技能不能包含 API key、token、cookie、私有 URL 或本地专属绝对路径。

校验仓库：

```bash
scripts/validate-skills.sh
```

## License

MIT
