'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default function RootPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // [PRD-AI-HOME-V1 2026-05-19] (tabs) 路由组已归档，菜单模式首页 /home 下线，
    // 强制收敛为 AI 首页 /ai-home。保留对 /api/app-settings/page-style 的调用以兼容旧后端，
    // 但无论返回什么值，前端一律落到 /ai-home。
    fetch(`${basePath}/api/app-settings/page-style`)
      .then(res => res.json())
      .catch(() => {})
      .finally(() => {
        router.replace('/ai-home');
        setLoading(false);
      });
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
