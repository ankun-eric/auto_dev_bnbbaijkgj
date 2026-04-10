'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';

interface TemplateCategory {
  id: number;
  name: string;
  description: string;
  icon: string;
  user_plan_count: number;
}

const FALLBACK_COLORS = ['#52c41a', '#1890ff', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#faad14'];

export default function CustomPlanPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<TemplateCategory[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res: any = await api.get('/api/health-plan/template-categories');
        const data = res.data || res;
        setCategories(data.items || data || []);
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>自定义计划</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>自定义计划</NavBar>

      <div className="px-4 py-4" style={{ background: 'linear-gradient(135deg, #1890ff, #40a9ff)' }}>
        <div className="text-white text-center">
          <div className="text-lg font-bold">📋 自定义计划</div>
          <div className="text-xs opacity-80 mt-1">选择模板分类，创建个性化健康管理计划</div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        {categories.length === 0 ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '40px 20px' }}>
            <div className="text-4xl mb-3">📋</div>
            <div className="text-gray-400 text-sm">暂无模板分类</div>
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {categories.map((cat, i) => {
              const color = FALLBACK_COLORS[i % FALLBACK_COLORS.length];
              return (
                <Card
                  key={cat.id}
                  onClick={() => router.push(`/health-plan/custom/${cat.id}`)}
                  style={{ borderRadius: 12, overflow: 'hidden', padding: 0 }}
                  bodyStyle={{ padding: 0 }}
                >
                  <div className="p-4">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center text-xl mb-3"
                      style={{ background: `${color}15` }}
                    >
                      {cat.icon || '📋'}
                    </div>
                    <div className="font-bold text-sm mb-1">{cat.name}</div>
                    <div className="text-xs text-gray-400 mb-2 line-clamp-2" style={{ minHeight: 32 }}>
                      {cat.description}
                    </div>
                    {cat.user_plan_count > 0 && (
                      <span
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: `${color}15`, color }}
                      >
                        {cat.user_plan_count} 个计划
                      </span>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
