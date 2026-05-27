'use client';

/**
 * [PRD-GUARDIAN-V1.3.1 §0/§9] 路径收敛 - v13 兼容重定向
 *
 * v1.3.1 要求：取消 v13 / i-guard / 主页 三个路径的混乱。
 * 本页面作为旧路径兼容入口，统一重定向到 /health-profile/i-guard（v1.3.1 守护人统一列表）。
 *
 * 注：根据现有项目结构，v1.3.1「我守护的人」实际页面挂在 /health-profile/i-guard。
 * 主健康档案页 /health-profile 通过卡片入口进入 i-guard。
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HealthProfileV13Redirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/health-profile/i-guard');
  }, [router]);
  return (
    <div style={{ padding: 40, textAlign: 'center', color: '#64748B', fontSize: 14 }}>
      正在跳转到「我守护的人」…
    </div>
  );
}
