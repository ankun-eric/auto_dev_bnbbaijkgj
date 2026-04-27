'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default function RootPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${basePath}/api/app-settings/page-style`)
      .then(res => res.json())
      .then(data => {
        if (data.value === 'menu') {
          router.replace('/home');
        } else {
          router.replace('/ai-home');
        }
      })
      .catch(() => router.replace('/ai-home'))
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen" style={{ background: '#F5F6FA' }}>
      <div className="text-center">
        <div className="text-4xl mb-4">🌿</div>
        <div style={{ color: '#5B6CFF' }} className="font-bold text-lg">宾尼小康</div>
        <div className="text-gray-400 text-sm mt-1">AI健康管家</div>
      </div>
    </div>
  );
}
