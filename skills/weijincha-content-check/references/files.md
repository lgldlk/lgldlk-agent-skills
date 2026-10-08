# File and URL Review

## Supported Inputs

Use `--file` for local text-like files and `--url` for public HTTP(S) text files. The loader accepts UTF-8, UTF-8 with BOM, and GB18030 text. It rejects content containing null bytes or content that cannot be decoded safely.

Typical supported formats include TXT, Markdown, CSV, JSON, JSONL, YAML, XML, HTML, logs, source code, and other plain-text formats. PDF, DOCX, images, archives, audio, and video require extraction by an appropriate format-specific tool before this skill can audit the resulting text.

## Commands

```bash
python scripts/check_text.py --scope xianyu --file ./product.md --pretty
```

```bash
python scripts/check_text.py --scope xianyu --url 'https://example.com/product.txt' --pretty
```

```bash
python scripts/check_text.py \
  --scope xianyu \
  --scope ad \
  --file ./title.txt \
  --file ./description.md \
  --pretty
```

## Limits

- Maximum sources per run: 20.
- Default maximum bytes per local or remote file: 1 MiB.
- Default maximum decoded characters per source: 100,000.
- Default provider chunk size: 3,500 characters.
- Override limits with `--max-file-bytes`, `--max-chars`, and `--chunk-size` only when the data is trusted and request volume is acceptable.

Each chunk reports character offsets and line numbers. Multiple scopes multiply provider calls by `source_count × chunk_count × scope_count`.

## Remote URL Safety

- Allow only `http` and `https` URLs.
- Reject embedded usernames or passwords.
- Resolve and reject loopback, private, link-local, multicast, reserved, and unspecified network addresses.
- Apply the same checks to redirects.
- Limit downloaded bytes before decoding.

These controls reduce accidental SSRF exposure but do not turn the command into a hardened public URL-fetching service. Keep application-facing adapters authenticated and rate-limited.
