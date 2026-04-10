'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from 'antd-mobile';

export default function FamilyPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/health-profile');
  }, [router]);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-6 px-8"
      style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}
    >
      <div className="text-4xl">👨‍👩‍👧‍👦</div>
      <div className="text-base text-gray-600 text-center">家庭成员管理已迁移到健康档案页面</div>
      <Button
        style={{
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          color: '#fff',
          border: 'none',
          borderRadius: 24,
          height: 44,
          paddingLeft: 32,
          paddingRight: 32,
        }}
        onClick={() => router.replace('/health-profile')}
      >
        前往健康档案
      </Button>
    </div>
  );
}
