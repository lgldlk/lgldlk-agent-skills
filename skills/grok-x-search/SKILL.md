---
name: grok-x-search
description: Search, filter, and summarize real-time X posts through Grok. Defaults to web_search constrained to X post pages with direct x.com status links; supports native x_search when explicitly selected, filters, retries, and traceable citations.
---

# Grok X Search

Use `scripts/search_x.py` for X, web, or mixed research. It calls a
Responses-compatible endpoint and enables `x_search`, `web_search`, or both. The default is
`web` with `strict` scope: public web search is constrained to individual X post pages and
requires direct `x.com/<handle>/status/<id>` links. Use `--search-scope loose` when X should
remain the priority but relevant non-X context is also acceptable. Use `x` only when an
official xAI key and native `x_search` access are available; use `hybrid` only when both
sources are needed.

## Operating procedure

1. Translate the user's request into one focused search query.
2. Preserve explicit constraints:
   - result count, with `--limit` (default `20`)
   - inclusive dates, with `--from-date` and `--to-date`
   - account allowlist or blocklist, with repeated `--allow-handle` or `--exclude-handle`
   - media analysis, with `--images` or `--videos`
   - ordering, with `--sort relevance` or `--sort recent`
   - preferred language, with `--language Chinese` or another language name
   - search source, with `--search-type x|web|hybrid` (default `web`)
   - web strictness, with `--search-scope strict|loose` (default `strict`)
3. Run the script and parse its JSON output.
4. Present the model's summaries together with direct `x.com` URLs and the returned
   `citations` list. The script also extracts and deduplicates `x.com` and `twitter.com`
   status URLs when a gateway flattens tool results into final text. Do not invent authors,
   dates, metrics, quotes, or URLs.
5. State the actual number of usable posts when it is lower than requested.

Requests stream by default (`stream: true`, SSE): text deltas are echoed to stderr as they
arrive and the final response is reassembled from `response.completed` or
`response.incomplete`, so long searches survive proxies like Cloudflare that kill idle
origins. Disable with `--no-stream` or config key `"stream": false`. A provider `error` or
`response.failed` event exits non-zero. A stream that closes with no response object and no
text also exits non-zero. Text deltas without a completed event are still returned, with
`status` `incomplete_stream`.

For more than 20 results, pass the full count in one call. The prompt asks Grok to make
additional searches and deduplicate canonical post URLs. A requested count is a target,
not a guarantee.

## Models and search modes

There is one Responses API request model. `x_search` is a tool attached to that request,
not a second endpoint or credential. This skill exposes two names so deployments can
choose deliberately:

- `default_model`, the general fallback model
- `search_model`, the model used by this X Search command
- `search_type`, the default source mode, `x`, `web`, or `hybrid`
- `search_scope`, the web mode scope, `strict` or `loose`

Both default to `grok-4.6`. Keep them equal unless the configured
gateway documents separate model names. Override per call with `--search-model`; `--model`
is retained as a general compatibility override.

`web` is the default because it does not require the official xAI `x_search` credential.
In `strict` scope it applies the provider's `allowed_domains` filter for `x.com` and
`twitter.com`, adds `site:x.com`/`site:twitter.com` to the prompt, and permits only
individual post pages. In `loose` scope it removes the hard domain filter, while the prompt
still constrains the search toward X, asks Grok to use site qualifiers, and allows useful
non-X context when necessary.

## Configuration

Configuration is intentionally isolated from Codex and from the user's home config.
The default file is `config.json` beside this `SKILL.md`. It is ignored by the skill's
local `.gitignore`.

Precedence, highest first:

1. CLI flags, `--base-url`, `--api-key`, `--search-model`, `--model`
2. Environment, `GROK_BASE_URL`/`XAI_BASE_URL`, `GROK_API_KEY`/`XAI_API_KEY`,
   `GROK_SEARCH_MODEL`, then `GROK_MODEL`
3. Local `config.json`
4. Defaults, base URL `https://api.x.ai/v1`, model `grok-4.6`

The local schema is:

```json
{
  "base_url": "https://api.x.ai/v1",
  "default_model": "grok-4.6",
  "search_model": "grok-4.6",
  "search_type": "web",
  "search_scope": "strict",
  "api_key": "..."
}
```

Create or update it without putting the key in shell history:

```bash
python3 scripts/configure.py
```

The configurator writes atomically and sets file permissions to `600`. Never print or
summarize the API key. `GROK_X_SEARCH_CONFIG` may point to an explicitly chosen alternate
file; no Codex `config.toml`, `auth.json`, or `OPENAI_API_KEY` is read.

## Reliability and diagnostics

Transient HTTP failures, rate limits, 5xx responses, network errors, and timeouts are
retried with exponential backoff. Tune with `--retries` and `--timeout`; use
`--retries 0` to disable retries. Error bodies are truncated before printing.

Use `--dry-run` to inspect the resolved endpoint, model, filters, and prompt without making
a network request or requiring a key. Use `--raw` only when the complete provider response
is needed for debugging. Normal JSON output includes `posts`, `actual_extracted_count`, and
`search_execution`. The value is `native_tool` when the provider exposes a search-call
object and `text_fallback` when valid X status URLs were recovered from final text.

## Examples

```bash
# Default, 20 relevant posts
python3 scripts/search_x.py "Grok 4.5 user reactions"

# Newest Chinese posts, with images analyzed
python3 scripts/search_x.py "国内 AI 产品发布" \
  --limit 30 --sort recent --language Chinese --images

# Restrict to selected accounts and a date window
python3 scripts/search_x.py "model release announcements" \
  --limit 30 \
  --allow-handle xai \
  --allow-handle elonmusk \
  --from-date 2026-07-01 \
  --to-date 2026-07-23

# Inspect configuration and request construction
python3 scripts/search_x.py "test query" --dry-run

# Explicitly use web_search constrained to X post pages (also the default)
python3 scripts/search_x.py "GPT 新模型新闻" --search-type web --limit 20

# Prefer X, but allow useful context from other web pages
python3 scripts/search_x.py "GPT 新模型新闻" --search-type web --search-scope loose

# Combine web coverage and X discussion
python3 scripts/search_x.py "GPT 新模型" --search-type hybrid --limit 20
```

## Constraints

- Do not combine `--allow-handle` and `--exclude-handle`.
- Each account filter accepts at most 20 handles.
- Dates must use `YYYY-MM-DD` and are inclusive on both ends for the caller.
- `web_search` has no date parameter. Web mode, including the default strict scope, puts
  that inclusive window in the prompt.
- Native `x_search` treats `to_date` as exclusive. The script sends the next calendar day,
  so the requested end date is included. `--to-date 9999-12-31` is rejected because that
  conversion overflows.
- Keep citations when reporting results; they are the traceability layer.
- Accept `text_fallback` as a valid gateway response shape, but distinguish extracted URLs
  from provider citations when describing confidence.
