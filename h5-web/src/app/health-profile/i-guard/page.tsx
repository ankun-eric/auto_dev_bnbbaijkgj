'use client';

/**
 * [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 路口A1] 旧 IGuard 页面整体下线
 *
 * 根据 PRD v1.0 落地核查报告 路口A1（整体下线）方案：
 *  - 旧 i-guard 页面已废弃，所有入口收口到 /health-profile/archive-list
 *  - 老 URL 自动跳转到新档案列表页
 *  - 透传 invite_history / member_id 等 query 参数（archive-list 自身已处理邀请记录）
 *
 * 这样做的收益：
 *  1. 删除「+ 发起邀请」顶部大按钮（PRD §4.1 验收 8.1#9）
 *  2. 删除卡片上无视 S2 才显示规则的「发起邀请」按钮（PRD §4.1 验收 8.1#10）
 *  3. 新页面已内置：7 态状态机、按钮矩阵、统一删除接口、reason_code 错误提示
 *  4. 用户在任意旧入口（书签、外链、二维码）都会自动进入新页面
 */

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

// 由于 Next.js 14 在 client 组件使用 useSearchParams() 时要求外层包裹 <Suspense>，
// 这里把 redirect 逻辑抽离到内部组件，外层用 Suspense 包裹避免 prerender 报错。
function IGuardRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const qs = searchParams?.toString() || '';
    const target = qs
      ? `/health-profile/archive-list?${qs}`
      : '/health-profile/archive-list';
    router.replace(target);
  }, [router, searchParams]);

  return (
    <div
      data-testid="i-guard-redirect-placeholder"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#F0F9FF',
        color: '#64748B',
        fontSize: 14,
      }}
    >
      正在跳转到档案列表…
    </div>
  );
}

export default function IGuardPageRedirect() {
  return (
    <Suspense fallback={
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#F0F9FF',
          color: '#64748B',
          fontSize: 14,
        }}
      >
        加载中…
      </div>
    }>
      <IGuardRedirectInner />
    </Suspense>
  );
}
