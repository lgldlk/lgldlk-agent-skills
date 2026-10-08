---
name: video-to-text
description: Transcribe local video/audio files or public media download URLs with Tencent Cloud ASR. Use for speech-to-text, timestamped transcripts, subtitles, speaker separation, or reusable MP4/MOV/M4V/WAV/MP3 transcription without hardcoding API keys.
---

# Video To Text

Transcribe local media or a public media URL with `scripts/transcribe_media.py`. Keep credentials outside the skill in a private config file or environment variables.

## Choose The Input Mode

- Local file: use `--input`. Files up to 5 MB are uploaded directly; larger files are transcoded to mono 16 kHz AAC when `ffmpeg` is available. If the result still exceeds 5 MB, use URL mode.
- URL: use `--url` with an HTTP(S) media address that Tencent Cloud can download without cookies or custom request headers. Signed COS URLs are supported while valid.

A video webpage such as a normal `v.qq.com`, YouTube, or Bilibili page is not a media download URL. Do not pass webpage URLs to Tencent ASR. Obtain an authorized downloadable media URL or local file first; do not bypass access controls.

## Tencent Cloud ASR

- Default model: `16k_zh`, suitable for ordinary Mandarin content.
- For noisy, dialect-heavy, or mixed Chinese/English recordings, consider `--engine-model-type 16k_zh_en_2.0`; it uses a different billing tier.
- Default result format: `3`, with punctuation-based segments and timestamps suitable for subtitles.
- URL recordings must be no longer than five hours and must remain downloadable while Tencent processes the task.
- Use `--speaker-diarization` for supported models and `--sentence-max-length 20` to control subtitle line length.
- Use `--hotword-list '产品名|10,人名|8'` for request-scoped vocabulary, or `--hotword-id` for a saved Tencent hotword table.

## Run

```bash
python3 scripts/transcribe_media.py --input ./video.mp4 --output ./transcript.txt
python3 scripts/transcribe_media.py --url 'https://example.com/video.mp4' --output ./subtitle.srt --sentence-max-length 20
python3 scripts/transcribe_media.py --url 'https://example.com/audio.m4a' --output ./transcript.md --speaker-diarization
```

The output format is inferred from `.txt`, `.json`, `.srt`, `.md`, or `.markdown`. Override it with `--output-format`. JSON preserves the full Tencent response, including word timing and speaker data.

## Configuration

Read [configuration](references/config.md) when credentials, defaults, or environment variables need to be set. Copy `config.example.json` to an ignored user or project config; never commit real credentials. Keep reusable Skill code separate from ignored project-local or user-local configuration.

## Companion: social-content-parser

When the source is a Douyin, Xiaohongshu, Bilibili, X/Twitter, or other share page, parse it first with `social-content-parser`. Tencent ASR needs a direct media file URL or a local file, not the share page.

Recommended order:

1. Parse the share URL and inspect `normalized.json`.
2. Transcribe only when the user explicitly asks.
3. Prefer `parse_social.mjs --transcribe` so the parser selects the first normalized video.
4. Or call this script on `normalized.primaryVideo` / a downloaded `media/video.*` file.

Install the two skills as siblings so the parser can discover `scripts/transcribe_media.py` automatically.

## Operational Boundaries

- Do not print media URLs because signed URLs may contain credentials.
- Do not start a paid transcription without the user's media and configured Tencent credentials.
- Polling can take minutes. Results are written only after Tencent reports success.
- If credentials are missing, ask for a private config or environment setup; never place secrets in the skill directory.
