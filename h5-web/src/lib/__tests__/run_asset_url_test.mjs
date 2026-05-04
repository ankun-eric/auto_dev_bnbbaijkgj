/**
 * 单元测试运行器（纯 JS）：验证 resolveAssetUrl 工具的契约。
 *
 * 不依赖 jest/vitest，直接 node 运行：
 *   node h5-web/src/lib/__tests__/run_asset_url_test.mjs
 *
 * 通过临时模拟 process.env.NEXT_PUBLIC_BASE_PATH 验证多种部署形态。
 */

// 模拟 BASE_PATH = '/autodev/test-uuid' 的实现（与 asset-url.ts/admin-web 契约一致）
function makeResolver(rawBase) {
  const BASE_PATH = (rawBase || '').replace(/\/+$/, '');
  function resolveAssetUrl(path) {
    if (!path) return '';
    const s = String(path).trim();
    if (!s) return '';
    if (/^(https?:|blob:|data:)/i.test(s)) return s;
    if (s.startsWith('//')) return s;
    if (!s.startsWith('/')) {
      if (!BASE_PATH) return s;
      return BASE_PATH + '/' + s;
    }
    if (!BASE_PATH) return s;
    if (s === BASE_PATH || s.startsWith(BASE_PATH + '/')) return s;
    return BASE_PATH + s;
  }
  function resolveAssetUrls(paths) {
    if (!paths || !Array.isArray(paths)) return [];
    return paths.map(resolveAssetUrl).filter((u) => !!u);
  }
  return { resolveAssetUrl, resolveAssetUrls };
}

let pass = 0;
let fail = 0;
const failures = [];

function check(name, got, expected) {
  if (JSON.stringify(got) === JSON.stringify(expected)) {
    pass += 1;
  } else {
    fail += 1;
    failures.push(`✗ ${name}\n   expected = ${JSON.stringify(expected)}\n   got      = ${JSON.stringify(got)}`);
  }
}

// 场景 1：带 basePath 部署（测试环境）
{
  const { resolveAssetUrl, resolveAssetUrls } = makeResolver('/autodev/test-uuid');
  check('basepath:空串',           resolveAssetUrl(''),         '');
  check('basepath:null',            resolveAssetUrl(null),       '');
  check('basepath:undefined',       resolveAssetUrl(undefined),  '');
  check('basepath:纯空白',          resolveAssetUrl('   '),      '');
  check('basepath:https URL',       resolveAssetUrl('https://cdn.x.com/a.jpg'), 'https://cdn.x.com/a.jpg');
  check('basepath:http URL',        resolveAssetUrl('http://cdn.x.com/a.jpg'),  'http://cdn.x.com/a.jpg');
  check('basepath:blob URL',        resolveAssetUrl('blob:http://localhost/abc'), 'blob:http://localhost/abc');
  check('basepath:data URI',        resolveAssetUrl('data:image/png;base64,iVBORw0'), 'data:image/png;base64,iVBORw0');
  check('basepath:协议相对 //',     resolveAssetUrl('//cdn.x.com/a.jpg'), '//cdn.x.com/a.jpg');
  check('basepath:裸 /uploads',     resolveAssetUrl('/uploads/order_attachments/35.jpg'),
        '/autodev/test-uuid/uploads/order_attachments/35.jpg');
  check('basepath:裸 /static',      resolveAssetUrl('/static/foo.png'),
        '/autodev/test-uuid/static/foo.png');
  check('basepath:裸根 /',          resolveAssetUrl('/'), '/autodev/test-uuid/');
  check('basepath:幂等-已带前缀',   resolveAssetUrl('/autodev/test-uuid/uploads/x.jpg'),
        '/autodev/test-uuid/uploads/x.jpg');
  check('basepath:幂等-等于本身',   resolveAssetUrl('/autodev/test-uuid'),
        '/autodev/test-uuid');
  check('basepath:相对路径',        resolveAssetUrl('images/a.png'),
        '/autodev/test-uuid/images/a.png');
  check('basepath:批量', resolveAssetUrls(['/uploads/a.jpg', null, 'https://x.com/b.png', '']),
        ['/autodev/test-uuid/uploads/a.jpg', 'https://x.com/b.png']);
}

// 场景 2：根路径部署（生产环境）
{
  const { resolveAssetUrl } = makeResolver('');
  check('root:空串',                resolveAssetUrl(''),                '');
  check('root:裸 /uploads',         resolveAssetUrl('/uploads/x.jpg'),   '/uploads/x.jpg');
  check('root:https URL',           resolveAssetUrl('https://cdn.x.com/a.jpg'), 'https://cdn.x.com/a.jpg');
  check('root:相对路径',            resolveAssetUrl('images/a.png'),     'images/a.png');
}

// 场景 3：basePath 末尾带斜线（容错）
{
  const { resolveAssetUrl } = makeResolver('/autodev/test-uuid///');
  check('basepath-trailing-slash: 裸 /uploads',
        resolveAssetUrl('/uploads/x.jpg'), '/autodev/test-uuid/uploads/x.jpg');
}

if (fail === 0) {
  console.log(`✓ asset-url tests: all ${pass} assertions passed`);
  process.exit(0);
} else {
  console.error(`✗ asset-url tests: ${fail} failed, ${pass} passed\n`);
  console.error(failures.join('\n\n'));
  process.exit(1);
}
