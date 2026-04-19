'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, Button, SpinLoading, Toast, Tag, Dialog } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface PlanTask {
  id: number;
  name: string;
  task_name?: string;
  target_value: number | null;
  target_unit: string;
  sort_order: number;
}

interface PlanDetail {
  id: number;
  name: string;
  description: string;
  target_audience: string;
  duration_days: number;
  tasks: PlanTask[];
  category_name: string;
  is_joined: boolean;
}

export default function RecommendedPlanDetailPage() {
  const router = useRouter();
  const params = useParams();
  const planId = params.planId as string;

  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [plan, setPlan] = useState<PlanDetail | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res: any = await api.get(`/api/health-plan/recommended-plans/${planId}`);
        const raw = res.data || res;
        const mappedTasks = (raw.tasks || []).map((t: any) => ({
          ...t,
          name: t.task_name || t.name,
        }));
        setPlan({ ...raw, tasks: mappedTasks });
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [planId]);

  const handleJoin = async () => {
    if (!plan) return;
    const confirmed = await Dialog.confirm({
      content: `确定加入「${plan.name}」吗？加入后每日任务将出现在您的今日待办中。`,
    });
    if (!confirmed) return;

    setJoining(true);
    try {
      await api.post(`/api/health-plan/recommended-plans/${planId}/join`);
      Toast.show({ content: '加入成功', icon: 'success' });
      router.back();
    } catch {
      Toast.show({ content: '加入失败', icon: 'fail' });
    } finally {
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>加载中...</GreenNavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>计划详情</GreenNavBar>
        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-4xl mb-3">😔</div>
          <div className="text-gray-400 text-sm">计划不存在</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <GreenNavBar>计划详情</GreenNavBar>

      <div className="px-4 py-5" style={{ background: 'linear-gradient(135deg, #1890ff, #40a9ff)' }}>
        <div className="text-white">
          <div className="text-xl font-bold mb-2">{plan.name}</div>
          <div className="text-sm opacity-90 mb-3">{plan.description}</div>
          <div className="flex items-center gap-3">
            {plan.target_audience && (
              <Tag
                style={{
                  '--background-color': 'rgba(255,255,255,0.2)',
                  '--text-color': '#fff',
                  '--border-color': 'transparent',
                  fontSize: 11,
                }}
              >
                适合: {plan.target_audience}
              </Tag>
            )}
            <Tag
              style={{
                '--background-color': 'rgba(255,255,255,0.2)',
                '--text-color': '#fff',
                '--border-color': 'transparent',
                fontSize: 11,
              }}
            >
              周期: {plan.duration_days}天
            </Tag>
            {plan.category_name && (
              <Tag
                style={{
                  '--background-color': 'rgba(255,255,255,0.2)',
                  '--text-color': '#fff',
                  '--border-color': 'transparent',
                  fontSize: 11,
                }}
              >
                {plan.category_name}
              </Tag>
            )}
          </div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12 }}>
          <div className="section-title">每日任务 ({plan.tasks?.length || 0}项)</div>
          {(!plan.tasks || plan.tasks.length === 0) ? (
            <div className="text-center text-gray-400 text-sm py-4">暂无任务</div>
          ) : (
            plan.tasks.map((task, idx) => (
              <div
                key={task.id}
                className="flex items-center py-3 border-b border-gray-50 last:border-b-0"
              >
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mr-3 shrink-0"
                  style={{ background: '#1890ff15', color: '#1890ff' }}
                >
                  {idx + 1}
                </div>
                <div className="flex-1">
                  <div className="text-sm">{task.name}</div>
                  {task.target_value && (
                    <div className="text-xs text-gray-400 mt-0.5">
                      目标: {task.target_value}{task.target_unit}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </Card>
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        {plan.is_joined ? (
          <Button
            block
            size="large"
            disabled
            style={{ borderRadius: 12, height: 48 }}
          >
            已加入此计划
          </Button>
        ) : (
          <Button
            block
            color="primary"
            size="large"
            loading={joining}
            style={{ borderRadius: 12, background: 'linear-gradient(135deg, #1890ff, #40a9ff)', border: 'none', height: 48 }}
            onClick={handleJoin}
          >
            加入计划
          </Button>
        )}
      </div>
    </div>
  );
}
