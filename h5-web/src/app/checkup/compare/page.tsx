'use client';

/** [2026-04-23] 旧结构化对比已下线，跳转到新的对比选择页。 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function CheckupCompareLegacyPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/checkup/compare/select');
  }, [router]);
  return (
    <div style={{ padding: 40, textAlign: 'center', color: '#999', fontSize: 14 }}>
      报告对比已升级为对话式，正在跳转...
    </div>
  );
}
