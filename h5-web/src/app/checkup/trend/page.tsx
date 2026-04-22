'use client';

/** [2026-04-23] 趋势分析已下线，重定向到体检报告列表。 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function CheckupTrendRemovedPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/checkup');
  }, [router]);
  return (
    <div style={{ padding: 40, textAlign: 'center', color: '#999', fontSize: 14 }}>
      趋势分析功能已下线，正在跳转...
    </div>
  );
}
