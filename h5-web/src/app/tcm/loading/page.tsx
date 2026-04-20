'use client';

import { useEffect, useState } from 'react';
import { SpinLoading } from 'antd-mobile';

const LOADING_TIPS = [
  '正在分析您的体质特征...',
  '正在比对 9 种体质标准...',
  '正在为您匹配个性化方案...',
  '正在生成专属养生处方...',
  '正在计算体质雷达图...',
];

export default function TcmLoadingPage() {
  const [tipIndex, setTipIndex] = useState(0);

  useEffect(() => {
    const t = setInterval(() => {
      setTipIndex((i) => (i + 1) % LOADING_TIPS.length);
    }, 1200);
    return () => clearInterval(t);
  }, []);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-6"
      style={{ background: 'linear-gradient(180deg, #f6ffed 0%, #e6fffb 50%, #fff 100%)' }}
    >
      <div className="text-6xl mb-4 animate-pulse">🌿</div>
      <div className="text-lg font-semibold text-gray-800 mb-3">数字中医师分析中</div>
      <div className="mb-6">
        <SpinLoading style={{ '--size': '44px', '--color': '#52c41a' }} />
      </div>
      <div
        className="text-sm min-h-[24px] text-center"
        style={{ color: '#52c41a', fontWeight: 500 }}
      >
        {LOADING_TIPS[tipIndex]}
      </div>
      <div className="mt-10 text-[11px] text-gray-400 text-center px-8 leading-relaxed">
        本测评融合 AI 与《中医体质分类与判定》思路，<br />
        为您生成个性化养生方案。
      </div>
    </div>
  );
}
