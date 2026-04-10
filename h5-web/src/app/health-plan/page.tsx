'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';

interface PlanCounts {
  medications_count: number;
  checkin_count: number;
  custom_plan_count: number;
  completed_count: number;
  total_count: number;
}

const categories = [
  {
    key: 'medications',
    title: '用药提醒',
    desc: '设置每日用药时间，按时推送提醒',
    icon: '💊',
    color: '#fa8c16',
    gradient: 'linear-gradient(135deg, #fa8c16, #f5af19)',
    countKey: 'medications_count' as keyof PlanCounts,
  },
  {
    key: 'checkin',
    title: '健康打卡',
    desc: '自定义每日健康习惯打卡项',
    icon: '✅',
    color: '#52c41a',
    gradient: 'linear-gradient(135deg, #52c41a, #73d13d)',
    countKey: 'checkin_count' as keyof PlanCounts,
  },
  {
    key: 'custom',
    title: '自定义计划',
    desc: '基于模板创建个性化健康管理计划',
    icon: '📋',
    color: '#1890ff',
    gradient: 'linear-gradient(135deg, #1890ff, #40a9ff)',
    countKey: 'custom_plan_count' as keyof PlanCounts,
  },
];

export default function HealthPlanPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [counts, setCounts] = useState<PlanCounts | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [todosRes, medsRes, checkinRes, plansRes] = await Promise.allSettled([
          api.get('/api/health-plan/today-todos'),
          api.get('/api/health-plan/medications'),
          api.get('/api/health-plan/checkin-items'),
          api.get('/api/health-plan/user-plans'),
        ]);

        const todosData: any = todosRes.status === 'fulfilled' ? ((todosRes.value as any).data || todosRes.value) : {};
        const medsData: any = medsRes.status === 'fulfilled' ? ((medsRes.value as any).data || medsRes.value) : {};
        const checkinData: any = checkinRes.status === 'fulfilled' ? ((checkinRes.value as any).data || checkinRes.value) : {};
        const plansData: any = plansRes.status === 'fulfilled' ? ((plansRes.value as any).data || plansRes.value) : {};

        const medsGroups = medsData.groups || {};
        let medsCount = 0;
        Object.values(medsGroups).forEach((items: any) => { medsCount += Array.isArray(items) ? items.length : 0; });

        const checkinItems = checkinData.items || checkinData || [];
        const checkinCount = Array.isArray(checkinItems) ? checkinItems.length : 0;

        const userPlans = plansData.items || plansData || [];
        const plansCount = Array.isArray(userPlans) ? userPlans.length : 0;

        setCounts({
          medications_count: medsCount,
          checkin_count: checkinCount,
          custom_plan_count: plansCount,
          completed_count: todosData.total_completed || 0,
          total_count: todosData.total_count || 0,
        });
      } catch {
        setCounts({ medications_count: 0, checkin_count: 0, custom_plan_count: 0, completed_count: 0, total_count: 0 });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleAIGenerate = () => {
    Toast.show({ content: 'AI正在为您生成个性化健康计划...', icon: 'loading' });
    setTimeout(() => {
      const sessionId = `plan-${Date.now()}`;
      router.push(`/chat/${sessionId}?type=health&msg=${encodeURIComponent('请根据我的健康档案为我制定一份个性化的健康计划')}`);
    }, 1000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>健康计划</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>健康计划</NavBar>

      <div className="px-4 py-5" style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
        <div className="text-white text-center">
          <div className="text-lg font-bold mb-1">AI 健康计划</div>
          <div className="text-xs opacity-80 mb-4">根据您的健康档案，智能生成专属健康方案</div>
        </div>
        <div
          onClick={handleAIGenerate}
          className="flex items-center justify-center py-3 rounded-xl cursor-pointer"
          style={{
            background: 'rgba(255,255,255,0.95)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          }}
        >
          <span className="text-xl mr-2">🤖</span>
          <span className="text-base font-bold" style={{ color: '#52c41a' }}>AI 为我生成计划</span>
        </div>
        {counts && counts.total_count > 0 && (
          <div className="flex items-center justify-center mt-3 text-white text-xs opacity-80">
            今日待办 {counts.completed_count}/{counts.total_count} 已完成
          </div>
        )}
      </div>

      <div className="px-4 -mt-3">
        {categories.map((cat) => (
          <Card
            key={cat.key}
            onClick={() => router.push(`/health-plan/${cat.key}`)}
            style={{ borderRadius: 12, marginBottom: 12, overflow: 'hidden', padding: 0 }}
            bodyStyle={{ padding: 0 }}
          >
            <div className="flex items-center p-4">
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mr-4 shrink-0"
                style={{ background: `${cat.color}15` }}
              >
                {cat.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-base">{cat.title}</span>
                  {counts && (
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: `${cat.color}15`, color: cat.color }}
                    >
                      {counts[cat.countKey] || 0} 项
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-400 mt-1">{cat.desc}</div>
              </div>
              <div className="ml-2 text-gray-300">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
            </div>
          </Card>
        ))}

        <div
          className="card cursor-pointer flex items-center justify-center py-4"
          onClick={() => router.push('/health-plan/statistics')}
          style={{ background: 'linear-gradient(135deg, #f0faf0, #e8f8f5)', border: '1px dashed #52c41a40' }}
        >
          <span className="text-xl mr-2">📊</span>
          <span className="text-sm font-medium" style={{ color: '#52c41a' }}>查看打卡统计</span>
        </div>
      </div>
    </div>
  );
}
