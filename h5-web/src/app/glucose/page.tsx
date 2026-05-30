'use client';

/**
 * [PRD-GLUCOSE-CARD-OPTIMIZE-V1 2026-05-30] 旧【血糖管理】整页已物理下线。
 *
 * 原页面承载的所有功能（录入 / 趋势 / 历史 / AI 解读 / 预警 / 健康报告）
 * 已全部并入【健康档案】→【血糖卡片】→【血糖详情页】（/health-metric/blood_glucose）。
 *
 * 为避免历史外链与第三方分享链接形成死链，此处提供 301-style 客户端跳转兜底，
 * 自动将访问者引导到健康档案首页（用户在那里点击血糖卡片可进入新详情页）。
 *
 * 注意：Next.js App Router 在静态预渲染时，`useSearchParams` 必须被 <Suspense> 包裹，
 * 否则 `npm run build` 会报 prerender error。这里用一个内部 Inner 组件 + Suspense 包裹。
 */
import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function ObsoleteGlucoseInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const profileId = searchParams?.get('profileId');
    if (profileId) {
      router.replace(`/health-metric/blood_glucose?profileId=${profileId}`);
    } else {
      router.replace('/health-profile');
    }
  }, [router, searchParams]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, textAlign: 'center', background: '#F4F7FB', color: '#475569', fontSize: 14 }}>
      <div>
        <div style={{ fontSize: 36, marginBottom: 12 }}>🩸</div>
        <div style={{ fontWeight: 700, color: '#0C4A6E', marginBottom: 6 }}>页面已迁移</div>
        <div>血糖管理已合并进【健康档案 → 血糖卡片】，正在为您跳转…</div>
      </div>
    </div>
  );
}

export default function ObsoleteGlucosePage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F4F7FB', color: '#475569', fontSize: 14 }}>
        <div>正在跳转…</div>
      </div>
    }>
      <ObsoleteGlucoseInner />
    </Suspense>
  );
}
