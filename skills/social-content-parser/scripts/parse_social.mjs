#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';

const PLATFORMS = {
  xiaohongshu: {
    endpoint: 'https://api.bugpk.com/api/xhsjx',
    fallbackEndpoint: 'https://api.bugpk.com/api/short_videos',
    hosts: ['xiaohongshu.com', 'xhslink.com']
  },
  douyin: {
    endpoint: 'https://api.bugpk.com/api/douyin',
    profileEndpoint: 'https://api.bugpk.com/api/dyzy',
    secondaryEndpoint: 'https://www.devtool.top/api/douyin/parse',
    fallbackEndpoint: 'https://api.bugpk.com/api/short_videos',
    hosts: ['douyin.com', 'iesdouyin.com']
  },
  bilibili: {
    endpoint: 'https://api.bugpk.com/api/bilibili',
    secondaryEndpoint: 'https://uapis.cn/api/v1/social/bilibili/videoinfo',
    fallbackEndpoint: 'https://api.bugpk.com/api/short_videos',
    hosts: ['bilibili.com', 'b23.tv']
  }
};

function parseArgs(argv) {
  const args = { downloadVideo: false, downloadImages: true, retry: 1, kind: 'auto', count: 10 };
  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (item === '--url') args.url = argv[++i];
    else if (item === '--id') args.id = argv[++i];
    else if (item === '--platform') args.platform = argv[++i];
    else if (item === '--kind') args.kind = argv[++i];
    else if (item === '--count') args.count = Number(argv[++i] ?? 10);
    else if (item === '--from-file') args.fromFile = argv[++i];
    else if (item === '--out-dir') args.outDir = argv[++i];
    else if (item === '--no-download') args.noDownload = true;
    else if (item === '--download-video') args.downloadVideo = true;
    else if (item === '--no-images') args.downloadImages = false;
    else if (item === '--retry') args.retry = Number(argv[++i] ?? 1);
    else if (item === '--help' || item === '-h') args.help = true;
  }
  return args;
}

function printHelp() {
  console.log([
    'Usage: node parse_social.mjs --url <share-url> [--out-dir <root-dir>]',
    '       node parse_social.mjs --url <douyin-profile-url> --kind profile [--count 10]',
    '       node parse_social.mjs --platform douyin --kind profile --id <sec_uid> [--count 10]',
    '       node parse_social.mjs --from-file <raw.json> --platform <xiaohongshu|douyin|bilibili>',
    '',
    'Options:',
    '  --kind <auto|post|profile>  Content kind, default auto',
    '  --count <n>        Douyin profile work count, default 10',
    '  --id <id>          Douyin profile ID when no homepage URL is available',
    '  --no-download      Do not download media files',
    '  --download-video   Download primary videos and live-photo videos',
    '  --no-images        Skip image downloads',
    '  --retry <n>        Retry API calls, default 1'
  ].join('\n'));
}

function detectPlatform(sourceUrl) {
  let host = '';
  try {
    host = new URL(sourceUrl).hostname.replace(/^www\./, '');
  } catch {
    throw new Error(`Invalid URL: ${sourceUrl}`);
  }

  for (const [platform, config] of Object.entries(PLATFORMS)) {
    if (config.hosts.some((knownHost) => host === knownHost || host.endsWith(`.${knownHost}`))) {
      return platform;
    }
  }
  throw new Error(`Unsupported platform host: ${host}`);
}

function normalizePlatform(value) {
  if (!value) return '';
  const key = String(value).toLowerCase();
  if (['xhs', 'xiaohongshu', 'rednote'].includes(key)) return 'xiaohongshu';
  if (['dy', 'douyin', 'tiktok-cn'].includes(key)) return 'douyin';
  if (['bili', 'bilibili', 'b23'].includes(key)) return 'bilibili';
  return key;
}

function normalizeShareUrl(sourceUrl) {
  if (!sourceUrl) return '';
  try {
    const u = new URL(sourceUrl);
    return `${u.origin}${u.pathname}`;
  } catch {
    return sourceUrl;
  }
}

function normalizeKind(value) {
  const key = String(value || 'auto').toLowerCase();
  if (['profile', 'homepage', 'home', 'user'].includes(key)) return 'profile';
  if (['post', 'work', 'aweme', 'content', 'video', 'image', 'live'].includes(key)) return 'post';
  return 'auto';
}

function detectDouyinKind(sourceUrl, explicitKind = 'auto') {
  const kind = normalizeKind(explicitKind);
  if (kind !== 'auto') return kind;
  if (!sourceUrl) return 'post';

  try {
    const u = new URL(sourceUrl);
    const pathname = u.pathname.toLowerCase();
    if (pathname.includes('/user/')) return 'profile';
    return 'post';
  } catch {
    return 'post';
  }
}

function inferKind(platform, payload, sourceUrl, explicitKind = 'auto') {
  if (platform !== 'douyin') return 'post';
  const kind = normalizeKind(explicitKind);
  if (kind !== 'auto') return kind;
  if (Array.isArray(payload?.data)) return 'profile';
  return detectDouyinKind(sourceUrl, kind);
}

function apiUrlFor({ platform, sourceUrl, kind = 'auto', count = 10, id = '' }) {
  const resolvedKind = platform === 'douyin' && id && normalizeKind(kind) === 'auto'
    ? 'profile'
    : platform === 'douyin'
      ? detectDouyinKind(sourceUrl, kind)
      : 'post';
  const endpoint = resolvedKind === 'profile'
    ? PLATFORMS[platform]?.profileEndpoint
    : PLATFORMS[platform]?.endpoint;
  if (!endpoint) throw new Error(`Unsupported platform: ${platform}`);
  const u = new URL(endpoint);
  if (platform === 'douyin' && resolvedKind === 'profile') {
    if (id) u.searchParams.set('id', id);
    else if (sourceUrl) u.searchParams.set('url', sourceUrl);
    else throw new Error('Douyin profile parsing requires --url or --id');
    u.searchParams.set('count', String(Number.isFinite(count) && count > 0 ? count : 10));
  } else {
    u.searchParams.set('url', sourceUrl);
  }
  return u.toString();
}

function apiSecondaryUrlFor(platform, sourceUrl, canonicalUrl) {
  const endpoint = PLATFORMS[platform]?.secondaryEndpoint;
  if (!endpoint) return '';
  const u = new URL(endpoint);

  if (platform === 'douyin') {
    u.searchParams.set('url', sourceUrl || canonicalUrl || '');
  } else if (platform === 'bilibili') {
    const target = resolveBilibiliTarget(sourceUrl || canonicalUrl || '');
    if (target.aid) u.searchParams.set('aid', String(target.aid));
    else if (target.bvid) u.searchParams.set('bvid', target.bvid);
    else return '';
  }

  return u.toString();
}

function apiFallbackUrlFor(sourceUrl) {
  const u = new URL(PLATFORMS.xiaohongshu.fallbackEndpoint);
  u.searchParams.set('url', sourceUrl);
  return u.toString();
}

function resolveBilibiliTarget(sourceUrl) {
  try {
    const u = new URL(sourceUrl);
    const bvid = u.pathname.match(/\/video\/([^/?]+)/)?.[1];
    const aid = u.pathname.match(/\/video\/av(\d+)/i)?.[1];
    return { bvid, aid };
  } catch {
    return { bvid: '', aid: '' };
  }
}

function formatDuration(seconds) {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total < 0) return '';
  const s = Math.floor(total % 60);
  const m = Math.floor((total / 60) % 60);
  const h = Math.floor(total / 3600);
  const parts = h > 0 ? [h, m, s] : [m, s];
  return parts.map((value) => String(value).padStart(2, '0')).join(':');
}

async function fetchJson(url) {
  const res = await fetch(url, {
    headers: {
      accept: 'application/json, text/plain, */*',
      'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
      referer: 'https://api.bugpk.com/',
      origin: 'https://api.bugpk.com'
    }
  });
  const text = await res.text();
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.body = text;
    throw err;
  }
  return JSON.parse(text);
}

async function fetchWithRetry(apiUrl, retries) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await fetchJson(apiUrl);
    } catch (err) {
      lastErr = err;
      if (attempt < retries) continue;
      throw err;
    }
  }
  throw lastErr;
}

async function readJsonFile(filePath) {
  const raw = await fs.readFile(filePath, 'utf8');
  return JSON.parse(raw);
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === 'string' && value) return [value];
  return [];
}

function pickText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function sanitizeName(name) {
  return String(name || 'unknown').replace(/[\\/:*?"<>|\n\r]+/g, '_').slice(0, 120);
}

function getShanghaiDateStamp(date = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(date);
}

function extractSourceId(platform, sourceUrl, data) {
  if (platform === 'douyin') return data?.aweme_id || data?.id || '';
  if (platform === 'bilibili') {
    try {
      const u = new URL(sourceUrl);
      const bvid = u.pathname.match(/\/video\/([^/?]+)/)?.[1];
      return bvid || data?.bvid || data?.aid || '';
    } catch {
      return data?.bvid || data?.aid || '';
    }
  }
  try {
    const u = new URL(sourceUrl);
    return u.pathname.match(/\/explore\/([^/]+)/)?.[1] || '';
  } catch {
    return '';
  }
}

function normalizeAuthor(platform, data) {
  if (platform === 'bilibili') {
    return {
      name: data?.user?.name ?? '',
      id: data?.user?.id ?? '',
      avatar: data?.user?.avatar ?? ''
    };
  }
  const author = data?.author || {};
  return {
    name: author.name ?? '',
    id: author.id ?? author.uid ?? '',
    avatar: author.avatar ?? ''
  };
}

function normalizeLivePhoto(value) {
  return Array.isArray(value)
    ? value.filter(Boolean).map((item) => ({
        image: item?.image ?? '',
        video: item?.video ?? ''
      }))
    : [];
}

function normalizeParts(platform, data) {
  if (platform !== 'bilibili') return [];
  return Array.isArray(data?.videos)
    ? data.videos.map((item) => ({
        index: item.index ?? null,
        title: item.title ?? '',
        duration: item.duration ?? null,
        durationFormat: item.durationFormat ?? '',
        url: item.url ?? ''
      }))
    : [];
}

function normalizeDouyinProfileItem(item) {
  return {
    index: item?.index ?? null,
    sourceId: item?.aweme_id ?? '',
    type: item?.type ?? null,
    title: item?.title ?? item?.desc ?? '',
    desc: item?.desc ?? '',
    createdAt: item?.create_time ?? '',
    shareUrl: item?.share_url ?? '',
    author: {
      name: item?.author ?? '',
      id: item?.author_uid ?? '',
      secUid: item?.author_sec_uid ?? ''
    },
    cover: item?.cover ?? '',
    primaryVideo: item?.url ?? '',
    images: asArray(item?.images),
    music: {
      title: item?.music_title ?? '',
      author: item?.music_author ?? '',
      url: item?.music_url ?? '',
      cover: ''
    },
    statistics: item?.statistics ?? {},
    hashtags: asArray(item?.hashtags)
  };
}

function normalizeDouyinProfile(payload, sourceUrl) {
  const items = Array.isArray(payload?.data) ? payload.data.map(normalizeDouyinProfileItem) : [];
  const first = items[0] || {};
  const author = first.author || {};
  const profileId = author.secUid || author.id || '';

  return {
    platform: 'douyin',
    kind: 'profile',
    sourceUrl,
    code: payload?.code ?? null,
    msg: payload?.msg ?? '',
    type: 'profile',
    title: author.name ? `Douyin profile: ${author.name}` : 'Douyin profile',
    desc: '',
    author: {
      name: author.name ?? '',
      id: author.id ?? '',
      secUid: author.secUid ?? '',
      avatar: ''
    },
    cover: first.cover ?? '',
    primaryVideo: '',
    videoBackups: [],
    images: [],
    livePhoto: [],
    music: {},
    statistics: {},
    parts: [],
    totalVideos: items.length,
    items,
    pagination: payload?.pagination ?? {},
    sourceId: profileId || first.sourceId || '',
    supportedFields: [
      'items',
      'pagination',
      'author',
      'cover',
      'primaryVideo',
      'images',
      'music',
      'statistics'
    ]
  };
}

function normalizeDouyinSecondary(payload, sourceUrl, canonicalUrl) {
  const data = payload?.data || {};
  const authorAvatar = data.avatar ?? data.music?.avatar ?? '';
  return {
    platform: 'douyin',
    kind: 'secondary',
    sourceUrl,
    canonicalUrl,
    code: payload?.code ?? null,
    msg: payload?.msg ?? '',
    type: 'video',
    title: data.title ?? '',
    desc: '',
    author: {
      name: data.author ?? '',
      id: data.uid ?? '',
      avatar: authorAvatar
    },
    cover: data.cover ?? '',
    primaryVideo: data.video?.url ?? data.url ?? '',
    videoBackups: asArray(data.video?.url_with_water_mask),
    images: [],
    livePhoto: [],
    music: {
      title: '',
      author: data.music?.author ?? '',
      url: '',
      cover: data.music?.avatar ?? ''
    },
    statistics: {
      like: data.like ?? null,
      time: data.time ?? null
    },
    parts: [],
    totalVideos: 0,
    items: [],
    pagination: {},
    sourceId: extractSourceId('douyin', sourceUrl, data),
    fallbackUsed: true,
    secondaryUsed: true,
    supportedFields: [
      'title',
      'author',
      'cover',
      'primaryVideo',
      'videoBackups',
      'music',
      'statistics'
    ]
  };
}

function normalizeBilibiliSecondary(payload, sourceUrl, canonicalUrl) {
  const pages = Array.isArray(payload?.pages) ? payload.pages : [];
  const primaryPage = pages[0] || {};
  const owner = payload?.owner || {};
  const stat = payload?.stat || {};
  return {
    platform: 'bilibili',
    kind: 'secondary',
    sourceUrl,
    canonicalUrl,
    code: payload?.code ?? 200,
    msg: payload?.message ?? payload?.msg ?? 'success',
    type: 'video',
    title: payload?.title ?? '',
    desc: payload?.desc ?? '',
    author: {
      name: owner.name ?? '',
      id: owner.mid ?? '',
      avatar: owner.face ?? ''
    },
    cover: payload?.pic ?? '',
    primaryVideo: primaryPage.weblink ?? '',
    videoBackups: [],
    images: [],
    livePhoto: [],
    music: {},
    statistics: stat,
    parts: pages.map((item) => ({
      index: item.page ?? null,
      title: item.part ?? '',
      duration: item.duration ?? null,
      durationFormat: formatDuration(item.duration),
      url: item.weblink ?? ''
    })),
    totalVideos: payload?.videos ?? pages.length,
    items: [],
    pagination: {},
    sourceId: payload?.bvid ?? payload?.aid ?? extractSourceId('bilibili', sourceUrl, payload),
    fallbackUsed: true,
    secondaryUsed: true,
    supportedFields: [
      'title',
      'desc',
      'author',
      'cover',
      'primaryVideo',
      'parts',
      'statistics'
    ]
  };
}

function normalizeFallbackPayload(platform, payload, sourceUrl, canonicalUrl) {
  const data = payload?.data || {};
  const authorName = data.author ?? data.user?.name ?? '';
  const authorId = data.uid ?? data.user?.id ?? '';
  const authorAvatar = data.avatar ?? data.user?.avatar ?? '';
  const images = asArray(data.images);
  const primaryVideo = data.url ?? data.video_url ?? '';
  const type = data.type ?? (images.length ? 'image' : primaryVideo ? 'video' : null);

  return {
    platform,
    kind: 'fallback',
    sourceUrl,
    canonicalUrl,
    code: payload?.code ?? null,
    msg: payload?.msg ?? '',
    type,
    title: data.title ?? '',
    desc: data.desc ?? '',
    author: {
      name: authorName,
      id: authorId,
      avatar: authorAvatar
    },
    cover: data.cover ?? '',
    primaryVideo,
    videoBackups: asArray(data.video_backup),
    images,
    livePhoto: normalizeLivePhoto(data.live_photo),
    music: data.music ?? {
      title: '',
      author: '',
      url: '',
      cover: ''
    },
    statistics: {
      like: data.like ?? null,
      time: data.time ?? null
    },
    parts: [],
    totalVideos: 0,
    items: [],
    pagination: {},
    sourceId: extractSourceId(platform, sourceUrl, data) || authorId || '',
    fallbackUsed: true,
    secondaryUsed: false,
    supportedFields: [
      'title',
      'desc',
      'author',
      'cover',
      'primaryVideo',
      'videoBackups',
      'images',
      'livePhoto',
      'music',
      'statistics'
    ]
  };
}

function isUsablePrimaryPayload(platform, payload, kind) {
  if (!payload || typeof payload !== 'object') return false;
  const code = Number(payload.code);
  if (Number.isFinite(code) && code !== 200) return false;
  if (platform === 'douyin' && kind === 'profile') return Array.isArray(payload.data) && payload.data.length > 0;
  if (platform === 'bilibili') {
    return Boolean(payload?.data?.title || payload?.data?.url || (Array.isArray(payload?.data?.videos) && payload.data.videos.length));
  }
  return Boolean(payload?.data && (Array.isArray(payload.data) ? payload.data.length > 0 : Object.keys(payload.data).length > 0));
}

function normalizePayload(platform, payload, sourceUrl, kind = 'auto') {
  const resolvedKind = inferKind(platform, payload, sourceUrl, kind);
  if (platform === 'douyin' && resolvedKind === 'profile') {
    return normalizeDouyinProfile(payload, sourceUrl);
  }

  const data = payload?.data || {};
  const author = normalizeAuthor(platform, data);
  const images = Array.isArray(data.images) ? data.images.filter(Boolean) : [];
  const livePhoto = normalizeLivePhoto(data.live_photo);
  const videoBackups = [
    ...asArray(data.video_backup),
    ...normalizeParts(platform, data).map((item) => item.url).filter(Boolean)
  ];

  return {
    platform,
    kind: 'post',
    sourceUrl,
    canonicalUrl: normalizeShareUrl(sourceUrl),
    code: payload?.code ?? null,
    msg: payload?.msg ?? '',
    type: data.type ?? (platform === 'bilibili' ? 'video' : null),
    title: data.title ?? '',
    desc: data.desc ?? data.description ?? '',
    author,
    cover: data.cover ?? data.imgurl ?? '',
    primaryVideo: data.url ?? data.video_url ?? '',
    videoBackups,
    images,
    livePhoto,
    music: data.music ?? {
      title: data.music_title ?? '',
      author: data.music_author ?? '',
      url: data.music_url ?? '',
      cover: ''
    },
    statistics: data.statistics ?? {},
    parts: normalizeParts(platform, data),
    totalVideos: data.totalVideos ?? normalizeParts(platform, data).length,
    items: [],
    pagination: {},
    sourceId: extractSourceId(platform, sourceUrl, data),
    fallbackUsed: false,
    supportedFields: [
      'title',
      'desc',
      'author',
      'cover',
      'primaryVideo',
      'videoBackups',
      'images',
      'livePhoto',
      'music',
      'statistics',
      'parts'
    ]
  };
}

function buildRunFolderName(normalized) {
  const platform = sanitizeName(normalized.platform);
  const title = sanitizeName(normalized.title || 'social-post');
  const date = getShanghaiDateStamp();
  const id = sanitizeName(normalized.sourceId || 'unknown');
  return `${platform}-${title}-${date}-${id}`;
}

async function fetchPrimaryOrFallback({ platform, sourceUrl, canonicalUrl, kind, count, id, retries }) {
  const primarySourceUrl = platform === 'xiaohongshu' ? sourceUrl : canonicalUrl;
  const primaryUrl = apiUrlFor({ platform, sourceUrl: primarySourceUrl, kind, count, id });
  try {
    const payload = await fetchWithRetry(primaryUrl, retries);
    if (isUsablePrimaryPayload(platform, payload, kind)) return { payload, mode: 'primary' };
  } catch {
    // continue
  }

  const secondaryUrl = apiSecondaryUrlFor(platform, sourceUrl, canonicalUrl);
  if (secondaryUrl) {
    try {
      const payload = await fetchWithRetry(secondaryUrl, retries);
      if (platform === 'douyin' && payload?.code === 200 && payload?.data) return { payload, mode: 'secondary' };
      if (platform === 'bilibili' && (payload?.title || payload?.pages || payload?.owner)) return { payload, mode: 'secondary' };
    } catch {
      // continue
    }
  }

  const fallbackSourceUrl = platform === 'xiaohongshu' ? sourceUrl || canonicalUrl : sourceUrl || canonicalUrl;
  const fallbackUrl = apiFallbackUrlFor(fallbackSourceUrl);
  const payload = await fetchWithRetry(fallbackUrl, retries);
  return { payload, mode: 'fallback' };
}

function resolveDownloadRoot(cwd) {
  return path.join(cwd, 'social-notes');
}

async function writeFileSafe(filePath, content) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content);
}

function extensionFromUrl(url, fallback) {
  try {
    const ext = path.extname(new URL(url).pathname);
    return ext || fallback;
  } catch {
    return fallback;
  }
}

async function downloadToFile(url, filePath) {
  const res = await fetch(url, {
    headers: {
      accept: '*/*',
      'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
    }
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status} ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, buf);
}

async function downloadMedia(normalized, mediaDir, args) {
  const downloads = [];
  const add = async (url, name, fallbackExt) => {
    if (!url) return;
    const file = path.join(mediaDir, `${name}${extensionFromUrl(url, fallbackExt)}`);
    await downloadToFile(url, file);
    downloads.push(file);
  };

  await add(normalized.author.avatar, 'author-avatar', '.jpg');
  await add(normalized.cover, 'cover', '.jpg');

  if (args.downloadImages) {
    for (let i = 0; i < normalized.images.length; i += 1) {
      await add(normalized.images[i], `image-${String(i + 1).padStart(2, '0')}`, '.jpg');
    }
    for (let i = 0; i < normalized.livePhoto.length; i += 1) {
      await add(normalized.livePhoto[i].image, `live-photo-${String(i + 1).padStart(2, '0')}`, '.jpg');
    }
  }

  if (args.downloadVideo) {
    await add(normalized.primaryVideo, 'video', '.mp4');
    for (let i = 0; i < normalized.livePhoto.length; i += 1) {
      await add(normalized.livePhoto[i].video, `live-video-${String(i + 1).padStart(2, '0')}`, '.mp4');
    }
  }

  return downloads;
}

function buildReport(normalized, outDir, downloads) {
  const partsText = normalized.parts.length
    ? normalized.parts.map((item) => `- P${item.index ?? ''} ${item.title || '未命名'}：${item.durationFormat || item.duration || '时长待确认'}`).join('\n')
    : '- 无';
  const itemsText = normalized.items?.length
    ? normalized.items.map((item) => `- ${item.index ?? ''}. ${item.desc || item.title || '未命名'}（${item.type || '类型待确认'}，${item.createdAt || '时间待确认'}）`).join('\n')
    : '- 无';

  return [
    `# ${normalized.title || 'Social Content'}`,
    '',
    '## 结论',
    `- 平台：${normalized.platform}`,
    `- 标题：${normalized.title || '待确认'}`,
    `- 作者：${normalized.author.name || '待确认'}`,
    `- 内容形态：${normalized.kind || 'post'}`,
    `- 类型：${normalized.type || '待确认'}`,
    `- 兜底解析：${normalized.fallbackUsed ? '是' : '否'}`,
    `- 解析模式：${normalized.parseMode || 'primary'}`,
    `- 下载目录：${outDir}`,
    '',
    '## 关键信息',
    `- 原始链接：${normalized.canonicalUrl || '待确认'}`,
    `- 规范链接：${normalized.canonicalUrl || '待确认'}`,
    `- 响应码：${normalized.code ?? '待确认'}`,
    `- 解析结果：${normalized.msg || '待确认'}`,
    `- 正文：${normalized.desc || '待确认'}`,
    `- 图片数量：${normalized.images.length}`,
    `- 实况数量：${normalized.livePhoto.length}`,
    `- 分 P / 合集数量：${normalized.parts.length || normalized.totalVideos || 0}`,
    `- 主页作品数量：${normalized.items?.length || 0}`,
    '',
    '## 作者',
    `- 名称：${normalized.author.name || '待确认'}`,
    `- ID：${normalized.author.id || '待确认'}`,
    `- 头像：${normalized.author.avatar || '无'}`,
    '',
    '## 资源',
    `- 封面：${normalized.cover || '无'}`,
    `- 主视频：${normalized.primaryVideo || '无'}`,
    `- 备用视频：${normalized.videoBackups.length ? normalized.videoBackups.join('\n  - ') : '无'}`,
    `- 图片：${normalized.images.length ? normalized.images.join('\n  - ') : '无'}`,
    '',
    '## 分集 / 合集',
    partsText,
    '',
    '## 主页作品',
    itemsText,
    '',
    '## 音乐',
    `- 标题：${pickText(normalized.music?.title) || '无'}`,
    `- 作者：${pickText(normalized.music?.author) || '无'}`,
    `- 链接：${pickText(normalized.music?.url) || '无'}`,
    '',
    '## 统计',
    pickText(normalized.statistics) || '无',
    '',
    '## 本地下载',
    downloads.length ? downloads.map((item) => `- ${item}`).join('\n') : '- 未下载或无可下载资源',
    '',
    '## 过程/方法',
    '1. 自动识别链接平台。',
    '2. 先清理分享链接中的跟踪参数，只保留内容路径。',
    '3. 对抖音链接先判断主页或作品，再调用对应 BugPk API。',
    '4. 主接口失手时，自动切到聚合解析兜底。',
    '5. 保存原始响应。',
    '6. 归一化核心字段。',
    '7. 生成报告并按需下载媒体。',
    '',
    '## 易错点',
    '- 不要把不同平台的字段名当成一致。',
    '- 分享链接常带 tracking 参数，先清理再解析更稳。',
    '- 抖音主页和抖音作品返回结构不同，主页是作品列表，作品页才有 `type=video/image/live`。',
    '- 主接口失败时再用聚合兜底，不要反过来抢占主路径。',
    '- 直链可能会过期，长期归档应下载媒体文件。',
    '- 视频默认不下载，需要显式传入 `--download-video`。',
    '',
    '## 变更记录',
    `- ${new Date().toISOString().slice(0, 10)}：生成本地报告与媒体下载。`,
    '',
    '## 下一步',
    '- [ ] 如需更多字段，再扩展归一化规则。'
  ].join('\n');
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    printHelp();
    process.exit(0);
  }

  const cwd = process.cwd();
  const rootDir = path.resolve(args.outDir || resolveDownloadRoot(cwd));
  let payload;
  let sourceUrl = '';
  let canonicalUrl = '';
  let platform = normalizePlatform(args.platform);
  let kind = normalizeKind(args.kind);
  let parseMode = 'primary';

  if (args.fromFile) {
    payload = await readJsonFile(args.fromFile);
    sourceUrl = args.url || payload?.sourceUrl || payload?.requestUrl || '';
    canonicalUrl = normalizeShareUrl(sourceUrl);
    platform = platform || normalizePlatform(payload?.platform);
    if (!platform) throw new Error('Missing --platform when using --from-file');
    kind = inferKind(platform, payload, sourceUrl, kind);
  } else {
    if (!args.url && !args.id) throw new Error('Missing --url, --id, or --from-file');
    sourceUrl = args.url || '';
    canonicalUrl = normalizeShareUrl(sourceUrl);
    platform = platform || (sourceUrl ? detectPlatform(sourceUrl) : '');
    if (!platform) throw new Error('Missing --platform when using --id without --url');
    kind = platform === 'douyin' && args.id && kind === 'auto' ? 'profile' : platform === 'douyin' ? detectDouyinKind(sourceUrl, kind) : 'post';
    const result = await fetchPrimaryOrFallback({
      platform,
      sourceUrl,
      canonicalUrl,
      kind,
      count: args.count,
      id: args.id,
      retries: Math.max(0, args.retry)
    });
    payload = result.payload;
    parseMode = result.mode;
  }

  let normalized;
  if (platform === 'douyin' && parseMode === 'secondary') {
    normalized = normalizeDouyinSecondary(payload, sourceUrl, canonicalUrl);
  } else if (platform === 'bilibili' && parseMode === 'secondary') {
    normalized = normalizeBilibiliSecondary(payload, sourceUrl, canonicalUrl);
  } else if (parseMode === 'fallback') {
    normalized = normalizeFallbackPayload(platform, payload, sourceUrl, canonicalUrl);
  } else {
    normalized = normalizePayload(platform, payload, sourceUrl, kind);
  }
  normalized.parseMode = parseMode;
  const outDir = path.join(rootDir, buildRunFolderName(normalized));
  const mediaDir = path.join(outDir, 'media');
  await fs.mkdir(outDir, { recursive: true });
  await writeFileSafe(path.join(outDir, 'raw.json'), JSON.stringify(payload, null, 2));
  await writeFileSafe(path.join(outDir, 'normalized.json'), JSON.stringify(normalized, null, 2));

  const downloads = args.noDownload ? [] : await downloadMedia(normalized, mediaDir, args);
  const report = buildReport(normalized, outDir, downloads);
  await writeFileSafe(path.join(outDir, 'report.md'), report);

  console.log(JSON.stringify({
    platform: normalized.platform,
    outDir,
    report: path.join(outDir, 'report.md'),
    normalized: path.join(outDir, 'normalized.json'),
    raw: path.join(outDir, 'raw.json'),
    mediaDir,
    title: normalized.title,
    author: normalized.author.name,
    kind: normalized.kind,
    type: normalized.type,
    items: normalized.items?.length || 0,
    images: normalized.images.length,
    livePhoto: normalized.livePhoto.length,
    parts: normalized.parts.length,
    downloads: downloads.length
  }, null, 2));
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
