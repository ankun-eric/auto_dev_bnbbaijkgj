/**
 * 单元测试：401 拦截器跳转路径解析函数
 * Bug 修复验证：商家端 H5 登录后被踢到用户端登录页
 *
 * 本测试为纯函数测试，不依赖 DOM/axios，运行方式（如需执行）：
 *   npx jest h5-web/src/lib/__tests__/api.redirect.test.ts
 * 或采用 ts-node 简单执行。
 */

import { resolveLoginRedirectPath } from '../api';

type Case = {
  name: string;
  pathname: string;
  basePath: string;
  expectPath: string;
  expectTokenKey: 'token' | 'merchant_token';
  expectAlreadyOnLogin: boolean;
};

const cases: Case[] = [
  {
    name: '商家端手机版工作台触发 401 -> 跳 /merchant/m/login',
    pathname: '/autodev/xxx/merchant/m/dashboard/',
    basePath: '/autodev/xxx',
    expectPath: '/autodev/xxx/merchant/m/login',
    expectTokenKey: 'merchant_token',
    expectAlreadyOnLogin: false,
  },
  {
    name: '商家端手机版登录页自身 401 -> 不跳转',
    pathname: '/autodev/xxx/merchant/m/login/',
    basePath: '/autodev/xxx',
    expectPath: '/autodev/xxx/merchant/m/login',
    expectTokenKey: 'merchant_token',
    expectAlreadyOnLogin: true,
  },
  {
    name: '商家端 PC 版订单页触发 401 -> 跳 /merchant/login',
    pathname: '/autodev/xxx/merchant/orders/',
    basePath: '/autodev/xxx',
    expectPath: '/autodev/xxx/merchant/login',
    expectTokenKey: 'merchant_token',
    expectAlreadyOnLogin: false,
  },
  {
    name: '商家端 PC 版登录页自身 401 -> 不跳转',
    pathname: '/autodev/xxx/merchant/login/',
    basePath: '/autodev/xxx',
    expectPath: '/autodev/xxx/merchant/login',
    expectTokenKey: 'merchant_token',
    expectAlreadyOnLogin: true,
  },
  {
    name: 'C 端用户 H5 触发 401 -> 跳 /login',
    pathname: '/autodev/xxx/chat/123/',
    basePath: '/autodev/xxx',
    expectPath: '/autodev/xxx/login',
    expectTokenKey: 'token',
    expectAlreadyOnLogin: false,
  },
  {
    name: 'C 端登录页自身 401 -> 不跳转',
    pathname: '/autodev/xxx/login/',
    basePath: '/autodev/xxx',
    expectPath: '/autodev/xxx/login',
    expectTokenKey: 'token',
    expectAlreadyOnLogin: true,
  },
  {
    name: '无 basePath 场景：商家手机版 dashboard',
    pathname: '/merchant/m/dashboard/',
    basePath: '',
    expectPath: '/merchant/m/login',
    expectTokenKey: 'merchant_token',
    expectAlreadyOnLogin: false,
  },
  {
    name: '无 basePath 场景：C 端首页',
    pathname: '/home/',
    basePath: '',
    expectPath: '/login',
    expectTokenKey: 'token',
    expectAlreadyOnLogin: false,
  },
];

describe('resolveLoginRedirectPath', () => {
  cases.forEach((c) => {
    it(c.name, () => {
      const r = resolveLoginRedirectPath(c.pathname, c.basePath);
      expect(r.path).toBe(c.expectPath);
      expect(r.tokenKey).toBe(c.expectTokenKey);
      expect(r.alreadyOnLogin).toBe(c.expectAlreadyOnLogin);
    });
  });
});

// 如果没有 jest runner，提供简易 node 运行入口
if (typeof (global as any).describe === 'undefined') {
  let failed = 0;
  for (const c of cases) {
    const r = resolveLoginRedirectPath(c.pathname, c.basePath);
    const ok =
      r.path === c.expectPath &&
      r.tokenKey === c.expectTokenKey &&
      r.alreadyOnLogin === c.expectAlreadyOnLogin;
    if (!ok) {
      failed++;
      console.error('[FAIL]', c.name, 'got=', r, 'expected=', c);
    } else {
      console.log('[OK]  ', c.name);
    }
  }
  if (failed > 0) {
    console.error(`\n${failed} / ${cases.length} 用例失败`);
    process.exit(1);
  } else {
    console.log(`\n全部 ${cases.length} 用例通过`);
  }
}
