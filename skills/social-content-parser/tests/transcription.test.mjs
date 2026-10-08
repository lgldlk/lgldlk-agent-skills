import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';


const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const PARSER = path.resolve(TEST_DIR, '..', 'scripts', 'parse_social.mjs');
const SIBLING_TRANSCRIBER = path.resolve(
  TEST_DIR,
  '..',
  '..',
  'video-to-text',
  'scripts',
  'transcribe_media.py'
);

test('discovers video-to-text as a sibling skill', async () => {
  await fs.access(SIBLING_TRANSCRIBER);
});

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      ...options,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

async function writeFixture(tempDir) {
  const rawPath = path.join(tempDir, 'raw.json');
  await fs.writeFile(rawPath, JSON.stringify({
    code: 200,
    msg: 'success',
    data: {
      type: 'video',
      title: 'Transcription fixture',
      desc: 'Fixture description',
      author: { name: 'Fixture author', id: 'author-1', avatar: '' },
      url: 'https://media.example.test/video.mp4'
    }
  }));
  return rawPath;
}

test('does not invoke video-to-text unless --transcribe is present', async () => {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'social-parser-test-'));
  try {
    const rawPath = await writeFixture(tempDir);
    const result = await run(process.execPath, [
      PARSER,
      '--from-file', rawPath,
      '--platform', 'xiaohongshu',
      '--out-dir', path.join(tempDir, 'out'),
      '--no-download',
      '--video-to-text-script', path.join(tempDir, 'missing.py')
    ]);

    assert.equal(result.code, 0, result.stderr);
    const summary = JSON.parse(result.stdout);
    assert.equal(summary.transcription.status, 'not-requested');
    const normalized = JSON.parse(await fs.readFile(summary.normalized, 'utf8'));
    assert.equal(normalized.transcription.enabled, false);
  } finally {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
});

test('uses direct URL transcription by default when requested', async () => {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'social-parser-test-'));
  try {
    const rawPath = await writeFixture(tempDir);
    const capturePath = path.join(tempDir, 'captured-args.json');
    const fakeTranscriber = path.join(tempDir, 'fake_transcriber.py');
    await fs.writeFile(fakeTranscriber, [
      'import json, os, pathlib, sys',
      'args = sys.argv[1:]',
      'pathlib.Path(os.environ["CAPTURE_ARGS"]).write_text(json.dumps(args), encoding="utf-8")',
      'output = pathlib.Path(args[args.index("--output") + 1])',
      'output.write_text("fixture transcript\\n", encoding="utf-8")'
    ].join('\n'));

    const result = await run(process.execPath, [
      PARSER,
      '--from-file', rawPath,
      '--platform', 'xiaohongshu',
      '--out-dir', path.join(tempDir, 'out'),
      '--no-download',
      '--transcribe',
      '--transcript-format', 'md',
      '--video-to-text-script', fakeTranscriber
    ], {
      env: { ...process.env, CAPTURE_ARGS: capturePath }
    });

    assert.equal(result.code, 0, result.stderr);
    const summary = JSON.parse(result.stdout);
    assert.equal(summary.transcription.status, 'success');
    assert.equal(summary.transcription.requestedMode, 'direct');
    assert.equal(summary.transcription.usedMode, 'direct');
    assert.equal(await fs.readFile(summary.transcription.output, 'utf8'), 'fixture transcript\n');
    const report = await fs.readFile(summary.report, 'utf8');
    assert.match(report, /## 视频转写/);
    assert.match(report, /- 状态：success/);
    const captured = JSON.parse(await fs.readFile(capturePath, 'utf8'));
    assert.deepEqual(captured.slice(0, 2), [
      '--url',
      'https://media.example.test/video.mp4'
    ]);
  } finally {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
});

test('auto mode falls back to direct URL when local download fails before ASR submission', async () => {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'social-parser-test-'));
  const server = http.createServer((request, response) => {
    response.writeHead(403);
    response.end('forbidden');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const address = server.address();
    const mediaUrl = `http://127.0.0.1:${address.port}/protected.mp4`;
    const rawPath = path.join(tempDir, 'raw.json');
    await fs.writeFile(rawPath, JSON.stringify({
      code: 200,
      msg: 'success',
      data: {
        type: 'video',
        title: 'Fallback fixture',
        author: { name: 'Fixture author' },
        url: mediaUrl
      }
    }));
    const capturePath = path.join(tempDir, 'captured-args.json');
    const fakeTranscriber = path.join(tempDir, 'fake_transcriber.py');
    await fs.writeFile(fakeTranscriber, [
      'import json, os, pathlib, sys',
      'args = sys.argv[1:]',
      'pathlib.Path(os.environ["CAPTURE_ARGS"]).write_text(json.dumps(args), encoding="utf-8")',
      'output = pathlib.Path(args[args.index("--output") + 1])',
      'output.write_text("fallback transcript\\n", encoding="utf-8")'
    ].join('\n'));

    const result = await run(process.execPath, [
      PARSER,
      '--from-file', rawPath,
      '--platform', 'xiaohongshu',
      '--out-dir', path.join(tempDir, 'out'),
      '--no-download',
      '--transcribe',
      '--transcription-mode', 'auto',
      '--video-to-text-script', fakeTranscriber
    ], {
      env: { ...process.env, CAPTURE_ARGS: capturePath }
    });

    assert.equal(result.code, 0, result.stderr);
    const summary = JSON.parse(result.stdout);
    assert.equal(summary.transcription.requestedMode, 'auto');
    assert.equal(summary.transcription.usedMode, 'direct');
    const captured = JSON.parse(await fs.readFile(capturePath, 'utf8'));
    assert.deepEqual(captured.slice(0, 2), ['--url', mediaUrl]);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await fs.rm(tempDir, { recursive: true, force: true });
  }
});
