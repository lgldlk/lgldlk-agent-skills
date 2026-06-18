---
name: api-data-research
description: Research and compare official and third-party API data-access options for a platform, product, content source, or data vendor. Use when the user asks to verify API docs, compare vendors, confirm exact fields such as text/media/links/likes/views/comments, include pricing/value/stability/operating years, produce a capability matrix, create a cited Markdown note, or export the matrix/table as an image. Especially use for social/content data APIs where claims must be checked against official docs, OpenAPI schemas, endpoint examples, pricing pages, and community or stability signals.
---

# API Data Research

Produce a document-backed API capability comparison. The goal is not to recommend the loudest vendor; the goal is to verify exact fields from docs and make access, pricing, stability, and confidence visible.

## Research Contract

For each vendor, answer these questions with evidence:

- What exact endpoints or product functions exist?
- What exact fields are documented, using original field names?
- Which requested dimensions are unsupported or only indirectly implied?
- What is the access scope: own authorized account, public lookup, search, scraped public data, login-cookie flow, or sales-gated API?
- What is the pricing unit: per resource, per request, per credit, subscription, or custom quote?
- What is the operating-years口径 and how was it verified?
- What confidence level should be assigned to the fields: docs, sample, or live test?

## Workflow

1. Build the dimension list first.
   - Always include the user's requested fields.
   - For content/social platforms, default to: content text, long-form/full content, images/media URLs, links/entities, likes, comments/replies, shares/reposts/retweets, views/impressions/reads, bookmarks/saves, author/account fields, search/timeline/replies/thread endpoints, pagination, price, access scope, stability, and operating-years口径.

2. Search from primary sources outward.
   - Official/first-party: API reference, data dictionary, endpoint docs, OpenAPI/Swagger, pricing, rate limits, changelog, status page.
   - Third-party: OpenAPI files, endpoint pages, `llms.txt`, SDK docs, pricing pages, status pages.
   - Stability/community: GitHub issues/releases, developer forum, Reddit/Hacker News/Product Hunt only as secondary signals.
   - If a vendor is named by the user, search at least three query patterns before marking a field as unresolved.

3. Extract fields from schemas and examples.
   - Prefer OpenAPI/Swagger schemas, response examples, endpoint parameter tables, and data dictionaries.
   - Keep original field names exactly, e.g. `public_metrics.like_count`, `media_url_https`, `engagement.views`.
   - Do not infer a field from words like "analytics", "monitoring", "insights", or "social listening".
   - If the docs only say an endpoint exists, mark fields as `能力可见，字段待确认`.
   - Separate `文档确认`, `样例确认`, and `实测确认`. If no API key is available, say the result is doc-level only.
   - For live tests, only use API keys explicitly provided by the user or already present in environment variables. Never write keys into reports, screenshots, logs, or notes.

4. Validate price, limits, and access.
   - Record unit basis: per request, per returned resource, per credit, subscription, trial quota, or商务报价.
   - Include auth mode, rate limit, page size, pagination cursor, historical depth, and login/account requirement when documented.
   - If current price is only visible after login or sales contact, write `公开价格待确认`.

5. Verify operating years with an explicit口径.
   - Prefer public "founded / launched / since" statements.
   - If unavailable, use domain RDAP/WHOIS registration date or earliest public docs/changelog as `公开可核验起点`.
   - Label fallback dates clearly; never present domain age as company age.

6. Produce the shortest useful output first.
   - Start with 3-6 concise conclusions.
   - Include a capability matrix and, when fields matter, a field-alignment table.
   - Use direct capability wording: "returns `like_count` and `media_url_https`" rather than "适合舆情监测".
   - Save a Markdown note when the user asks for a reusable record or the project instructions require it.

## Evidence Levels

Use these confidence labels internally and surface them when useful:

- `明确可取`: official docs or schema names the field.
- `样例可见`: sample response contains it, but schema/table does not clearly define it.
- `实测可取`: live API call returned the field for the tested sample.
- `能力可见，字段待确认`: docs say the endpoint/function exists, but no response field dictionary is public.
- `未确认`: not found after multiple searches.
- `不支持`: docs explicitly exclude the field or show a different scope.

Maintain a source ledger while researching:

| Vendor | Source URL | Source type | Evidence extracted | Confidence |
|---|---|---|---|---|

Source type examples: `official docs`, `OpenAPI schema`, `pricing`, `status`, `RDAP`, `community`.

## Search Patterns

When the user challenges missing research, or when a vendor is important, rerun with:

- `site:{vendor-domain} {platform} API {field}`
- `site:{docs-domain} openapi {endpoint}`
- `{vendor} llms.txt`
- `{vendor} OpenAPI Swagger API reference`
- `{vendor} pricing credits {platform}`
- `{vendor} founded launched since`
- `{vendor} status API outage`
- `{vendor} API docs {field_name}`

## Output Tables

Use this minimum capability matrix:

| 方案 | 公开起点 / 运营年限口径 | 正文内容 | 图片 / 链接 | 点赞 / 互动指标 | 价格 / 计费 | 稳定性 / 信度 | 备注 |
|---|---:|---|---|---|---|---|---|

Use this field-alignment table when the user asks for concrete fields:

| 维度 | 官方 API | 第三方 A | 第三方 B | 第三方 C |
|---|---|---|---|---|
| 正文内容 | ... | ... | ... | ... |
| 图片 / 媒体 | ... | ... | ... | ... |
| 链接 / entities | ... | ... | ... | ... |
| 点赞 | ... | ... | ... | ... |
| 浏览 / 阅读 / 展示 | ... | ... | ... | ... |
| 评论 / 回复 | ... | ... | ... | ... |
| 转发 / 分享 | ... | ... | ... | ... |
| 收藏 / 书签 | ... | ... | ... | ... |

Add a compact vendor-detail section when decisions depend on nuance:

```markdown
### Vendor
- Endpoints checked:
- Fields confirmed:
- Pricing:
- Access limits:
- Operating-years口径:
- Confidence:
- Gaps:
```

## Exporting Table Images

When the user asks to export a matrix/table as an image:

1. Save or identify the Markdown source.
2. Create a picture-friendly short table if the source table is too wide or field-heavy. Keep exact field names in the Markdown note and use concise labels in the PNG.
3. Resolve the script path relative to this skill directory, then use `scripts/render_markdown_table_png.py`:
   ```bash
   python3 path/to/api-data-research/scripts/render_markdown_table_png.py \
     --input path/to/report.md \
     --heading "数据维度能力矩阵" \
     --output path/to/matrix.png \
     --title "平台 API 数据方案调研"
   ```
4. Inspect the PNG visually if image viewing is available.
5. If text is clipped or unreadable, rerun with larger `--width`, `--row-height`, `--first-col-width`, smaller `--body-font-size`, or a shorter picture-specific table.
6. Use `--max-row-height` only when truncation is acceptable; the script will add `...` and warn if it clips content.

## Common Pitfalls

- Do not equate official API "Article create/manage" with public retrieval of arbitrary third-party long-form article content unless docs clearly say so.
- Do not call a vendor a "舆情监测 API" unless docs expose concrete monitoring/search/alert functions. Prefer listing exact functions.
- Do not mix backend/private account analytics with public front-end metrics. Label access scope: own authorized account, public post lookup, search, scraped public data, or login-cookie based.
- Do not treat `views`, `impressions`, `reads`, and `video views` as interchangeable. Keep the source's metric names.
- Do not recommend only based on SEO visibility. Include smaller vendors if docs expose better fields.
- Do not put exhaustive field dictionaries into a PNG. Images are for comparison; Markdown is for full traceability.

## Final Quality Check

Before finalizing, verify:

- Every recommended vendor has at least one primary source.
- Every requested field dimension is either filled, marked `未确认`, or marked `不支持`.
- Pricing and operating years include their口径.
- Third-party claims are not stated as official platform capabilities.
- The final answer gives links to sources used when web research was performed.
