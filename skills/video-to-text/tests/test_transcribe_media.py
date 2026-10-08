from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "transcribe_media.py"
SPEC = importlib.util.spec_from_file_location("transcribe_media", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
transcribe_media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transcribe_media)


SAMPLE_RESULT = {
    "TaskId": 42,
    "Status": 2,
    "StatusStr": "success",
    "Result": "你好。\n这是测试。",
    "AudioDuration": 3.5,
    "ResultDetail": [
        {
            "FinalSentence": "你好。",
            "StartMs": 0,
            "EndMs": 1200,
            "SpeakerId": 0,
            "Words": [],
        },
        {
            "FinalSentence": "这是测试。",
            "StartMs": 1250,
            "EndMs": 3500,
            "SpeakerId": 1,
            "Words": [],
        },
    ],
}


class CredentialTests(unittest.TestCase):
    def test_resolves_relative_credential_from_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            credential_path = project_dir / "keys" / "tencent.json"
            credential_path.parent.mkdir()
            credential_path.write_text(
                json.dumps({"SecretId": "test-id", "SecretKey": "test-key"}),
                encoding="utf-8",
            )

            credentials = transcribe_media.load_tencent_credentials(
                {"tencent": {"credentialFile": "keys/tencent.json"}},
                None,
                project_dir / ".video-to-text.json",
            )

        self.assertEqual(credentials, ("test-id", "test-key"))

    def test_project_config_precedes_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            project_config = project_dir / transcribe_media.PROJECT_CONFIG_NAME
            project_config.write_text("{}", encoding="utf-8")
            with mock.patch.dict("os.environ", {}, clear=True):
                resolved = transcribe_media.resolve_config_path(None, project_dir)

        self.assertEqual(resolved, project_config)

    def test_loads_configured_credential_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credential_path = Path(tmpdir) / "tencent.json"
            credential_path.write_text(
                json.dumps({"SecretId": "test-id", "SecretKey": "test-key"}),
                encoding="utf-8",
            )

            credentials = transcribe_media.load_tencent_credentials(
                {"tencent": {"credentialFile": str(credential_path)}},
                None,
            )

        self.assertEqual(credentials, ("test-id", "test-key"))

    def test_explicit_credential_file_overrides_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            configured_path = Path(tmpdir) / "configured.json"
            explicit_path = Path(tmpdir) / "explicit.json"
            configured_path.write_text(
                json.dumps({"SecretId": "configured-id", "SecretKey": "configured-key"}),
                encoding="utf-8",
            )
            explicit_path.write_text(
                json.dumps({"SecretId": "explicit-id", "SecretKey": "explicit-key"}),
                encoding="utf-8",
            )

            credentials = transcribe_media.load_tencent_credentials(
                {"tencent": {"credentialFile": str(configured_path)}},
                explicit_path,
            )

        self.assertEqual(credentials, ("explicit-id", "explicit-key"))


class CreateTaskBodyTests(unittest.TestCase):
    def test_url_source_uses_source_type_zero_without_inline_data(self) -> None:
        body = transcribe_media.build_create_task_body(
            media_bytes=None,
            media_url="https://media.example.com/video.mp4?signature=secret",
            engine_model_type="16k_zh",
            res_text_format=3,
            channel_num=1,
            speaker_diarization=1,
            sentence_max_length=20,
            hotword_list="腾讯云|10,ASR|8",
        )

        self.assertEqual(body["SourceType"], 0)
        self.assertEqual(body["Url"], "https://media.example.com/video.mp4?signature=secret")
        self.assertNotIn("Data", body)
        self.assertNotIn("DataLen", body)
        self.assertEqual(body["SpeakerDiarization"], 1)
        self.assertEqual(body["SentenceMaxLength"], 20)

    def test_inline_source_rejects_more_than_five_megabytes(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceeds Tencent"):
            transcribe_media.build_create_task_body(
                media_bytes=b"x" * (transcribe_media.MAX_INLINE_BYTES + 1),
                media_url=None,
                engine_model_type="16k_zh",
                res_text_format=3,
                channel_num=1,
            )

    def test_create_task_submits_url_payload(self) -> None:
        body = transcribe_media.build_create_task_body(
            media_bytes=None,
            media_url="https://media.example.com/audio.m4a",
            engine_model_type="16k_zh",
            res_text_format=3,
            channel_num=1,
        )
        with mock.patch.object(
            transcribe_media,
            "call_asr",
            return_value={"Data": {"TaskId": 123}},
        ) as call:
            task_id = transcribe_media.create_task("id", "key", "ap-shanghai", body)

        self.assertEqual(task_id, 123)
        call.assert_called_once_with("id", "key", "CreateRecTask", body, "ap-shanghai")


class OutputTests(unittest.TestCase):
    def test_srt_contains_timestamps_and_speakers(self) -> None:
        rendered = transcribe_media.render_srt(SAMPLE_RESULT)
        self.assertIn("00:00:00,000 --> 00:00:01,200", rendered)
        self.assertIn("Speaker 0: 你好。", rendered)
        self.assertIn("Speaker 1: 这是测试。", rendered)

    def test_markdown_contains_timestamps_and_speakers(self) -> None:
        rendered = transcribe_media.render_markdown(SAMPLE_RESULT)
        self.assertIn("[00:00:01.250 - 00:00:03.500]", rendered)
        self.assertIn("**Speaker 1:**", rendered)

    def test_json_preserves_result_details(self) -> None:
        rendered = transcribe_media.render_output(SAMPLE_RESULT, "json")
        self.assertIn('"ResultDetail"', rendered)
        self.assertIn('"AudioDuration": 3.5', rendered)

    def test_output_format_is_inferred_from_extension(self) -> None:
        self.assertEqual(transcribe_media.infer_output_format(Path("result.srt"), "auto"), "srt")
        self.assertEqual(transcribe_media.infer_output_format(Path("result.md"), "auto"), "md")
        self.assertEqual(transcribe_media.infer_output_format(Path("result.txt"), "auto"), "txt")


if __name__ == "__main__":
    unittest.main()
