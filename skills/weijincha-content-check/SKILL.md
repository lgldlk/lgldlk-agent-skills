---
name: weijincha-content-check
description: Check Chinese inline text, local text files, and public HTTP(S) text-file links for prohibited, advertising, sexual, violent, political, platform-specific, and industry-specific risk terms through the Weijincha multi-scope endpoint. Use when Codex needs to review Xianyu listings, chat copy, attached text-like files, linked copy files, content for Xiaohongshu, Douyin, Kuaishou, Bilibili, WeChat, Taobao, JD, Pinduoduo, or e-commerce, health, beauty, education, and game compliance wording.
---

# Weijincha Content Check

Use the bundled CLI to submit public-facing Chinese copy, local text files, or public text-file URLs to the selected risk scope and return normalized JSON.

## Workflow

1. Select the narrowest applicable scope. Use `xianyu` for Xianyu titles, descriptions, and public chat templates.
2. Run `scripts/check_text.py` with `--text`, `--file`, `--url`, or stdin.
3. Inspect `success`, `passed`, `words`, and each scope result. Treat matches as review signals, not legal conclusions.
4. Explain false-positive risk and manually review normal second-hand descriptions, brand names, and contextual quotations.
5. When integrating into an application, call the provider from the backend, add a timeout, cache identical text, limit request frequency, and retain a local deterministic fallback.

## Commands

Check one scope:

```bash
python scripts/check_text.py --scope xianyu --text '支持私下交易，拍前私聊确认。' --pretty
```

Combine several scopes:

```bash
python scripts/check_text.py --scope xianyu --scope ban --scope ad --text '待检测文案' --pretty
```

Read from stdin when the text is long:

```bash
python scripts/check_text.py --scope xianyu --pretty
```

Then provide the text on stdin.

Check a local text-like file:

```bash
python scripts/check_text.py --scope xianyu --file ./listing-copy.md --pretty
```

Check a public text-file link:

```bash
python scripts/check_text.py --scope xianyu --url 'https://example.com/listing.txt' --pretty
```

Repeat `--file` or `--url` to audit several sources. Long sources are split into bounded chunks and results include character and line locations.

## Interpretation

- `success=false`: The provider request or response failed. Do not interpret this as approval.
- `passed=true`: The provider returned no matched words. Do not promise that the content will pass platform review.
- `passed=false`: Review every matched phrase in context. Block only when local policy assigns a blocking severity.
- Different calls can return different phrase grouping. Deduplicate matches and avoid exact-output snapshot assumptions.

## Safety and Reliability

- Submit only public listing copy. Never send card codes, passwords, cookies, tokens, personal data, or unredacted automatic-delivery payloads.
- Inspect only text-like files. Reject binary files, private-network URLs, credential-bearing URLs, oversized sources, and unsupported encodings.
- Do not call the provider directly from browser code; its CORS policy is restricted.
- Do not depend on this undocumented endpoint as the sole publishing gate or represent it as an official Xianyu service.
- Obtain provider permission before production use and keep the endpoint replaceable.
- Validate scopes against the bundled allowlist; never interpolate arbitrary user input into the provider URL.

Read [references/api.md](references/api.md) for endpoint details, supported scopes, response semantics, and known limitations.
Read [references/files.md](references/files.md) when reviewing local files or remote file links.
