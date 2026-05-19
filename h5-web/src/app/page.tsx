'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RootPage() {
  const router = useRouter();

  // [PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19]
  // 旧 page-style 兼容 fetch 已删除：H5 端唯一首页为 /ai-home，不再需要根据
  // /api/app-settings/page-style 做任何路由分支判断。
  useEffect(() => {
    router.replace('/ai-home');
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen" style={{ background: '#F5F6FA' }}>
      <div className="text-center">
        <div className="text-4xl mb-4">🌿</div>
        <div style={{ color: '#0EA5E9' }} className="font-bold text-lg">宾尼小康</div>
        <div className="text-gray-400 text-sm mt-1">AI健康管家</div>
      </div>
    </div>
  );
}
