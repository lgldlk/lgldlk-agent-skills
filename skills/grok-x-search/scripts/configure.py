#!/usr/bin/env python3
"""Interactively store Grok X Search connection settings."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path


DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4.6"
DEFAULT_SEARCH_MODEL = "grok-4.6"
DEFAULT_SEARCH_TYPE = "web"
DEFAULT_SEARCH_SCOPE = "strict"


def config_path() -> Path:
    override = os.getenv("GROK_X_SEARCH_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "config.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Grok X Search")
    parser.add_argument("--base-url", help="Responses-compatible API base URL")
    parser.add_argument("--model", help="Default request model")
    parser.add_argument("--search-model", help="Default X Search request model")
    parser.add_argument(
        "--search-type",
        choices=("x", "web", "hybrid"),
        help="Default search mode: x, web, or hybrid",
    )
    parser.add_argument(
        "--search-scope",
        choices=("strict", "loose"),
        help="Default web scope: strict X-only or loose X-preferred",
    )
    parser.add_argument("--api-key", help=argparse.SUPPRESS)
    parser.add_argument("--path", type=Path, help="Override config file path")
    args = parser.parse_args()

    path = (args.path or config_path()).expanduser()
    base_url = args.base_url or input(f"Base URL [{DEFAULT_BASE_URL}]: ").strip()
    model = args.model or input(f"Default model [{DEFAULT_MODEL}]: ").strip()
    search_model = args.search_model or input(
        f"Default search model [{DEFAULT_SEARCH_MODEL}]: "
    ).strip()
    search_type = args.search_type or input(
        f"Default search type [{DEFAULT_SEARCH_TYPE}]: "
    ).strip().lower()
    search_scope = args.search_scope or input(
        f"Default search scope [{DEFAULT_SEARCH_SCOPE}]: "
    ).strip().lower()
    api_key = args.api_key or getpass.getpass("API key (input hidden): ").strip()

    base_url = base_url or DEFAULT_BASE_URL
    model = model or DEFAULT_MODEL
    search_model = search_model or model or DEFAULT_SEARCH_MODEL
    search_type = search_type or DEFAULT_SEARCH_TYPE
    search_scope = search_scope or DEFAULT_SEARCH_SCOPE
    if search_type not in {"x", "web", "hybrid"}:
        parser.error("search type must be x, web, or hybrid")
    if search_scope not in {"strict", "loose"}:
        parser.error("search scope must be strict or loose")
    if not api_key:
        parser.error("API key cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        json.dumps(
            {
                "base_url": base_url.rstrip("/"),
                "api_key": api_key,
                "default_model": model,
                "search_model": search_model,
                "search_type": search_type,
                "search_scope": search_scope,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    print(f"Saved Grok X Search configuration to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
