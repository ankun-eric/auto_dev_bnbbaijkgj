'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Button, Toast, Grid, SpinLoading, Tag } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface DailyTask {
  key: string;
  title: string;
  subtitle?: string;
  points: number;
  category: 'daily' | 'once' | 'repeatable';
  completed: boolean;
  status?: 'pending' | 'completed';
  completed_at?: string | null;
  fields_filled?: boolean;
  pending_count?: number;
  invited_count?: number;
  action_type: 'sign_in' | 'navigate';
  route?: string;
}

// Bug 7：完善健康档案统一跳转 /health-profile
// Bug 8：移除 first_order 硬编码（后端已过滤，完全由后端 task.route 驱动）
const TASK_ROUTE_OVERRIDES: Record<string, string> = {
  complete_profile: '/health-profile',
};

const CATEGORY_LABEL: Record<string, { text: string; color: string }> = {
  daily: { text: '每日', color: '#52c41a' },
  once: { text: '一次性', color: '#fa8c16' },
  repeatable: { text: '可重复', color: '#1890ff' },
};

export default function PointsPage() {
  const router = useRouter();
  // Bug#4：可用积分严禁前端自己累加流水，统一走 /api/points/summary
  const [availablePoints, setAvailablePoints] = useState(0);
  const [todayEarned, setTodayEarned] = useState(0);
  const [signedToday, setSignedToday] = useState(false);
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [summaryRes, tasksRes]: any[] = await Promise.allSettled([
        api.get('/api/points/summary'),
        api.get('/api/points/tasks'),
      ]);
      if (summaryRes.status === 'fulfilled') {
        const s = summaryRes.value?.data || summaryRes.value;
        setAvailablePoints(Number(s?.available_points ?? s?.total_points ?? 0));
        setTodayEarned(s?.today_earned_points ?? 0);
        setSignedToday(s?.signed_today ?? false);
      }
      if (tasksRes.status === 'fulfilled') {
        const d = tasksRes.value?.data || tasksRes.value;
        const items = d?.items || [];
        setTasks(Array.isArray(items) ? items : []);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSign = async () => {
    if (signedToday || signing) return;
    setSigning(true);
    try {
      const res: any = await api.post('/api/points/signin');
      const data = res?.data || res || {};
      const earned = data?.points_earned ?? 0;
      Toast.show({ content: earned ? `签到成功 +${earned}积分` : '签到成功' });
      fetchData();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '签到失败', icon: 'fail' });
    } finally {
      setSigning(false);
    }
  };

  const handleTaskClick = (task: DailyTask) => {
    if (task.action_type === 'sign_in') {
      handleSign();
      return;
    }
    if (task.completed && task.category === 'once') return;
    const route = TASK_ROUTE_OVERRIDES[task.key] || task.route;
    if (route) router.push(route);
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-8">
      <GreenNavBar
        right={
          <span
            className="text-white text-sm cursor-pointer"
            onClick={() => router.push('/points/detail')}
          >
            积分明细 ›
          </span>
        }
      >
        积分中心
      </GreenNavBar>

      {/* Bug 3：我的积分卡片背景色统一为 #C8E6C9（浅绿），与上方深绿标题区形成层次 */}
      <div
        className="px-4 pt-6 pb-8 text-center"
        style={{ background: '#C8E6C9' }}
      >
        <div className="text-sm" style={{ color: '#1B5E20' }}>可用积分</div>
        <div className="text-4xl font-bold my-2" style={{ color: '#1B5E20' }}>
          {loading ? '--' : availablePoints}
        </div>
        <div className="text-sm mt-1" style={{ color: '#2E7D32' }}>
          {todayEarned > 0
            ? `今天获得积分 +${todayEarned}`
            : '今天还未获得积分，快去赚取吧'}
        </div>
      </div>

      <div className="px-4 -mt-3">
        <Grid columns={1} gap={12} style={{ marginBottom: 16 }}>
          <Grid.Item>
            <Card
              style={{ borderRadius: 12 }}
              onClick={() => router.push('/points/mall')}
            >
              <div className="flex items-center">
                <div className="text-2xl mr-3">🎁</div>
                <div className="flex-1">
                  <div className="font-medium">积分商城</div>
                  <div className="text-xs text-gray-400">用积分兑换好礼</div>
                </div>
                <span className="text-gray-300">›</span>
              </div>
            </Card>
          </Grid.Item>
        </Grid>

        <div className="flex items-center justify-between mb-3">
          <span className="text-base font-semibold">日常任务</span>
          <span className="text-xs text-gray-400">完成任务赚积分</span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-10">
            <SpinLoading color="primary" />
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((t) => {
              const cat = CATEGORY_LABEL[t.category] || CATEGORY_LABEL.daily;
              // Bug 6：一次性任务完成后置灰、不可点击；7 天后由后端不再返回
              const onceDone = t.completed && t.category === 'once';
              const disabled = onceDone;
              const btnText = onceDone
                ? '已完成 ✓'
                : t.completed && t.category === 'daily'
                ? '已完成'
                : t.action_type === 'sign_in'
                ? '去签到'
                : t.key === 'complete_profile'
                ? '去完善'
                : '去完成';
              return (
                <Card
                  key={t.key}
                  style={{
                    borderRadius: 12,
                    opacity: onceDone ? 0.55 : 1,
                    background: onceDone ? '#f5f5f5' : '#fff',
                    cursor: onceDone ? 'not-allowed' : 'pointer',
                  }}
                  onClick={() => { if (!onceDone) handleTaskClick(t); }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 mr-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className="font-medium text-sm"
                          style={{
                            color: onceDone ? '#999' : undefined,
                            textDecoration: onceDone ? 'line-through' : 'none',
                          }}
                        >
                          {t.title}
                          {onceDone ? ' ✓ 已完成' : ''}
                        </span>
                        <Tag
                          fill="outline"
                          style={{
                            '--background-color': onceDone ? '#eeeeee' : `${cat.color}10`,
                            '--text-color': onceDone ? '#bfbfbf' : cat.color,
                            '--border-color': onceDone ? '#d9d9d9' : cat.color,
                            fontSize: 10,
                          }}
                        >
                          {cat.text}
                        </Tag>
                        <span style={{ color: onceDone ? '#bfbfbf' : '#fa8c16', fontSize: 12 }}>
                          +{t.points} 积分
                        </span>
                      </div>
                      {t.subtitle && (
                        <div className="text-xs" style={{ color: onceDone ? '#bfbfbf' : '#999' }}>
                          {t.subtitle}
                        </div>
                      )}
                    </div>
                    <Button
                      size="small"
                      disabled={disabled || (t.action_type === 'sign_in' && signedToday)}
                      loading={t.action_type === 'sign_in' && signing}
                      onClick={(e) => { e.stopPropagation(); handleTaskClick(t); }}
                      style={{
                        background: disabled || (t.action_type === 'sign_in' && signedToday)
                          ? '#e8e8e8'
                          : 'linear-gradient(135deg, #52c41a, #13c2c2)',
                        color: disabled || (t.action_type === 'sign_in' && signedToday) ? '#999' : '#fff',
                        border: 'none',
                        borderRadius: 16,
                        fontSize: 12,
                        minWidth: 72,
                      }}
                    >
                      {t.action_type === 'sign_in' && signedToday ? '已签到' : btnText}
                    </Button>
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
