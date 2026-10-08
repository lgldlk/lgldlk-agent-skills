#!/usr/bin/env python3
"""Transcribe a local media file or public media URL with Tencent Cloud ASR."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse


HOST = "asr.tencentcloudapi.com"
ENDPOINT = f"https://{HOST}/"
SERVICE = "asr"
VERSION = "2019-06-14"
DEFAULT_REGION = "ap-shanghai"
DEFAULT_ENGINE_MODEL = "16k_zh"
DEFAULT_RES_TEXT_FORMAT = 3
DEFAULT_CHANNEL_NUM = 1
MAX_INLINE_BYTES = 5 * 1024 * 1024
PROJECT_CONFIG_NAME = ".video-to-text.json"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "video-to-text" / "config.json"
OUTPUT_FORMATS = ("auto", "txt", "json", "srt", "md")


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"config must contain a JSON object: {path}")
    return payload


def resolve_config_path(path: Path | None, cwd: Path | None = None) -> Path | None:
    if path is not None:
        resolved = path.expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"config file not found: {resolved}")
        return resolved

    env_path = os.getenv("VIDEO_TO_TEXT_CONFIG")
    if env_path:
        resolved = Path(env_path).expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"VIDEO_TO_TEXT_CONFIG file not found: {resolved}")
        return resolved

    project_config = (cwd or Path.cwd()) / PROJECT_CONFIG_NAME
    if project_config.exists():
        return project_config

    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    return None


def load_config(path: Path | None, cwd: Path | None = None) -> dict[str, Any]:
    resolved = resolve_config_path(path, cwd)
    return read_json(resolved) if resolved is not None else {}


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def normalize_tencent_config(config: dict[str, Any]) -> dict[str, Any]:
    tencent = config.get("tencent")
    if tencent is None:
        return {}
    if not isinstance(tencent, dict):
        raise ValueError("config field 'tencent' must be a JSON object")
    return tencent


def load_tencent_credentials(
    config: dict[str, Any],
    cred_file: Path | None,
    config_path: Path | None = None,
) -> tuple[str, str]:
    tencent = normalize_tencent_config(config)
    configured_cred_file = tencent.get("credentialFile") or tencent.get("credential_file")
    if cred_file is None and configured_cred_file:
        cred_file = Path(str(configured_cred_file)).expanduser()
        if not cred_file.is_absolute() and config_path is not None:
            cred_file = config_path.parent / cred_file

    if cred_file is not None:
        if not cred_file.exists():
            raise FileNotFoundError(f"credential file not found: {cred_file}")
        payload = read_json(cred_file)
        secret_id = payload.get("SecretId") or payload.get("secretId") or payload.get("secret_id")
        secret_key = payload.get("SecretKey") or payload.get("secretKey") or payload.get("secret_key")
        if secret_id and secret_key:
            return str(secret_id), str(secret_key)
        raise ValueError(f"credential file {cred_file} must contain SecretId and SecretKey")

    secret_id = (
        tencent.get("secretId")
        or tencent.get("secret_id")
        or first_env("TENCENT_SECRET_ID", "TENCENTCLOUD_SECRET_ID")
    )
    secret_key = (
        tencent.get("secretKey")
        or tencent.get("secret_key")
        or first_env("TENCENT_SECRET_KEY", "TENCENTCLOUD_SECRET_KEY")
    )
    if not secret_id or not secret_key:
        raise ValueError(
            "missing Tencent credentials; provide --tencent-cred-file, a config file, or env vars"
        )
    return str(secret_id), str(secret_key)


def tc3_sign(secret_id: str, secret_key: str, payload: bytes, timestamp: int) -> str:
    canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{HOST}\n"
    signed_headers = "content-type;host"
    canonical_request = "\n".join(
        ["POST", "/", "", canonical_headers, signed_headers, sha256_hex(payload)]
    )
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    credential_scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = "\n".join(
        [
            "TC3-HMAC-SHA256",
            str(timestamp),
            credential_scope,
            sha256_hex(canonical_request.encode("utf-8")),
        ]
    )
    secret_date = hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = hmac.new(secret_date, SERVICE.encode("utf-8"), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def call_asr(
    secret_id: str,
    secret_key: str,
    action: str,
    body: dict[str, Any],
    region: str,
) -> dict[str, Any]:
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = int(time.time())
    headers = {
        "Authorization": tc3_sign(secret_id, secret_key, payload, timestamp),
        "Content-Type": "application/json; charset=utf-8",
        "Host": HOST,
        "X-TC-Action": action,
        "X-TC-Version": VERSION,
        "X-TC-Region": region,
        "X-TC-Timestamp": str(timestamp),
    }
    req = urlrequest.Request(ENDPOINT, data=payload, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urlerror.HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(f"HTTP {exc.code}: {raw.decode('utf-8', 'replace')}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"network error: {exc}") from exc

    data = json.loads(raw.decode("utf-8"))
    response = data.get("Response")
    if not isinstance(response, dict):
        raise RuntimeError(f"unexpected response: {data}")
    if "Error" in response:
        err = response["Error"]
        raise RuntimeError(f"{err.get('Code')}: {err.get('Message')}")
    return response


def transcode_with_ffmpeg(input_path: Path) -> bytes | None:
    if shutil.which("ffmpeg") is None:
        return None

    with tempfile.TemporaryDirectory(prefix="video-to-text-") as tmpdir:
        out_path = Path(tmpdir) / f"{input_path.stem}.m4a"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(out_path),
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0 or not out_path.exists():
            eprint(proc.stderr.strip())
            return None
        return out_path.read_bytes()


def prepare_media_bytes(
    input_path: Path,
    max_inline_bytes: int,
    force_transcode: bool,
) -> tuple[bytes, str]:
    if max_inline_bytes <= 0 or max_inline_bytes > MAX_INLINE_BYTES:
        raise ValueError(f"--max-inline-bytes must be between 1 and {MAX_INLINE_BYTES}")

    raw = input_path.read_bytes()
    if not force_transcode and len(raw) <= max_inline_bytes:
        return raw, "original"

    transcoded = transcode_with_ffmpeg(input_path)
    if transcoded is not None and len(transcoded) <= max_inline_bytes:
        return transcoded, "ffmpeg-aac-m4a"

    smallest_size = min(len(raw), len(transcoded) if transcoded is not None else len(raw))
    raise ValueError(
        f"media remains {smallest_size} bytes after preparation; Tencent inline upload is limited "
        f"to {max_inline_bytes} bytes. Upload it to a public/COS URL and use --url instead"
    )


def normalize_media_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--url must be a public HTTP(S) media download URL")
    return value


def optional_int(value: Any, name: str, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc


def build_create_task_body(
    *,
    media_bytes: bytes | None,
    media_url: str | None,
    engine_model_type: str,
    res_text_format: int,
    channel_num: int,
    speaker_diarization: int = 0,
    speaker_number: int = 0,
    sentence_max_length: int = 0,
    hotword_id: str | None = None,
    hotword_list: str | None = None,
) -> dict[str, Any]:
    if (media_bytes is None) == (media_url is None):
        raise ValueError("provide exactly one source: media bytes or media URL")
    if res_text_format not in range(0, 6):
        raise ValueError("ResTextFormat must be between 0 and 5")
    if channel_num not in {1, 2}:
        raise ValueError("ChannelNum must be 1 or 2")
    if speaker_diarization not in {0, 1}:
        raise ValueError("SpeakerDiarization must be 0 or 1")
    if speaker_number not in range(0, 11):
        raise ValueError("SpeakerNumber must be between 0 and 10")
    if sentence_max_length != 0 and sentence_max_length not in range(6, 41):
        raise ValueError("SentenceMaxLength must be 0 or between 6 and 40")
    if sentence_max_length and res_text_format != 3:
        raise ValueError("SentenceMaxLength requires ResTextFormat=3")

    body: dict[str, Any] = {
        "ChannelNum": channel_num,
        "EngineModelType": engine_model_type,
        "ResTextFormat": res_text_format,
        "SpeakerDiarization": speaker_diarization,
        "SpeakerNumber": speaker_number,
        "SentenceMaxLength": sentence_max_length,
    }
    if media_url is not None:
        body.update({"SourceType": 0, "Url": normalize_media_url(media_url)})
    else:
        assert media_bytes is not None
        if len(media_bytes) > MAX_INLINE_BYTES:
            raise ValueError(f"inline media exceeds Tencent's {MAX_INLINE_BYTES}-byte limit")
        body.update(
            {
                "SourceType": 1,
                "Data": base64.b64encode(media_bytes).decode("ascii"),
                "DataLen": len(media_bytes),
            }
        )
    if hotword_id:
        body["HotwordId"] = hotword_id
    if hotword_list:
        body["HotwordList"] = hotword_list
    return body


def create_task(
    secret_id: str,
    secret_key: str,
    region: str,
    body: dict[str, Any],
) -> int:
    response = call_asr(secret_id, secret_key, "CreateRecTask", body, region)
    task = response.get("Data") or {}
    task_id = task.get("TaskId")
    if task_id is None:
        raise RuntimeError(f"CreateRecTask returned no TaskId: {response}")
    return int(task_id)


def describe_task(secret_id: str, secret_key: str, region: str, task_id: int) -> dict[str, Any]:
    response = call_asr(secret_id, secret_key, "DescribeTaskStatus", {"TaskId": task_id}, region)
    return response.get("Data") or {}


def poll_task(
    secret_id: str,
    secret_key: str,
    region: str,
    task_id: int,
    poll_interval: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = None
    while True:
        data = describe_task(secret_id, secret_key, region, task_id)
        status = data.get("Status")
        status_str = data.get("StatusStr")
        if status != last_status:
            eprint(f"status: {status} ({status_str})")
            last_status = status
        if status == 2:
            return data
        if status == 3:
            raise RuntimeError(data.get("ErrorMsg") or "task failed")
        if time.time() >= deadline:
            raise TimeoutError(f"timed out waiting for task {task_id}")
        time.sleep(poll_interval)


def sentence_text(item: dict[str, Any]) -> str:
    value = item.get("WrittenText") or item.get("FinalSentence") or item.get("SliceSentence") or ""
    return str(value).strip()


def result_details(data: dict[str, Any]) -> list[dict[str, Any]]:
    details = data.get("ResultDetail") or []
    if not isinstance(details, list):
        return []
    return [item for item in details if isinstance(item, dict)]


def pick_transcript(data: dict[str, Any]) -> str:
    sentences = [sentence_text(item) for item in result_details(data)]
    sentences = [sentence for sentence in sentences if sentence]
    if sentences:
        return "\n".join(sentences)
    return str(data.get("Result") or "").strip()


def format_timestamp(milliseconds: Any, decimal_separator: str) -> str:
    try:
        total_ms = max(0, int(milliseconds))
    except (TypeError, ValueError):
        total_ms = 0
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{decimal_separator}{millis:03d}"


def render_srt(data: dict[str, Any]) -> str:
    blocks: list[str] = []
    for item in result_details(data):
        text = sentence_text(item)
        if not text or item.get("StartMs") is None or item.get("EndMs") is None:
            continue
        start = format_timestamp(item["StartMs"], ",")
        end = format_timestamp(item["EndMs"], ",")
        speaker_id = item.get("SpeakerId")
        if speaker_id is not None:
            text = f"Speaker {speaker_id}: {text}"
        blocks.append(f"{len(blocks) + 1}\n{start} --> {end}\n{text}")
    if not blocks:
        raise ValueError("Tencent returned no sentence timestamps; use ResTextFormat=3 for SRT output")
    return "\n\n".join(blocks) + "\n"


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in result_details(data):
        text = sentence_text(item)
        if not text:
            continue
        start = format_timestamp(item.get("StartMs"), ".")
        end = format_timestamp(item.get("EndMs"), ".")
        speaker_id = item.get("SpeakerId")
        speaker = f" **Speaker {speaker_id}:**" if speaker_id is not None else ""
        lines.append(f"- `[{start} - {end}]`{speaker} {text}")
    if lines:
        return "# Transcript\n\n" + "\n".join(lines) + "\n"
    transcript = pick_transcript(data)
    return f"# Transcript\n\n{transcript}\n"


def infer_output_format(output: Path | None, requested: str) -> str:
    if requested != "auto":
        return requested
    if output is None:
        return "txt"
    extension_map = {".json": "json", ".srt": "srt", ".md": "md", ".markdown": "md"}
    return extension_map.get(output.suffix.lower(), "txt")


def render_output(data: dict[str, Any], output_format: str) -> str:
    if output_format == "txt":
        transcript = pick_transcript(data)
        return transcript + ("\n" if transcript else "")
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if output_format == "srt":
        return render_srt(data)
    if output_format == "md":
        return render_markdown(data)
    raise ValueError(f"unsupported output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe a local media file or public media URL with Tencent Cloud ASR"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="local video/audio file")
    source.add_argument(
        "--url",
        help="public HTTP(S) media download URL; ordinary video webpage URLs are not supported",
    )
    parser.add_argument("--config", type=Path, help="path to a JSON config file")
    parser.add_argument("--provider", default=None, help="ASR provider; current built-in value: tencent")
    parser.add_argument("--output", type=Path, help="output file; extension selects format when auto")
    parser.add_argument("--output-format", choices=OUTPUT_FORMATS, default="auto")
    parser.add_argument(
        "--tencent-cred-file",
        type=Path,
        help="JSON file with SecretId and SecretKey; overrides config and env vars",
    )
    parser.add_argument("--region", default=None, help="Tencent Cloud region override")
    parser.add_argument("--engine-model-type", default=None, help="Tencent ASR model override")
    parser.add_argument("--res-text-format", type=int, default=None, help="Tencent result format (0-5)")
    parser.add_argument("--channel-num", type=int, default=None, help="Tencent ASR channel count")
    parser.add_argument(
        "--speaker-diarization",
        action="store_true",
        default=None,
        help="separate speakers for supported models",
    )
    parser.add_argument("--speaker-number", type=int, default=None, help="speaker count (0-10; 0=auto)")
    parser.add_argument(
        "--sentence-max-length",
        type=int,
        default=None,
        help="subtitle sentence length: 0 or 6-40; requires ResTextFormat=3",
    )
    parser.add_argument("--hotword-id", default=None, help="Tencent persistent hotword table ID")
    parser.add_argument(
        "--hotword-list",
        default=None,
        help='temporary hotwords, for example "腾讯云|10,语音识别|5"',
    )
    parser.add_argument(
        "--max-inline-bytes",
        type=int,
        default=MAX_INLINE_BYTES,
        help=f"local upload/transcode threshold; cannot exceed {MAX_INLINE_BYTES}",
    )
    parser.add_argument("--force-transcode", action="store_true", help="transcode local media first")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="poll interval in seconds")
    parser.add_argument("--timeout", type=float, default=10800.0, help="overall timeout in seconds")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.input is not None and not args.input.is_file():
        raise FileNotFoundError(f"input file not found: {args.input}")
    if args.poll_interval <= 0 or args.timeout <= 0:
        raise ValueError("--poll-interval and --timeout must be positive")

    config_path = resolve_config_path(args.config)
    config = read_json(config_path) if config_path is not None else {}
    provider = (
        args.provider or os.getenv("VIDEO_TO_TEXT_PROVIDER") or config.get("provider") or "tencent"
    ).lower()
    if provider != "tencent":
        raise NotImplementedError(f"provider not supported yet: {provider}")

    tencent = normalize_tencent_config(config)
    secret_id, secret_key = load_tencent_credentials(
        config,
        args.tencent_cred_file,
        config_path,
    )
    region = str(args.region or tencent.get("region") or DEFAULT_REGION)
    engine_model_type = str(
        args.engine_model_type or tencent.get("engineModelType") or DEFAULT_ENGINE_MODEL
    )
    res_text_format = optional_int(
        args.res_text_format if args.res_text_format is not None else tencent.get("resTextFormat"),
        "resTextFormat",
        DEFAULT_RES_TEXT_FORMAT,
    )
    channel_num = optional_int(
        args.channel_num if args.channel_num is not None else tencent.get("channelNum"),
        "channelNum",
        DEFAULT_CHANNEL_NUM,
    )
    speaker_diarization = optional_int(
        1 if args.speaker_diarization else tencent.get("speakerDiarization"),
        "speakerDiarization",
        0,
    )
    speaker_number = optional_int(
        args.speaker_number if args.speaker_number is not None else tencent.get("speakerNumber"),
        "speakerNumber",
        0,
    )
    sentence_max_length = optional_int(
        args.sentence_max_length
        if args.sentence_max_length is not None
        else tencent.get("sentenceMaxLength"),
        "sentenceMaxLength",
        0,
    )
    hotword_id = args.hotword_id or tencent.get("hotwordId")
    hotword_list = args.hotword_list or tencent.get("hotwordList")

    media_bytes: bytes | None = None
    media_url: str | None = None
    if args.url is not None:
        media_url = normalize_media_url(args.url)
        media_mode = "public-url"
    else:
        assert args.input is not None
        media_bytes, media_mode = prepare_media_bytes(
            args.input, args.max_inline_bytes, args.force_transcode
        )
    eprint(f"using provider={provider} source={media_mode} model={engine_model_type}")

    body = build_create_task_body(
        media_bytes=media_bytes,
        media_url=media_url,
        engine_model_type=engine_model_type,
        res_text_format=res_text_format,
        channel_num=channel_num,
        speaker_diarization=speaker_diarization,
        speaker_number=speaker_number,
        sentence_max_length=sentence_max_length,
        hotword_id=str(hotword_id) if hotword_id else None,
        hotword_list=str(hotword_list) if hotword_list else None,
    )
    task_id = create_task(secret_id, secret_key, region, body)
    eprint(f"task id: {task_id}")
    data = poll_task(
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
        task_id=task_id,
        poll_interval=args.poll_interval,
        timeout_seconds=args.timeout,
    )

    output_format = infer_output_format(args.output, args.output_format)
    rendered = render_output(data, output_format)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        eprint(f"saved {output_format}: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        eprint(f"error: {exc}")
        raise SystemExit(1)
