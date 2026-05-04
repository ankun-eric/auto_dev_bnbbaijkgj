/**
 * 单元测试：resolveAssetUrl 工具函数
 *
 * 验证 [2026-05-05 全端图片附件 BasePath 治理] 的核心契约：
 *   - 完整 URL / blob / data URI 原样返回
 *   - 裸 /uploads/... 自动补 basePath
 *   - 已带 basePath 的不重复拼接（幂等）
 *   - 空值安全
 *   - basePath 为空时透传（不破坏根路径部署）
 *
 * 通过环境变量 NEXT_PUBLIC_BASE_PATH 控制。
 *
 * 运行：
 *   NEXT_PUBLIC_BASE_PATH=/autodev/test-uuid npx tsx h5-web/src/lib/__tests__/asset-url.test.ts
 *   或集成到任意 jest/vitest pipeline 中。
 */

const ORIG = process.env.NEXT_PUBLIC_BASE_PATH;
process.env.NEXT_PUBLIC_BASE_PATH = '/autodev/test-uuid';

// 必须在设置环境变量之后再 import（basePath.ts 在模块加载时读取）
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { resolveAssetUrl, resolveAssetUrls } = require('../asset-url') as typeof import('../asset-url');

type Case = { name: string; input: string | null | undefined; expected: string };

const cases: Case[] = [
  // 空值
  { name: '空字符串',           input: '',         expected: '' },
  { name: 'null',                input: null,       expected: '' },
  { name: 'undefined',           input: undefined,  expected: '' },
  { name: '纯空白',              input: '   ',      expected: '' },

  // 完整 URL（不应被改动）
  { name: 'https URL',           input: 'https://cdn.x.com/a.jpg',          expected: 'https://cdn.x.com/a.jpg' },
  { name: 'http URL',            input: 'http://cdn.x.com/a.jpg',           expected: 'http://cdn.x.com/a.jpg' },
  { name: 'blob URL',            input: 'blob:http://localhost/abc',         expected: 'blob:http://localhost/abc' },
  { name: 'data URI',            input: 'data:image/png;base64,iVBORw0',     expected: 'data:image/png;base64,iVBORw0' },
  { name: '协议相对 //',          input: '//cdn.x.com/a.jpg',                 expected: '//cdn.x.com/a.jpg' },

  // 裸路径：拼 basePath
  { name: '裸 /uploads',         input: '/uploads/order_attachments/35.jpg',
    expected: '/autodev/test-uuid/uploads/order_attachments/35.jpg' },
  { name: '裸 /static',          input: '/static/foo.png',
    expected: '/autodev/test-uuid/static/foo.png' },
  { name: '裸根路径',            input: '/',
    expected: '/autodev/test-uuid/' },

  // 幂等：已带 basePath
  { name: '已带 basePath 前缀',   input: '/autodev/test-uuid/uploads/x.jpg',
    expected: '/autodev/test-uuid/uploads/x.jpg' },
  { name: 'basePath 等于本身',    input: '/autodev/test-uuid',
    expected: '/autodev/test-uuid' },

  // 相对路径
  { name: '相对路径',            input: 'images/a.png',
    expected: '/autodev/test-uuid/images/a.png' },
];

let pass = 0;
let fail = 0;
const failures: string[] = [];
for (const c of cases) {
  const got = resolveAssetUrl(c.input);
  if (got === c.expected) {
    pass += 1;
  } else {
    fail += 1;
    failures.push(`✗ ${c.name}\n   input    = ${JSON.stringify(c.input)}\n   expected = ${JSON.stringify(c.expected)}\n   got      = ${JSON.stringify(got)}`);
  }
}

// 批量
const arr = resolveAssetUrls(['/uploads/a.jpg', null, 'https://x.com/b.png', '']);
const expected = ['/autodev/test-uuid/uploads/a.jpg', 'https://x.com/b.png'];
if (JSON.stringify(arr) === JSON.stringify(expected)) {
  pass += 1;
} else {
  fail += 1;
  failures.push(`✗ resolveAssetUrls 批量\n   got      = ${JSON.stringify(arr)}\n   expected = ${JSON.stringify(expected)}`);
}

if (fail === 0) {
  // eslint-disable-next-line no-console
  console.log(`asset-url.test.ts: ✓ all ${pass} assertions passed`);
} else {
  // eslint-disable-next-line no-console
  console.error(`asset-url.test.ts: ${fail} failed, ${pass} passed`);
  // eslint-disable-next-line no-console
  console.error(failures.join('\n\n'));
  process.exit(1);
}

// 还原
if (ORIG === undefined) delete process.env.NEXT_PUBLIC_BASE_PATH;
else process.env.NEXT_PUBLIC_BASE_PATH = ORIG;
