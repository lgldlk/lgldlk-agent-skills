from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_DIR = Path(__file__).parents[1]
SEARCH_PATH = SKILL_DIR / "scripts" / "search_x.py"
CONFIGURE_PATH = SKILL_DIR / "scripts" / "configure.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


search_x = load_module("grok_x_search", SEARCH_PATH)


class FakeHTTPResponse:
    def __init__(self, body: str):
        self._lines = body.splitlines(keepends=True)

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def __iter__(self):
        for line in self._lines:
            yield line.encode()


def dry_run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SEARCH_PATH), *args, "--dry-run"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


class DateWindowTests(unittest.TestCase):
    def test_web_mode_puts_inclusive_dates_in_the_prompt_only(self) -> None:
        payload = dry_run(
            "model release",
            "--search-type",
            "web",
            "--from-date",
            "2026-07-01",
            "--to-date",
            "2026-07-23",
        )
        prompt = payload["payload"]["input"][0]["content"]
        self.assertIn("from 2026-07-01 through 2026-07-23 inclusive", prompt)
        self.assertEqual(
            payload["payload"]["tools"],
            [{"type": "web_search", "filters": {"allowed_domains": ["x.com", "twitter.com"]}}],
        )

    def test_x_mode_sends_exclusive_end_date(self) -> None:
        payload = dry_run(
            "model release",
            "--search-type",
            "x",
            "--from-date",
            "2026-07-01",
            "--to-date",
            "2026-07-31",
        )
        self.assertEqual(
            payload["payload"]["tools"],
            [{"type": "x_search", "from_date": "2026-07-01", "to_date": "2026-08-01"}],
        )
        prompt = payload["payload"]["input"][0]["content"]
        self.assertIn("through 2026-07-31 inclusive", prompt)

    def test_final_calendar_day_is_rejected(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SEARCH_PATH),
                "model release",
                "--search-type",
                "x",
                "--to-date",
                "9999-12-31",
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("exclusive end date", proc.stderr)

    def test_month_boundary_conversion(self) -> None:
        self.assertEqual(search_x.exclusive_to_date("2026-12-31"), "2027-01-01")


class ParseTests(unittest.TestCase):
    def test_extracts_and_canonicalizes_status_urls(self) -> None:
        text = (
            "https://twitter.com/xai/status/123 "
            "https://www.x.com/xai/status/123 "
            "https://x.com/OpenAI/status/456"
        )
        self.assertEqual(
            search_x.extract_x_post_urls(text),
            [
                "https://x.com/xai/status/123",
                "https://x.com/OpenAI/status/456",
            ],
        )

    def test_responses_endpoint_normalization(self) -> None:
        self.assertEqual(
            search_x.responses_endpoint("https://api.x.ai/v1"),
            "https://api.x.ai/v1/responses",
        )
        self.assertEqual(
            search_x.responses_endpoint("https://api.x.ai"),
            "https://api.x.ai/v1/responses",
        )
        self.assertEqual(
            search_x.responses_endpoint("https://api.x.ai/v1/responses"),
            "https://api.x.ai/v1/responses",
        )

    def test_sse_event_joins_data_lines(self) -> None:
        event, data = search_x.parse_sse_event(
            ["event: response.completed", "data: {", 'data: "ok": true', "data: }"]
        )
        self.assertEqual(event, "response.completed")
        self.assertEqual(data, '{\n"ok": true\n}')


class StreamTests(unittest.TestCase):
    def test_completed_event_is_the_response(self) -> None:
        body = "\n".join(
            [
                'data: {"type":"response.output_text.delta","delta":"hello"}',
                "",
                'data: {"type":"response.completed","response":{"id":"resp_1","status":"completed","output_text":"hello"}}',
                "",
            ]
        )
        with mock.patch.object(
            search_x.urllib.request, "urlopen", return_value=FakeHTTPResponse(body)
        ):
            result = search_x.send_stream_request(
                "https://api.x.ai/v1/responses", {}, "test", 1, 0
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["id"], "resp_1")
        self.assertEqual(result["status"], "completed")

    def test_failed_event_is_an_error(self) -> None:
        body = 'data: {"type":"response.failed","response":{"error":{"message":"boom"}}}\n\n'
        with mock.patch.object(
            search_x.urllib.request, "urlopen", return_value=FakeHTTPResponse(body)
        ):
            result = search_x.send_stream_request(
                "https://api.x.ai/v1/responses", {}, "test", 1, 0
            )
        self.assertIsNone(result)

    def test_empty_stream_is_an_error(self) -> None:
        with mock.patch.object(
            search_x.urllib.request, "urlopen", return_value=FakeHTTPResponse("")
        ):
            result = search_x.send_stream_request(
                "https://api.x.ai/v1/responses", {}, "test", 1, 0
            )
        self.assertIsNone(result)

    def test_text_without_completed_event_is_kept(self) -> None:
        body = 'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
        with mock.patch.object(
            search_x.urllib.request, "urlopen", return_value=FakeHTTPResponse(body)
        ):
            result = search_x.send_stream_request(
                "https://api.x.ai/v1/responses", {}, "test", 1, 0
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "incomplete_stream")
        self.assertEqual(result["output_text"], "partial")


class ConfigureTests(unittest.TestCase):
    def test_empty_answers_use_displayed_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CONFIGURE_PATH),
                    "--path",
                    str(path),
                    "--api-key",
                    "local-test",
                ],
                input="\n\n\n\n\n",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("local-test", proc.stdout)
            data = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(data["base_url"], "https://api.x.ai/v1")
        self.assertEqual(data["search_type"], "web")
        self.assertEqual(data["search_scope"], "strict")
        self.assertEqual(data["default_model"], "grok-4.6")
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
