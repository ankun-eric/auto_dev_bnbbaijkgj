'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, SpinLoading, Toast, Tag, SwipeAction, Dialog, Button } from 'antd-mobile';
import { EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface UserPlan {
  id: number;
  plan_name: string;
  name?: string;
  description: string;
  status: string;
  duration_days: number | null;
  current_day: number;
}

export default function CustomPlanPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<UserPlan[]>([]);

  const fetchData = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-plan/user-plans');
      const data = res.data || res;
      setPlans(data.items || data || []);
    } catch {
      Toast.show({ content: '加载失败', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleDelete = async (plan: UserPlan) => {
    const confirmed = await Dialog.confirm({
      content: `确认删除计划「${plan.plan_name || plan.name}」？`,
      confirmText: '删除',
      cancelText: '取消',
    });
    if (!confirmed) return;
    try {
      await api.delete(`/api/health-plan/user-plans/${plan.id}`);
      Toast.show({ content: '删除成功', icon: 'success' });
      fetchData();
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'active': return { text: '进行中', color: '#52c41a' };
      case 'completed': return { text: '已完成', color: '#1890ff' };
      case 'paused': return { text: '已暂停', color: '#faad14' };
      default: return { text: status, color: '#999' };
    }
  };

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
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>自定义计划</NavBar>

      <div className="px-4 py-4" style={{ background: 'linear-gradient(135deg, #1890ff, #40a9ff)' }}>
        <div className="text-white text-center">
          <div className="text-lg font-bold">📋 我的计划列表</div>
          <div className="text-xs opacity-80 mt-1">管理您的个人健康计划</div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        {plans.length === 0 ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '40px 20px' }}>
            <div className="text-4xl mb-3">📋</div>
            <div className="text-gray-400 text-sm mb-4">暂无计划，快来创建一个吧</div>
            <Button
              color="primary"
              style={{ borderRadius: 8, background: '#52c41a', border: 'none' }}
              onClick={() => router.push('/health-plan/custom/create')}
            >
              创建计划
            </Button>
          </Card>
        ) : (
          plans.map((plan) => {
            const sl = statusLabel(plan.status);
            const displayName = plan.plan_name || plan.name || '未命名计划';
            return (
              <SwipeAction
                key={plan.id}
                style={{ marginBottom: 12 }}
                rightActions={[
                  {
                    key: 'edit',
                    text: '编辑',
                    color: 'primary',
                    onClick: () => router.push(`/health-plan/custom/create?editId=${plan.id}`),
                  },
                  {
                    key: 'delete',
                    text: '删除',
                    color: 'danger',
                    onClick: () => handleDelete(plan),
                  },
                ]}
              >
                <Card
                  onClick={() => router.push(`/health-plan/custom/my-plan/${plan.id}`)}
                  style={{ borderRadius: 12, overflow: 'hidden', padding: 0 }}
                  bodyStyle={{ padding: 0 }}
                >
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-bold text-base flex-1 min-w-0 truncate">{displayName}</div>
                      <div className="flex items-center gap-2 ml-2 shrink-0">
                        <Tag
                          style={{
                            '--background-color': `${sl.color}15`,
                            '--text-color': sl.color,
                            '--border-color': 'transparent',
                            fontSize: 11,
                          }}
                        >
                          {sl.text}
                        </Tag>
                        <EditSOutline
                          className="text-gray-400 cursor-pointer"
                          fontSize={18}
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/health-plan/custom/create?editId=${plan.id}`);
                          }}
                        />
                        <DeleteOutline
                          className="text-gray-400 cursor-pointer"
                          fontSize={18}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(plan);
                          }}
                        />
                      </div>
                    </div>
                    {plan.description && (
                      <div className="text-xs text-gray-400 mb-2 line-clamp-2">{plan.description}</div>
                    )}
                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      <span>
                        {plan.duration_days ? `${plan.duration_days} 天计划` : '无限期'}
                      </span>
                      <span>第 {plan.current_day || 1} 天</span>
                    </div>
                  </div>
                </Card>
              </SwipeAction>
            );
          })
        )}
      </div>

      <div
        className="fixed bottom-0 left-0 right-0 p-4 bg-white"
        style={{
          maxWidth: 750,
          margin: '0 auto',
          boxShadow: '0 -2px 8px rgba(0,0,0,0.06)',
          paddingBottom: 'calc(16px + env(safe-area-inset-bottom))',
        }}
      >
        <Button
          block
          color="primary"
          size="large"
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #52c41a, #13c2c2)', border: 'none', height: 48 }}
          onClick={() => router.push('/health-plan/custom/create')}
        >
          创建计划
        </Button>
      </div>
    </div>
  );
}
