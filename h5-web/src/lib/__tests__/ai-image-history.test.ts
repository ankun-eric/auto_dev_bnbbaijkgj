/**
 * 单元测试：ai-image-history 工具函数
 *
 * 验证 [BUG_FIX_AI_HOME_IMAGE_HISTORY_RESTORE_V1 2026-06-01] 的核心契约：
 *   - 历史里存成纯文字的「[用户上传的图片 N 张] + URL 列表 + 说明」能还原成 {images, caption}
 *   - 单图 / 多图（最多 5 张）均能还原
 *   - 去掉冗余的「[用户上传的图片 N 张]」占位与裸 URL，保留真实说明文字
 *   - 非图片消息（普通文本）返回 null
 *   - 含图片但无占位文案的普通 AI 正文不被误判为「上传图片消息」
 *
 * 运行：
 *   npx tsx h5-web/src/lib/__tests__/ai-image-history.test.ts
 */

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { extractImagesFromContent, restoreImageMessageFromContent } =
  require('../ai-image-history') as typeof import('../ai-image-history');

let pass = 0;
let fail = 0;
const failures: string[] = [];

function assert(name: string, cond: boolean, detail?: string) {
  if (cond) {
    pass += 1;
  } else {
    fail += 1;
    failures.push(`✗ ${name}${detail ? `\n   ${detail}` : ''}`);
  }
}

function eq(name: string, got: unknown, expected: unknown) {
  const g = JSON.stringify(got);
  const e = JSON.stringify(expected);
  assert(name, g === e, `expected = ${e}\n   got      = ${g}`);
}

// ---- 1. 单图 + 说明（典型报告解读历史记录） ----
{
  const raw =
    '[用户上传的图片 1 张]\n1. https://xiaokang-xxx.oss.com/abc.jpeg\n\n体检报告';
  const r = restoreImageMessageFromContent(raw);
  assert('单图：非 null', r !== null);
  eq('单图：images', r?.images, ['https://xiaokang-xxx.oss.com/abc.jpeg']);
  eq('单图：caption', r?.caption, '体检报告');
}

// ---- 2. 多图（5 张）+ 说明 ----
{
  const urls = [
    'https://x.com/1.jpg',
    'https://x.com/2.jpeg',
    'https://x.com/3.png',
    'https://x.com/4.webp',
    'https://x.com/5.gif',
  ];
  const raw =
    `[用户上传的图片 5 张]\n` +
    urls.map((u, i) => `${i + 1}. ${u}`).join('\n') +
    `\n\n请帮我看看这份报告`;
  const r = restoreImageMessageFromContent(raw);
  assert('多图：非 null', r !== null);
  eq('多图：images 共 5 张', r?.images, urls);
  eq('多图：caption', r?.caption, '请帮我看看这份报告');
}

// ---- 3. 仅图片无说明（caption 应为空字符串，仍是图片消息） ----
{
  const raw = '[用户上传的图片 1 张]\n1. https://x.com/only.jpg';
  const r = restoreImageMessageFromContent(raw);
  assert('无说明：非 null', r !== null);
  eq('无说明：images', r?.images, ['https://x.com/only.jpg']);
  eq('无说明：caption 为空串', r?.caption, '');
}

// ---- 4. 拍照识药历史（带固定话术） ----
{
  const raw =
    '[用户上传的图片 1 张]\n1. https://x.com/drug.jpeg\n\n我上传了一张药品图片，请帮我识别';
  const r = restoreImageMessageFromContent(raw);
  assert('识药：非 null', r !== null);
  eq('识药：images', r?.images, ['https://x.com/drug.jpeg']);
  eq('识药：caption', r?.caption, '我上传了一张药品图片，请帮我识别');
}

// ---- 5. 普通文本消息：返回 null ----
{
  eq('普通文本：null', restoreImageMessageFromContent('你好，帮我看看血压'), null);
  eq('空字符串：null', restoreImageMessageFromContent(''), null);
}

// ---- 6. 含图片 URL 但无「[用户上传的图片」占位（如 AI 正文）：不被误判 ----
{
  const raw = '这是参考图 https://x.com/ref.png 请查看';
  eq('无占位含图：null', restoreImageMessageFromContent(raw), null);
}

// ---- 7. 含「[用户上传的图片」占位但抽不到图片 URL：返回 null ----
{
  const raw = '[用户上传的图片 1 张]\n（图片地址丢失）';
  eq('占位无 URL：null', restoreImageMessageFromContent(raw), null);
}

// ---- 8. extractImagesFromContent 基础能力 ----
{
  const { text, images } = extractImagesFromContent(
    '说明文字 https://x.com/a.jpg 中间 https://x.com/a.jpg 重复',
  );
  eq('extract：URL 去重', images, ['https://x.com/a.jpg']);
  assert('extract：剩余文本不含 URL', !/https?:\/\//.test(text));
}

if (fail === 0) {
  // eslint-disable-next-line no-console
  console.log(`ai-image-history.test.ts: ✓ all ${pass} assertions passed`);
} else {
  // eslint-disable-next-line no-console
  console.error(`ai-image-history.test.ts: ${fail} failed, ${pass} passed`);
  // eslint-disable-next-line no-console
  console.error(failures.join('\n\n'));
  process.exit(1);
}
