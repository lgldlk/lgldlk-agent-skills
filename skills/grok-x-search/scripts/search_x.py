#!/usr/bin/env python3
"""Search X posts through Grok's Responses API and native x_search tool."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4.6"
DEFAULT_SEARCH_MODEL = "grok-4.6"
DEFAULT_LIMIT = 20
DEFAULT_RETRIES = 3
DEFAULT_SEARCH_TYPE = "web"
DEFAULT_SEARCH_SCOPE = "strict"
DEFAULT_STREAM = True
TRANSIENT_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
X_POST_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x\.com|twitter\.com)/[A-Za-z0-9_]{1,15}/status/\d+"
)


def config_path() -> Path:
    override = os.getenv("GROK_X_SEARCH_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a JSON object")
    return data


def first_value(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "")), None)


def responses_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if re.fullmatch(r"https?://[^/]+", normalized):
        return f"{normalized}/v1/responses"
    return f"{normalized}/responses"


def parse_sse_event(lines: list[str]) -> tuple[str | None, str | None]:
    """Parse one SSE event block into (event_name, data)."""
    event: str | None = None
    data_parts: list[str] = []
    for line in lines:
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_parts.append(line[len("data:"):].strip())
    data = "\n".join(data_parts) if data_parts else None
    return event, data


def exclusive_to_date(value: str) -> str:
    """Return the next calendar day for x_search's exclusive to_date."""
    inclusive = date.fromisoformat(value)
    try:
        return date.fromordinal(inclusive.toordinal() + 1).isoformat()
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            f"--to-date {value} cannot be converted to x_search's exclusive end date"
        ) from exc


def date_window_instruction(from_date: str | None, to_date: str | None) -> str:
    """Describe the user-facing inclusive date window."""
    if from_date and to_date:
        return (
            f"Only include items dated from {from_date} through {to_date} inclusive (UTC). "
            "Drop anything outside that window."
        )
    if from_date:
        return f"Only include items dated on or after {from_date} (UTC, inclusive)."
    if to_date:
        return f"Only include items dated on or before {to_date} (UTC, inclusive)."
    return ""


def new_stream_state() -> dict[str, Any]:
    return {
        "text_parts": [],
        "output_items": {},
        "final_data": None,
        "failed": None,
    }


def consume_stream_object(state: dict[str, Any], event: str | None, obj: dict[str, Any]) -> None:
    event_name = event or obj.get("type")
    if event_name in ("response.completed", "response.incomplete"):
        inner = obj.get("response")
        if isinstance(inner, dict):
            state["final_data"] = inner
        return
    if event_name == "response.output_text.delta":
        delta = obj.get("delta")
        if isinstance(delta, str):
            state["text_parts"].append(delta)
            sys.stderr.write(delta)
            sys.stderr.flush()
        return
    if event_name == "response.output_item.added":
        item = obj.get("item")
        if isinstance(item, dict):
            state["output_items"][obj.get("output_index", len(state["output_items"]))] = item
            if str(item.get("type", "")).endswith("_search_call"):
                print(
                    f"\n[stream] search tool call: {item.get('type')}",
                    file=sys.stderr,
                )
        return
    if event_name in ("response.failed", "error"):
        detail = obj.get("response") if event_name == "response.failed" else obj
        message = None
        if isinstance(detail, dict):
            error = detail.get("error")
            if isinstance(error, dict):
                message = error.get("message")
            elif isinstance(error, str):
                message = error
            else:
                message = detail.get("message")
        state["failed"] = str(message or event_name)


def consume_sse_block(state: dict[str, Any], lines: list[str]) -> None:
    if not lines:
        return
    event, data = parse_sse_event(lines)
    if not data or data == "[DONE]":
        return
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return
    if isinstance(obj, dict):
        consume_stream_object(state, event, obj)


def stream_result(state: dict[str, Any]) -> dict[str, Any] | None:
    if state["failed"]:
        print(f"Grok API stream failed: {state['failed']}", file=sys.stderr)
        return None
    final_data = state["final_data"]
    if final_data is None:
        if not state["text_parts"] and not state["output_items"]:
            print("Grok API stream ended without a response", file=sys.stderr)
            return None
        final_data = {
            "id": None,
            "status": "incomplete_stream",
            "output": [
                state["output_items"][key]
                for key in sorted(state["output_items"])
                if isinstance(state["output_items"][key], dict)
            ],
            "output_text": "".join(state["text_parts"]),
        }
    print("\n", file=sys.stderr)
    return final_data


def send_stream_request(
    endpoint: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: float,
    retries: int,
) -> dict[str, Any] | None:
    """POST the request with stream=true and reassemble the SSE response.

    Streaming keeps bytes flowing through the connection so intermediary
    proxies (e.g. Cloudflare) do not kill long-running search requests.
    Returns the parsed response object, or None after exhausting retries.
    """
    stream_payload = dict(payload, stream=True)
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(stream_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "User-Agent": "grok-x-search/1.0",
            },
            method="POST",
        )
        try:
            state = new_stream_state()
            event_lines: list[str] = []
            with urllib.request.urlopen(request, timeout=timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line == "":
                        consume_sse_block(state, event_lines)
                        event_lines = []
                    else:
                        event_lines.append(line)
                consume_sse_block(state, event_lines)
            return stream_result(state)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code not in TRANSIENT_HTTP_CODES or attempt >= retries:
                print(f"Grok API HTTP {exc.code}: {error_body[:2000]}", file=sys.stderr)
                return None
            retry_after = exc.headers.get("Retry-After")
            try:
                delay = max(0.0, float(retry_after)) if retry_after else 0.0
            except ValueError:
                delay = 0.0
            delay = max(delay, 1.5 * (2**attempt))
            print(
                f"Grok API HTTP {exc.code}; retrying in {delay:g}s "
                f"({attempt + 1}/{retries})",
                file=sys.stderr,
            )
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= retries:
                detail = getattr(exc, "reason", str(exc))
                print(f"Grok API connection error: {detail}", file=sys.stderr)
                return None
            delay = 1.5 * (2**attempt)
            print(
                f"Grok API connection failed; retrying in {delay:g}s "
                f"({attempt + 1}/{retries})",
                file=sys.stderr,
            )
            time.sleep(delay)
    return None


def valid_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc
    return value


def normalize_handle(value: str) -> str:
    handle = value.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        raise argparse.ArgumentTypeError(f"invalid X handle: {value}")
    return handle


def extract_output_text(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    texts: list[str] = []
    annotations: list[dict[str, Any]] = []
    for item in data.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict) or content.get("type") != "output_text":
                continue
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
            for annotation in content.get("annotations", []):
                if isinstance(annotation, dict):
                    annotations.append(annotation)
    if not texts and isinstance(data.get("output_text"), str):
        texts.append(data["output_text"])
    return "\n\n".join(texts).strip(), annotations


def extract_x_post_urls(text: str) -> list[str]:
    """Extract canonical X post URLs from flattened text responses."""
    urls: list[str] = []
    seen: set[str] = set()
    for match in X_POST_URL_RE.finditer(text):
        url = match.group(0).replace("twitter.com", "x.com").replace("www.x.com", "x.com")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def merge_x_post_urls(*groups: list[str]) -> list[str]:
    """Merge canonical X post URLs while preserving first-seen order."""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for url in group:
            if url not in seen:
                seen.add(url)
                merged.append(url)
    return merged


def extract_search_sources(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect sources exposed by web_search/x_search call objects."""
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in data.get("output", []):
        if not isinstance(item, dict) or not item.get("type", "").endswith("_search_call"):
            continue
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        for source in action.get("sources", []):
            if not isinstance(source, dict) or not isinstance(source.get("url"), str):
                continue
            url = source["url"]
            if url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "url": url,
                    "type": action.get("type"),
                    "title": source.get("title"),
                }
            )
    return sources


def build_prompt(
    query: str,
    limit: int,
    extra_instruction: str | None,
    sort_order: str,
    language: str | None,
    search_type: str,
    search_scope: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> str:
    scale_instruction = (
        "Make multiple search tool calls when necessary, especially because the requested "
        "count is greater than 20. Deduplicate by canonical post URL."
        if limit > 20
        else "Deduplicate results by canonical post URL."
    )
    language_instruction = (
        f"\nPrefer posts written in {language} when language is relevant."
        if language
        else ""
    )
    date_instruction = date_window_instruction(from_date, to_date)
    if date_instruction:
        date_instruction = f"\n{date_instruction}"
    sort_instruction = (
        "Order results by newest first."
        if sort_order == "recent"
        else "Order results by relevance."
    )
    tool_name = {
        "x": "x_search",
        "web": "web_search",
        "hybrid": "web_search and x_search",
    }[search_type]
    if search_type == "x":
        source_scope = "Search X posts only."
    elif search_type == "hybrid":
        source_scope = (
            "Use web_search and x_search. Prefer X posts, and label the source type for "
            "each result."
        )
    elif search_scope == "strict":
        source_scope = (
            "Search public web pages, but restrict the search scope to individual X posts "
            "only. Add `site:x.com` or `site:twitter.com` to every web search query. "
            "Prefer canonical URLs matching `https://x.com/<handle>/status/<numeric_id>`."
        )
    else:
        source_scope = (
            "Use web_search with a prompt-level X constraint. Search X posts first and use "
            "`site:x.com` or `site:twitter.com` in the query. Prefer individual X posts "
            "and their direct URLs, but allow relevant non-X pages when they add useful "
            "context or when an X post is unavailable. This is a preference, not a hard "
            "domain filter."
        )
    if search_type == "web" and search_scope == "strict":
        url_instruction = (
            "For every result, provide the complete original X post URL. The URL must be a "
            "direct post URL in the form `https://x.com/<handle>/status/<numeric_id>`."
        )
        result_kind = "distinct X posts"
        output_contract = """
Only return real X posts. Do not return general news pages, profile pages, X search pages,
bookmarks, intents, generated links, or a search strategy. Do not return XML, tool-call
syntax, or a description of what you will search; perform the search and return the final
results directly. If a page is not an individual post, exclude it.
""".strip()
    elif search_type == "web":
        url_instruction = (
            "For X results, provide the complete original X post URL when available. "
            "For other sources, provide the direct source URL."
        )
        result_kind = "distinct relevant results"
        output_contract = """
Prefer X posts, but relevant non-X pages are allowed when they provide useful context.
Never invent URLs or turn a profile, search page, or generated link into a post URL.
Return final results directly; do not return XML, tool-call syntax, or a search strategy.
""".strip()
    else:
        url_instruction = (
            "For X results, provide the complete direct x.com post URL."
            if search_type == "x"
            else "For each result, provide the direct source URL and label whether it is an X post or web source."
        )
        result_kind = "distinct X posts" if search_type == "x" else "distinct results"
        output_contract = ""
    prompt = f"""
Current date is {date.today().isoformat()}. Treat this as the authoritative current date
for relative-date interpretation; do not reject a request as future solely because your
internal date differs.

Use {tool_name} to retrieve results. {source_scope}

Search query:
{f"(site:x.com OR site:twitter.com) {query}" if search_type == "web" and search_scope == "strict" else query}

Return up to {limit} {result_kind}. {scale_instruction}
Prefer original, information-rich sources over
near-identical reposts unless repost activity itself is relevant.
{language_instruction}{date_instruction}

For every result, provide:
1. rank
2. author or source name
3. post date/time when available
4. a concise faithful excerpt or summary
5. why it matches the request
6. {url_instruction}

{sort_instruction} Do not invent posts,
URLs, dates, authors, engagement numbers, or quotations. If fewer than {limit} suitable posts
are available, return the available posts and explicitly state the actual count.
{output_contract}
""".strip()
    if extra_instruction:
        prompt += f"\n\nAdditional user instruction:\n{extra_instruction.strip()}"
    return prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search with Grok Responses API tools.")
    parser.add_argument("query", help="Search topic or natural-language request")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Target number of distinct posts (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument("--base-url", help="Responses-compatible API base URL")
    parser.add_argument("--api-key", help=argparse.SUPPRESS)
    parser.add_argument("--model", help="Request model override")
    parser.add_argument(
        "--search-model",
        help=f"X Search request model override (default: {DEFAULT_SEARCH_MODEL})",
    )
    parser.add_argument("--from-date", type=valid_date, help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument("--to-date", type=valid_date, help="Inclusive end date, YYYY-MM-DD")
    parser.add_argument(
        "--allow-handle",
        action="append",
        default=[],
        type=normalize_handle,
        metavar="HANDLE",
        help="Only search this X account; repeat up to 20 times",
    )
    parser.add_argument(
        "--exclude-handle",
        action="append",
        default=[],
        type=normalize_handle,
        metavar="HANDLE",
        help="Exclude this X account; repeat up to 20 times",
    )
    parser.add_argument("--images", action="store_true", help="Enable image understanding")
    parser.add_argument("--videos", action="store_true", help="Enable video understanding")
    parser.add_argument(
        "--search-type",
        choices=("x", "web", "hybrid"),
        default=None,
        help="Search mode: x, web, or hybrid (default: configured value or web)",
    )
    parser.add_argument(
        "--search-scope",
        choices=("strict", "loose"),
        default=None,
        help="Web scope: strict X-only or loose X-preferred (default: strict)",
    )
    parser.add_argument(
        "--sort",
        choices=("relevance", "recent"),
        default="relevance",
        help="Result ordering (default: relevance)",
    )
    parser.add_argument(
        "--language",
        help="Preferred post language, for example Chinese or English",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "low", "medium", "high"),
        help="Optional Grok reasoning effort",
    )
    parser.add_argument("--extra-instruction", help="Additional ranking or output requirement")
    parser.add_argument("--timeout", type=float, default=300, help="HTTP timeout in seconds")
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retries for transient API failures (default: {DEFAULT_RETRIES})",
    )
    stream_group = parser.add_mutually_exclusive_group()
    stream_group.add_argument(
        "--stream",
        dest="stream",
        action="store_true",
        default=None,
        help="Use streaming SSE requests (default: on; keeps proxies from timing out)",
    )
    stream_group.add_argument(
        "--no-stream",
        dest="stream",
        action="store_false",
        help="Use a single non-streaming request instead",
    )
    parser.add_argument("--raw", action="store_true", help="Print the complete API response")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print endpoint and request payload without calling the API",
    )
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.query.strip():
        parser.error("query must not be empty")
    if args.limit < 1:
        parser.error("--limit must be a positive integer")
    if args.allow_handle and args.exclude_handle:
        parser.error("--allow-handle and --exclude-handle cannot be combined")
    if len(args.allow_handle) > 20:
        parser.error("--allow-handle accepts at most 20 handles")
    if len(args.exclude_handle) > 20:
        parser.error("--exclude-handle accepts at most 20 handles")
    if args.from_date and args.to_date and args.from_date > args.to_date:
        parser.error("--from-date must not be later than --to-date")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    if args.retries < 0:
        parser.error("--retries must be zero or greater")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(parser, args)

    try:
        config = load_config()
    except ValueError as exc:
        parser.error(str(exc))

    base_url = first_value(
        args.base_url,
        os.getenv("GROK_BASE_URL"),
        os.getenv("XAI_BASE_URL"),
        config.get("base_url"),
        DEFAULT_BASE_URL,
    )
    model = first_value(
        args.search_model,
        args.model,
        os.getenv("GROK_SEARCH_MODEL"),
        os.getenv("GROK_MODEL"),
        config.get("search_model"),
        config.get("default_model"),
        config.get("model"),
        DEFAULT_SEARCH_MODEL,
    )
    search_type = first_value(
        args.search_type,
        os.getenv("GROK_SEARCH_TYPE"),
        config.get("search_type"),
        DEFAULT_SEARCH_TYPE,
    )
    if search_type not in {"x", "web", "hybrid"}:
        parser.error("search type must be x, web, or hybrid")
    search_scope = first_value(
        args.search_scope,
        os.getenv("GROK_SEARCH_SCOPE"),
        config.get("search_scope"),
        DEFAULT_SEARCH_SCOPE,
    )
    if search_scope not in {"strict", "loose"}:
        parser.error("search scope must be strict or loose")
    stream = first_value(
        args.stream,
        os.getenv("GROK_X_SEARCH_STREAM"),
        config.get("stream"),
        DEFAULT_STREAM,
    )
    if isinstance(stream, str):
        stream = stream.lower() not in {"0", "false", "no", "off"}
    api_key = first_value(
        args.api_key,
        os.getenv("GROK_API_KEY"),
        os.getenv("XAI_API_KEY"),
        config.get("api_key"),
    )

    tools: list[dict[str, Any]] = []
    if search_type in ("x", "hybrid"):
        tools.append({"type": "x_search"})
    if search_type in ("web", "hybrid"):
        web_tool: dict[str, Any] = {"type": "web_search"}
        # In strict scope, use the provider's domain filter as a hard boundary
        # in addition to the prompt-level site restriction.
        if search_scope == "strict":
            web_tool["filters"] = {
                "allowed_domains": ["x.com", "twitter.com"],
            }
        tools.append(web_tool)
    if args.allow_handle and search_type == "web":
        parser.error("--allow-handle requires x or hybrid search mode")
    if args.exclude_handle and search_type == "web":
        parser.error("--exclude-handle requires x or hybrid search mode")
    if args.videos and search_type == "web":
        parser.error("--videos requires x or hybrid search mode")
    if args.allow_handle:
        tools[0]["allowed_x_handles"] = args.allow_handle
    if args.exclude_handle:
        tools[0]["excluded_x_handles"] = args.exclude_handle
    if args.from_date:
        for tool in tools:
            if tool["type"] == "x_search":
                tool["from_date"] = args.from_date
    if args.to_date:
        try:
            exclusive_end = exclusive_to_date(args.to_date)
        except ValueError as exc:
            parser.error(str(exc))
        for tool in tools:
            if tool["type"] == "x_search":
                tool["to_date"] = exclusive_end
    if args.images:
        for tool in tools:
            if tool["type"] in ("x_search", "web_search"):
                tool["enable_image_understanding"] = True
    if args.videos:
        for tool in tools:
            if tool["type"] == "x_search":
                tool["enable_video_understanding"] = True

    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": build_prompt(
                    args.query,
                    args.limit,
                    args.extra_instruction,
                    args.sort,
                    args.language,
                    search_type,
                    search_scope,
                    args.from_date,
                    args.to_date,
                ),
            }
        ],
        "tools": tools,
    }
    if args.reasoning_effort:
        payload["reasoning"] = {"effort": args.reasoning_effort}

    endpoint = responses_endpoint(str(base_url))
    if args.dry_run:
        print(
            json.dumps(
                {"endpoint": endpoint, "payload": payload},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not api_key:
        parser.error(
            "API key is missing. Set GROK_API_KEY/XAI_API_KEY, add it to the "
            "dedicated Grok X Search config file, or run scripts/configure.py"
        )

    data: dict[str, Any] | None
    if stream:
        data = send_stream_request(
            endpoint, payload, str(api_key), args.timeout, args.retries
        )
        if data is None:
            return 1
        if args.raw:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
    else:
        body: str | None = None
        for attempt in range(args.retries + 1):
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "grok-x-search/1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=args.timeout) as response:
                    body = response.read().decode("utf-8")
                break
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                if exc.code not in TRANSIENT_HTTP_CODES or attempt >= args.retries:
                    print(f"Grok API HTTP {exc.code}: {error_body[:2000]}", file=sys.stderr)
                    return 1
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = max(0.0, float(retry_after)) if retry_after else 0.0
                except ValueError:
                    delay = 0.0
                delay = max(delay, 1.5 * (2**attempt))
                print(
                    f"Grok API HTTP {exc.code}; retrying in {delay:g}s "
                    f"({attempt + 1}/{args.retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= args.retries:
                    detail = getattr(exc, "reason", str(exc))
                    print(f"Grok API connection error: {detail}", file=sys.stderr)
                    return 1
                delay = 1.5 * (2**attempt)
                print(
                    f"Grok API connection failed; retrying in {delay:g}s "
                    f"({attempt + 1}/{args.retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)

        if body is None:
            print("Grok API returned no response", file=sys.stderr)
            return 1

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            print("Grok API returned a non-JSON response", file=sys.stderr)
            print(body, file=sys.stderr)
            return 1

        if args.raw:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0

    text, annotations = extract_output_text(data)
    citations = data.get("citations", [])
    sources = extract_search_sources(data)
    source_x_urls = extract_x_post_urls(
        "\n".join(
            source.get("url", "")
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("url"), str)
        )
    )
    extracted_urls = merge_x_post_urls(extract_x_post_urls(text), source_x_urls)
    output_types = [
        item.get("type")
        for item in data.get("output", [])
        if isinstance(item, dict) and isinstance(item.get("type"), str)
    ]
    has_search_call = any(item.endswith("_search_call") for item in output_types)
    posts = [
        {"rank": index, "url": url}
        for index, url in enumerate(extracted_urls, start=1)
    ]
    result = {
        "query": args.query,
        "requested_count": args.limit,
        "model": data.get("model", model),
        "status": data.get("status"),
        "response_id": data.get("id"),
        "endpoint": endpoint,
        "search_execution": "native_tool" if has_search_call else "text_fallback",
        "streamed": bool(stream),
        "search_type": search_type,
        "source_scope": (
            "x_only"
            if search_type == "web" and search_scope == "strict"
            else "x_preferred"
            if search_type == "web"
            else search_type
        ),
        "search_scope": search_scope,
        "output_types": output_types,
        "posts": posts,
        "actual_extracted_count": len(posts),
        "sources": sources,
        "filters": {
            "from_date": args.from_date,
            "to_date": args.to_date,
            "allow_handles": args.allow_handle,
            "exclude_handles": args.exclude_handle,
            "sort": args.sort,
            "language": args.language,
            "images": args.images,
            "videos": args.videos,
        },
        "text": text,
        "citations": citations if isinstance(citations, list) else [],
        "annotations": annotations,
        "usage": data.get("usage"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
