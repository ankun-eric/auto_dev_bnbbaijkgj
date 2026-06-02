'use client';

/**
 * [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 重新接通 /health-plan/checkin
 *
 * 旧版被强制跳回 /ai-home 已废止。本次：将该路径作为旧链接兼容入口，重定向到新的
 * 打卡落地页 /health-plan（落地页即打卡首页）。
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function CheckinLegacyRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/health-plan');
  }, [router]);

  return (
    <div
      data-testid="health-plan-checkin-redirect-v1"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#6B7280',
        fontSize: 14,
        background: '#F5F5F7',
      }}
    >
      正在打开健康打卡...
    </div>
  );
}
