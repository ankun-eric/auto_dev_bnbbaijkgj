'use client';

/**
 * [PRD-HEALTH-ARCHIVE-V5-20260521 F16/F17] 旧页面已下线：
 *   - 健康档案"我的设备"卡片 → 改指向 /devices
 *   - 旧路由 /devices/member 仅保留为兼容重定向桩
 *
 * 老版本 App 访问会被重定向到 /devices；待全量更新后可彻底删除该桩。
 */

export const dynamic = 'force-dynamic';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function DevicesMemberRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    try {
      router.replace('/devices');
    } catch {
      if (typeof window !== 'undefined') window.location.href = '/devices';
    }
  }, [router]);

  return (
    <div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>
      该页面已下线，正在跳转到「我的设备」…
    </div>
  );
}
