'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from 'antd-mobile';
import { Suspense } from 'react';

const features = [
  { icon: '🤖', title: 'AI健康问答', description: '智能AI为您解答各类健康疑问，随时随地获取专业建议' },
  { icon: '🔍', title: '智能症状自查', description: '输入症状即可获得初步分析，帮助您更好地了解身体状况' },
  { icon: '📊', title: '体检报告AI解读', description: '上传体检报告，AI为您解读各项指标含义及健康风险' },
  { icon: '🏥', title: '中医体质辨识', description: '基于中医理论的体质评估，为您推荐个性化调理方案' },
  { icon: '📋', title: '个性化健康计划', description: '根据您的身体状况定制专属健康计划，科学管理每一天' },
];

function LandingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const ref = searchParams.get('ref') || '';

  const handleRegister = () => {
    router.push(ref ? `/login?ref=${ref}` : '/login');
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#fff' }}>
      <div
        className="relative px-6 pt-14 pb-10 text-center"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{ background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(10px)' }}>
          <span className="text-4xl">🌿</span>
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">宾尼小康</h1>
        <p className="text-white/80 text-sm">AI健康管家 · 您的私人健康助手</p>
      </div>

      <div className="px-5 py-8 flex-1">
        <h2 className="text-lg font-bold text-center mb-6" style={{ color: '#333' }}>
          为什么选择宾尼小康？
        </h2>

        <div className="space-y-4">
          {features.map((f, i) => (
            <div
              key={i}
              className="flex items-start gap-4 p-4 rounded-2xl"
              style={{ background: '#f8fdf5', border: '1px solid #e8f5e0' }}
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
              >
                <span className="text-2xl">{f.icon}</span>
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-bold mb-1" style={{ color: '#333' }}>{f.title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{f.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="sticky bottom-0 px-6 py-4 bg-white" style={{ boxShadow: '0 -4px 12px rgba(0,0,0,0.05)' }}>
        <Button
          block
          onClick={handleRegister}
          style={{
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
            borderRadius: '24px',
            height: '50px',
            fontSize: '17px',
            fontWeight: 700,
          }}
        >
          立即注册
        </Button>
        <p className="text-center text-xs text-gray-300 mt-2">注册即享全部AI健康服务</p>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-400 text-sm">加载中...</div>
      </div>
    }>
      <LandingContent />
    </Suspense>
  );
}
