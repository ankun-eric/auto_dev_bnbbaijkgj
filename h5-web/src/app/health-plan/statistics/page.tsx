'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, SpinLoading, Toast, ProgressBar } from 'antd-mobile';
import api from '@/lib/api';

interface DayData {
  date: string;
  rate: number;
}

interface PlanRank {
  name: string;
  rate: number;
  color: string;
}

interface Statistics {
  today_completed: number;
  today_total: number;
  streak_days: number;
  weekly_data: DayData[];
  monthly_data: DayData[];
  plan_ranks: PlanRank[];
}

const RANK_COLORS = ['#52c41a', '#1890ff', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#faad14'];

export default function StatisticsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Statistics | null>(null);
  const [timeRange, setTimeRange] = useState<'week' | 'month'>('week');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res: any = await api.get('/api/health-plan/statistics');
        const raw = res.data || res;
        const weeklyData = (raw.weekly_data || []).map((d: any) => ({
          date: d.date,
          rate: d.count || 0,
        }));
        setStats({
          today_completed: raw.today_completed || 0,
          today_total: raw.today_total || 0,
          streak_days: raw.consecutive_days || 0,
          weekly_data: weeklyData,
          monthly_data: raw.monthly_data || [],
          plan_ranks: raw.plan_ranks || [],
        });
      } catch {
        setStats({
          today_completed: 0,
          today_total: 0,
          streak_days: 0,
          weekly_data: [],
          monthly_data: [],
          plan_ranks: [],
        });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>打卡统计</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!stats) return null;

  const todayRate = stats.today_total > 0
    ? Math.round((stats.today_completed / stats.today_total) * 100)
    : 0;

  const chartData = timeRange === 'week' ? stats.weekly_data : stats.monthly_data;
  const maxRate = chartData.length > 0 ? Math.max(...chartData.map((d) => d.rate), 1) : 100;

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>打卡统计</NavBar>

      <div className="px-4 py-5" style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
        <div className="flex items-center justify-around text-white">
          <div className="text-center">
            <div className="relative w-20 h-20 mx-auto mb-2">
              <svg viewBox="0 0 100 100" className="w-full h-full" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="8" />
                <circle
                  cx="50" cy="50" r="42"
                  fill="none" stroke="#fff" strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${(todayRate / 100) * 264} 264`}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold">{todayRate}%</span>
              </div>
            </div>
            <div className="text-xs opacity-80">今日完成</div>
            <div className="text-sm font-medium">{stats.today_completed}/{stats.today_total}</div>
          </div>
          <div className="text-center">
            <div className="w-20 h-20 mx-auto mb-2 flex items-center justify-center">
              <div>
                <div className="text-3xl font-bold">{stats.streak_days}</div>
                <div className="text-xs opacity-80">天</div>
              </div>
            </div>
            <div className="text-xs opacity-80">连续打卡</div>
            <div className="text-sm font-medium">🔥 继续加油</div>
          </div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex items-center justify-between mb-4">
            <div className="section-title mb-0">完成率趋势</div>
            <div className="flex gap-1">
              {(['week', 'month'] as const).map((r) => (
                <div
                  key={r}
                  onClick={() => setTimeRange(r)}
                  className="px-3 py-1 rounded-full text-xs cursor-pointer"
                  style={{
                    background: timeRange === r ? '#52c41a15' : '#f5f5f5',
                    color: timeRange === r ? '#52c41a' : '#999',
                    fontWeight: timeRange === r ? 600 : 400,
                  }}
                >
                  {r === 'week' ? '周' : '月'}
                </div>
              ))}
            </div>
          </div>

          {chartData.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-8">暂无数据</div>
          ) : (
            <div>
              <div className="flex items-end gap-1" style={{ height: 120 }}>
                {chartData.map((d, i) => {
                  const h = maxRate > 0 ? (d.rate / maxRate) * 100 : 0;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center">
                      <div className="text-xs text-gray-400 mb-1">{d.rate}%</div>
                      <div
                        className="w-full rounded-t-md"
                        style={{
                          height: `${Math.max(h, 2)}%`,
                          background: d.rate >= 80
                            ? 'linear-gradient(180deg, #52c41a, #73d13d)'
                            : d.rate >= 50
                            ? 'linear-gradient(180deg, #faad14, #ffc53d)'
                            : 'linear-gradient(180deg, #ff7a45, #ffa39e)',
                          minHeight: 4,
                          transition: 'height 0.3s ease',
                        }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-1 mt-1">
                {chartData.map((d, i) => (
                  <div key={i} className="flex-1 text-center text-xs text-gray-400" style={{ fontSize: 10 }}>
                    {timeRange === 'week'
                      ? d.date.slice(-2)
                      : (i % 5 === 0 || i === chartData.length - 1) ? d.date.slice(-2) : ''
                    }
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card style={{ borderRadius: 12 }}>
          <div className="section-title">各计划完成率</div>
          {(!stats.plan_ranks || stats.plan_ranks.length === 0) ? (
            <div className="text-center text-gray-400 text-sm py-4">暂无数据</div>
          ) : (
            stats.plan_ranks.map((plan, idx) => (
              <div key={idx} className="mb-4 last:mb-0">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center">
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white mr-2"
                      style={{ background: RANK_COLORS[idx % RANK_COLORS.length] }}
                    >
                      {idx + 1}
                    </span>
                    <span className="text-sm">{plan.name}</span>
                  </div>
                  <span className="text-sm font-medium" style={{ color: RANK_COLORS[idx % RANK_COLORS.length] }}>
                    {plan.rate}%
                  </span>
                </div>
                <ProgressBar
                  percent={plan.rate}
                  style={{
                    '--track-width': '6px',
                    '--fill-color': RANK_COLORS[idx % RANK_COLORS.length],
                  }}
                />
              </div>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}
