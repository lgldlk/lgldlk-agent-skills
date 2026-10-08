# Configuration

Copy `config.example.json` to an ignored user or project config. Do not put real credentials in the skill directory.

The script resolves configuration in this order:

1. `--config /path/to/config.json`
2. `VIDEO_TO_TEXT_CONFIG=/path/to/config.json`
3. `.video-to-text.json` in the current working directory
4. `~/.config/video-to-text/config.json`
5. Credential environment variables, when the selected JSON does not contain credentials

## Tencent config

```json
{
  "provider": "tencent",
  "tencent": {
    "credentialFile": "keys/tencent.json",
    "region": "ap-shanghai",
    "engineModelType": "16k_zh",
    "resTextFormat": 3,
    "channelNum": 1,
    "speakerDiarization": 0,
    "speakerNumber": 0,
    "sentenceMaxLength": 0,
    "hotwordId": "",
    "hotwordList": ""
  }
}
```

Prefer `credentialFile` so the main config contains no secret values. A relative path is resolved from the config file's directory, which keeps project configuration portable. The referenced JSON must contain `SecretId` and `SecretKey`. Direct `secretId` and `secretKey` fields remain supported when needed.

`16k_zh` is the general Mandarin default. Use `16k_zh_en_2.0` when its higher accuracy and separate billing tier are appropriate. `sentenceMaxLength` must be `0` or `6` through `40`, and a nonzero value requires `resTextFormat: 3`.

## Environment variables

- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENTCLOUD_SECRET_ID`
- `TENCENTCLOUD_SECRET_KEY`
- `VIDEO_TO_TEXT_PROVIDER`

## Credential File

`--tencent-cred-file` accepts either Tencent's key names or lowercase variants:

```json
{
  "SecretId": "YOUR_SECRET_ID",
  "SecretKey": "YOUR_SECRET_KEY"
}
```

## Security

- Keep secrets out of the skill directory.
- Keep project-specific paths out of the Skill. Put them in an ignored `.video-to-text.json`, a user config, or environment variables.
- Restrict the credential file to the current user, for example mode `600` on macOS/Linux.
- A signed media URL may contain temporary credentials. Pass it directly with `--url`; do not add it to config or logs.
- For a personal machine, use `~/.config/video-to-text/config.json` and restrict its file permissions.
