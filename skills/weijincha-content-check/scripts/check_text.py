#!/usr/bin/env python3
"""Check text, local text files, or remote text URLs with Weijincha."""

from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_TEMPLATE = "https://nmapi.qikekeji.com/weijincha/aiCheck/{scope}/"
DEFAULT_CHUNK_SIZE = 3500
DEFAULT_MAX_CHARS = 100_000
DEFAULT_MAX_FILE_BYTES = 1_048_576
MAX_SOURCES = 20

SCOPES = {
    "ban": "违禁词检测",
    "ad": "广告法检测",
    "sex": "色情检测",
    "violence": "暴恐检测",
    "politics": "涉政检测",
    "xianyu": "闲鱼检测",
    "xhs": "小红书检测",
    "douyin": "抖音检测",
    "kuaishou": "快手检测",
    "bilibili": "B站检测",
    "wechat": "微信检测",
    "taobao": "淘宝/天猫检测",
    "jd": "京东检测",
    "pdd": "拼多多检测",
    "ecom": "电商合规",
    "health": "医疗合规",
    "beauty": "美妆合规",
    "education": "教育合规",
    "game": "游戏合规",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check public Chinese text, local text files, or HTTP(S) text files "
            "for platform and industry risk terms."
        )
    )
    parser.add_argument(
        "--scope",
        action="append",
        choices=tuple(SCOPES),
        help="Detection scope. Repeat to combine scopes. Defaults to xianyu.",
    )
    parser.add_argument("--text", help="Inline text to inspect.")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Local text file to inspect. Repeat to inspect several files.",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Public HTTP(S) text-file URL to inspect. Repeat for several URLs.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds (default: 5).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Characters sent per provider request (default: {DEFAULT_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Maximum decoded characters per source (default: {DEFAULT_MAX_CHARS}).",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help=f"Maximum local or remote file bytes (default: {DEFAULT_MAX_FILE_BYTES}).",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Include each raw provider payload in the normalized result.",
    )
    return parser.parse_args()


def deduplicate(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        word = str(value or "").strip()
        if word and word not in seen:
            seen.add(word)
            result.append(word)
    return result


def decode_text(data: bytes, source_name: str) -> tuple[str, str]:
    if b"\x00" in data[:8192]:
        raise ValueError(f"Binary file is not supported: {source_name}")

    encodings = (
        ("utf-8-sig", "gb18030")
        if data.startswith(b"\xef\xbb\xbf")
        else ("utf-8", "gb18030")
    )
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            return text, encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode text file: {source_name}")


def validate_remote_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Remote file URL must use http or https")
    if not parsed.hostname:
        raise ValueError("Remote file URL has no hostname")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in remote file URLs are not allowed")

    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or default_port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve remote hostname: {parsed.hostname}") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(f"Private or special network target is not allowed: {ip}")
    return parsed


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects to local or private network destinations."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        validate_remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_limited(stream: Any, max_bytes: int, source_name: str) -> bytes:
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds byte limit of {max_bytes}: {source_name}")
    return data


def load_local_file(path_value: str, max_bytes: int) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"File exceeds byte limit of {max_bytes}: {path}")

    with path.open("rb") as file_handle:
        data = read_limited(file_handle, max_bytes, str(path))
    text, encoding = decode_text(data, str(path))
    return {
        "type": "file",
        "name": path.name,
        "location": str(path),
        "bytes": len(data),
        "encoding": encoding,
        "text": text,
    }


def load_remote_file(url: str, timeout: float, max_bytes: int) -> dict[str, Any]:
    parsed = validate_remote_url(url)
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "text/*,application/json,application/xml,application/octet-stream;q=0.5",
            "User-Agent": "weijincha-content-check-skill/1.1",
        },
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            validate_remote_url(final_url)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(f"Remote file exceeds byte limit of {max_bytes}: {url}")
            data = read_limited(response, max_bytes, url)
            content_type = response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Remote file returned HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Unable to download remote file: {url}: {exc.reason}") from exc

    text, encoding = decode_text(data, final_url)
    return {
        "type": "url",
        "name": Path(parsed.path).name or parsed.hostname or "remote-text",
        "location": final_url,
        "bytes": len(data),
        "encoding": encoding,
        "content_type": content_type,
        "text": text,
    }


def split_text(text: str, chunk_size: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    start = 0
    length = len(text)
    separators = ("\n", "。", "！", "？", "；")

    while start < length:
        tentative_end = min(start + chunk_size, length)
        end = tentative_end
        if tentative_end < length:
            search_start = start + max(1, chunk_size // 2)
            candidates = [text.rfind(separator, search_start, tentative_end) for separator in separators]
            split_at = max(candidates)
            if split_at >= search_start:
                end = split_at + 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                {
                    "index": len(chunks) + 1,
                    "char_start": start,
                    "char_end": end,
                    "line_start": text.count("\n", 0, start) + 1,
                    "line_end": text.count("\n", 0, end) + 1,
                    "text": chunk_text,
                }
            )
        start = end
    return chunks


def request_scope(text: str, scope: str, timeout: float, include_raw: bool) -> dict[str, Any]:
    body = urllib.parse.urlencode({"text": text, "scope": scope, "mode": "ai"}).encode("utf-8")
    request = urllib.request.Request(
        API_TEMPLATE.format(scope=scope),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json",
            "User-Agent": "weijincha-content-check-skill/1.1",
        },
    )

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.status
            raw_body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "success": False,
            "scope": scope,
            "scope_name": SCOPES[scope],
            "words": [],
            "error": str(exc),
            "latency_ms": round((time.monotonic() - started) * 1000),
        }

    latency_ms = round((time.monotonic() - started) * 1000)
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return {
            "success": False,
            "scope": scope,
            "scope_name": SCOPES[scope],
            "words": [],
            "error": f"Invalid JSON response: {exc}",
            "http_status": status_code,
            "latency_ms": latency_ms,
        }

    result: dict[str, Any] = {
        "success": status_code == 200 and payload.get("status") == 1,
        "scope": scope,
        "scope_name": SCOPES[scope],
        "words": deduplicate(payload.get("data", {}).get("words", [])),
        "req_id": payload.get("req_id"),
        "http_status": status_code,
        "latency_ms": latency_ms,
    }
    if not result["success"]:
        result["error"] = payload.get("error") or payload.get("message") or "Provider error"
    if include_raw:
        result["raw"] = payload
    return result


def audit_source(
    source: dict[str, Any],
    scopes: list[str],
    timeout: float,
    chunk_size: int,
    include_raw: bool,
) -> dict[str, Any]:
    text = source.pop("text")
    chunks = split_text(text, chunk_size)
    chunk_results: list[dict[str, Any]] = []

    for chunk in chunks:
        provider_results = [
            request_scope(chunk["text"], scope, timeout, include_raw) for scope in scopes
        ]
        words = deduplicate(
            [
                word
                for result in provider_results
                if result.get("success")
                for word in result.get("words", [])
            ]
        )
        chunk_results.append(
            {
                key: value for key, value in chunk.items() if key != "text"
            }
            | {
                "success": all(result.get("success") for result in provider_results),
                "words": words,
                "results": provider_results,
            }
        )

    words = deduplicate(
        [word for chunk in chunk_results for word in chunk.get("words", [])]
    )
    successful = bool(chunk_results) and all(chunk.get("success") for chunk in chunk_results)
    return {
        **source,
        "chars": len(text),
        "chunk_count": len(chunk_results),
        "success": successful,
        "passed": successful and not words,
        "words": words,
        "chunks": chunk_results,
    }


def build_sources(args: argparse.Namespace) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    if args.text is not None and args.text.strip():
        sources.append(
            {
                "type": "inline",
                "name": "inline-text",
                "location": None,
                "bytes": len(args.text.encode("utf-8")),
                "encoding": "utf-8",
                "text": args.text,
            }
        )

    for path_value in args.file:
        sources.append(load_local_file(path_value, args.max_file_bytes))
    for url in args.url:
        sources.append(load_remote_file(url, args.timeout, args.max_file_bytes))

    if not sources and args.text is None and not args.file and not args.url:
        stdin_text = sys.stdin.read()
        if stdin_text.strip():
            sources.append(
                {
                    "type": "stdin",
                    "name": "stdin",
                    "location": None,
                    "bytes": len(stdin_text.encode("utf-8")),
                    "encoding": "utf-8",
                    "text": stdin_text,
                }
            )
    return sources


def emit(payload: dict[str, Any], pretty: bool) -> None:
    json.dump(
        payload,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    sys.stdout.write("\n")


def main() -> int:
    args = parse_args()

    if args.timeout <= 0:
        emit({"success": False, "passed": False, "words": [], "error": "Timeout must be positive"}, args.pretty)
        return 2
    if args.chunk_size <= 0:
        emit({"success": False, "passed": False, "words": [], "error": "chunk-size must be positive"}, args.pretty)
        return 2
    if args.max_chars <= 0 or args.max_file_bytes <= 0:
        emit({"success": False, "passed": False, "words": [], "error": "Limits must be positive"}, args.pretty)
        return 2
    if args.chunk_size > args.max_chars:
        emit({"success": False, "passed": False, "words": [], "error": "chunk-size cannot exceed max-chars"}, args.pretty)
        return 2

    try:
        sources = build_sources(args)
    except ValueError as exc:
        emit({"success": False, "passed": False, "words": [], "error": str(exc)}, args.pretty)
        return 2

    if not sources:
        emit({"success": False, "passed": False, "words": [], "error": "No non-empty text source provided"}, args.pretty)
        return 2
    if len(sources) > MAX_SOURCES:
        emit({"success": False, "passed": False, "words": [], "error": f"At most {MAX_SOURCES} sources are allowed"}, args.pretty)
        return 2

    oversized = [source["name"] for source in sources if len(source["text"]) > args.max_chars]
    if oversized:
        emit(
            {
                "success": False,
                "passed": False,
                "words": [],
                "error": f"Source exceeds character limit of {args.max_chars}: {oversized[0]}",
            },
            args.pretty,
        )
        return 2

    scopes = list(dict.fromkeys(args.scope or ["xianyu"]))
    source_results = [
        audit_source(source, scopes, args.timeout, args.chunk_size, args.raw)
        for source in sources
    ]
    words = deduplicate(
        [word for source in source_results for word in source.get("words", [])]
    )
    all_successful = all(source.get("success") for source in source_results)

    emit(
        {
            "success": all_successful,
            "passed": all_successful and not words,
            "provider": "weijincha-experimental",
            "scopes": scopes,
            "source_count": len(source_results),
            "words": words,
            "sources": source_results,
        },
        args.pretty,
    )
    return 0 if all_successful else 3


if __name__ == "__main__":
    raise SystemExit(main())
