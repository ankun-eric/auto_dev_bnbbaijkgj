'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { SpinLoading } from 'antd-mobile';

/**
 * 已废弃：我的档案列表页。
 * PRD v1.0（测评记录优化）已将测评记录合并到 /tcm 主页下方。
 * 此路由仅作为兜底重定向，自动回到 /tcm。
 */
export default function DeprecatedArchivePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/tcm');
  }, [router]);
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SpinLoading style={{ '--size': '32px', '--color': '#52c41a' }} />
    </div>
  );
}
