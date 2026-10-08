# Weijincha Endpoint Reference

## Endpoint

```text
POST https://nmapi.qikekeji.com/weijincha/aiCheck/{scope}/
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
```

Form fields:

| Field | Required | Value |
|---|---:|---|
| `text` | yes | Public-facing Chinese text to inspect |
| `scope` | yes | The same validated value used in the URL path |
| `mode` | yes | `ai` |

The website also exposes `keyword` and `local` modes. This skill intentionally supports only the tested remote `ai` endpoint. Local mode is implemented by website JavaScript rather than this HTTP endpoint.

## Supported Scopes

| Group | Scope | Meaning |
|---|---|---|
| General | `ban` | Prohibited terms |
| General | `ad` | Advertising-law wording |
| General | `sex` | Sexual content |
| General | `violence` | Violence and terrorism |
| General | `politics` | Political sensitivity |
| Platform | `xianyu` | Xianyu |
| Platform | `xhs` | Xiaohongshu |
| Platform | `douyin` | Douyin |
| Platform | `kuaishou` | Kuaishou |
| Platform | `bilibili` | Bilibili |
| Platform | `wechat` | WeChat |
| Platform | `taobao` | Taobao and Tmall |
| Platform | `jd` | JD |
| Platform | `pdd` | Pinduoduo |
| Industry | `ecom` | E-commerce |
| Industry | `health` | Health and medical |
| Industry | `beauty` | Beauty and cosmetics |
| Industry | `education` | Education |
| Industry | `game` | Games |

## Responses

Successful provider response:

```json
{
  "status": 1,
  "data": {
    "words": ["私下交易", "私聊"]
  },
  "req_id": "provider-request-id"
}
```

Application-level error responses may still use HTTP 200:

```json
{
  "status": 0,
  "error": "无效的文本",
  "req_id": "provider-request-id"
}
```

Always validate both the HTTP response and JSON `status`.

## Observed Behavior

- Typical response time during testing was roughly 0.9 to 2.5 seconds.
- No authentication was required during testing.
- The same input can return slightly different matches or phrase grouping across calls.
- Platform scopes overlap. For example, a Xianyu check may also flag advertising-law language.
- Normal second-hand wording can be a false positive; `九成新` was flagged in one test.
- Obfuscated wording can be returned as noisy single-character matches.
- The endpoint accepts some invalid or mismatched parameters instead of rejecting them, so callers must enforce their own allowlist.
- Browser CORS responses were restricted to `https://weijincha.com`; use a controlled backend adapter.

## Production Guardrails

1. Treat the endpoint as undocumented and replaceable.
2. Set a short timeout and do not retry successful responses merely to seek a different result.
3. Rate-limit requests and cache by normalized text hash plus scope.
4. Log `req_id`, latency, selected scope, and normalized matches, but do not log sensitive source text.
5. Combine the provider with local deterministic rules and a manual-review state.
6. Do not send credentials, delivery codes, cookies, tokens, or personal data.
