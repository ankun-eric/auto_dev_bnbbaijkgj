'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Card, Button, ProgressBar, SpinLoading, Toast, Tag } from 'antd-mobile';
import api from '@/lib/api';

interface PlanTask {
  id: number;
  name: string;
  task_name?: string;
  is_checked: boolean;
  today_completed?: boolean;
}

interface MyPlanDetail {
  id: number;
  name: string;
  plan_name?: string;
  description: string;
  current_day: number;
  total_days: number | null;
  duration_days: number | null;
  progress: number;
  status: string;
  category_name: string;
  tasks: PlanTask[];
}

export default function MyPlanExecutionPage() {
  const router = useRouter();
  const params = useParams();
  const planId = params.planId as string;

  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState<MyPlanDetail | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res: any = await api.get(`/api/health-plan/user-plans/${planId}`);
      const raw = res.data || res;
      const mappedTasks = (raw.tasks || []).map((t: any) => ({
        ...t,
        name: t.task_name || t.name,
        is_checked: t.today_completed || false,
      }));
      const completedCount = mappedTasks.filter((t: any) => t.is_checked).length;
      const totalCount = mappedTasks.length;
      setPlan({
        ...raw,
        name: raw.plan_name || raw.name,
        total_days: raw.duration_days || raw.total_days,
        progress: totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0,
        tasks: mappedTasks,
      });
    } catch {
      Toast.show({ content: '加载失败', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSimpleCheck = async (task: PlanTask) => {
    try {
      await api.post(`/api/health-plan/user-plans/${planId}/tasks/${task.id}/checkin`, { actual_value: null });
      Toast.show({ content: '打卡成功', icon: 'success' });
      fetchData();
    } catch {
      Toast.show({ content: '打卡失败', icon: 'fail' });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>加载中...</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>计划详情</NavBar>
        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-4xl mb-3">😔</div>
          <div className="text-gray-400 text-sm">计划不存在</div>
        </div>
      </div>
    );
  }

  const completedTasks = plan.tasks?.filter((t) => t.is_checked).length || 0;
  const totalTasks = plan.tasks?.length || 0;

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>{plan.name}</NavBar>

      <div className="px-4 py-5" style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
        <div className="text-white">
          <div className="flex items-center justify-between mb-2">
            <div className="text-lg font-bold">{plan.name}</div>
            <Tag
              style={{
                '--background-color': 'rgba(255,255,255,0.2)',
                '--text-color': '#fff',
                '--border-color': 'transparent',
                fontSize: 11,
              }}
            >
              {plan.status === 'active' ? '进行中' : plan.status === 'completed' ? '已完成' : '已暂停'}
            </Tag>
          </div>
          {plan.description && (
            <div className="text-sm opacity-80 mb-3">{plan.description}</div>
          )}
          <div className="flex items-center justify-between text-xs opacity-80 mb-2">
            <span>
              {plan.total_days ? `第 ${plan.current_day}/${plan.total_days} 天` : `第 ${plan.current_day} 天`}
            </span>
            <span>今日 {completedTasks}/{totalTasks} 已完成</span>
          </div>
          <ProgressBar
            percent={plan.progress}
            style={{
              '--track-width': '8px',
              '--fill-color': '#fff',
              '--track-color': 'rgba(255,255,255,0.3)',
            }}
          />
          <div className="text-right text-xs opacity-80 mt-1">总进度 {plan.progress}%</div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12 }}>
          <div className="section-title">今日任务</div>
          {(!plan.tasks || plan.tasks.length === 0) ? (
            <div className="text-center text-gray-400 text-sm py-4">暂无任务</div>
          ) : (
            plan.tasks.map((task) => (
                <div key={task.id} className="py-3 border-b border-gray-50 last:border-b-0">
                  <div className="flex items-center">
                    <div
                      className="w-5 h-5 rounded-full border-2 flex items-center justify-center mr-3 shrink-0 cursor-pointer"
                      style={{
                        borderColor: task.is_checked ? '#52c41a' : '#ddd',
                        background: task.is_checked ? '#52c41a' : 'transparent',
                      }}
                      onClick={() => {
                        if (!task.is_checked) handleSimpleCheck(task);
                      }}
                    >
                      {task.is_checked && <span className="text-white text-xs">✓</span>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={`text-sm ${task.is_checked ? 'text-gray-400 line-through' : ''}`}>
                        {task.name}
                      </div>
                    </div>
                    {!task.is_checked && (
                      <Button
                        size="mini"
                        color="primary"
                        style={{ borderRadius: 8, background: '#52c41a', border: 'none' }}
                        onClick={() => handleSimpleCheck(task)}
                      >
                        打卡
                      </Button>
                    )}
                    {task.is_checked && (
                      <span className="text-xs text-gray-400">已完成</span>
                    )}
                  </div>
                </div>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}
