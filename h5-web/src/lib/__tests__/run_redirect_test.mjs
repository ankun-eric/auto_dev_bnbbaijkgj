// 简易 node 运行测试（内联 resolveLoginRedirectPath 源逻辑 + 用例断言）
// 用途：在没有 jest 时快速验证 401 拦截器跳转路径解析逻辑是否正确

function resolveLoginRedirectPath(pathname, base) {
  const p = pathname || '';
  const normalized = p.replace(/\/+$/, '');
  const prefix = (base || '').replace(/\/+$/, '');
  const appPath = prefix && normalized.startsWith(prefix)
    ? normalized.substring(prefix.length)
    : normalized;

  if (appPath.startsWith('/merchant/m/') || appPath === '/merchant/m') {
    const target = `${prefix}/merchant/m/login`;
    return {
      path: target,
      tokenKey: 'merchant_token',
      alreadyOnLogin: appPath === '/merchant/m/login' || appPath.startsWith('/merchant/m/login/'),
    };
  }
  if (appPath.startsWith('/merchant/') || appPath === '/merchant') {
    const target = `${prefix}/merchant/login`;
    return {
      path: target,
      tokenKey: 'merchant_token',
      alreadyOnLogin: appPath === '/merchant/login' || appPath.startsWith('/merchant/login/'),
    };
  }
  const target = `${prefix}/login`;
  return {
    path: target,
    tokenKey: 'token',
    alreadyOnLogin: appPath === '/login' || appPath.startsWith('/login/'),
  };
}

const cases = [
  {
    name: '商家端手机版工作台 401 -> /merchant/m/login',
    pathname: '/autodev/xxx/merchant/m/dashboard/',
    basePath: '/autodev/xxx',
    expect: { path: '/autodev/xxx/merchant/m/login', tokenKey: 'merchant_token', alreadyOnLogin: false },
  },
  {
    name: '商家端手机版登录页 401 -> 不跳',
    pathname: '/autodev/xxx/merchant/m/login/',
    basePath: '/autodev/xxx',
    expect: { path: '/autodev/xxx/merchant/m/login', tokenKey: 'merchant_token', alreadyOnLogin: true },
  },
  {
    name: '商家 PC 版订单页 401 -> /merchant/login',
    pathname: '/autodev/xxx/merchant/orders/',
    basePath: '/autodev/xxx',
    expect: { path: '/autodev/xxx/merchant/login', tokenKey: 'merchant_token', alreadyOnLogin: false },
  },
  {
    name: '商家 PC 版登录页 401 -> 不跳',
    pathname: '/autodev/xxx/merchant/login/',
    basePath: '/autodev/xxx',
    expect: { path: '/autodev/xxx/merchant/login', tokenKey: 'merchant_token', alreadyOnLogin: true },
  },
  {
    name: 'C 端用户 H5 页面 401 -> /login',
    pathname: '/autodev/xxx/chat/123/',
    basePath: '/autodev/xxx',
    expect: { path: '/autodev/xxx/login', tokenKey: 'token', alreadyOnLogin: false },
  },
  {
    name: 'C 端登录页 401 -> 不跳',
    pathname: '/autodev/xxx/login/',
    basePath: '/autodev/xxx',
    expect: { path: '/autodev/xxx/login', tokenKey: 'token', alreadyOnLogin: true },
  },
  {
    name: '无 basePath：商家手机 dashboard',
    pathname: '/merchant/m/dashboard/',
    basePath: '',
    expect: { path: '/merchant/m/login', tokenKey: 'merchant_token', alreadyOnLogin: false },
  },
  {
    name: '无 basePath：C 端 /home',
    pathname: '/home/',
    basePath: '',
    expect: { path: '/login', tokenKey: 'token', alreadyOnLogin: false },
  },
];

let fail = 0;
for (const c of cases) {
  const r = resolveLoginRedirectPath(c.pathname, c.basePath);
  const ok = r.path === c.expect.path && r.tokenKey === c.expect.tokenKey && r.alreadyOnLogin === c.expect.alreadyOnLogin;
  if (!ok) { fail++; console.log('[FAIL]', c.name, 'got=', r, 'expect=', c.expect); }
  else console.log('[OK]  ', c.name);
}
if (fail) { console.log(`\n${fail}/${cases.length} FAILED`); process.exit(1); }
console.log(`\nALL ${cases.length} CASES PASSED`);
