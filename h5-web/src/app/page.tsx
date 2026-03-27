'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/home');
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="text-4xl mb-4">🌿</div>
        <div className="text-primary font-bold text-lg">宾尼小康</div>
        <div className="text-gray-400 text-sm mt-1">AI健康管家</div>
      </div>
    </div>
  );
}
