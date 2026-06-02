'use client';

/**
 * [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 打卡成果页
 *
 * 三个核心数字：连续天数、累计打卡、完成率
 * 月历视图：打过卡的日子高亮 + 支持点击补卡（最近 3 天）
 * 统计图表：各计划完成率的条形图
 */

import { useState, useEffect, useCallback } from 'react';
import { Card, SpinLoading, ProgressBar, Dialog, Toast } from 'antd-mobile';
import { LeftOutline, RightOutline } from 'antd-mobile-icons';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';

interface Plan {
  id: number;
  name: string;
  expected: number;
  done: number;
  completion_rate: number;
}

interface Summary {
  streak_days: number;
  total_checkins: number;
  overall_completion_rate: number;
  plans: Plan[];
}

interface CheckinItem {
  id: number;
  name: string;
}

const RANK_COLORS = ['#6366F1', '#8B5CF6', '#A855F7', '#EC4899', '#0EA5E9', '#10B981', '#F59E0B'];

function pad(n: number) {
  return String(n).padStart(2, '0');
}

export default function ResultPage() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [items, setItems] = useState<CheckinItem[]>([]);
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [calendarDays, setCalendarDays] = useState<{ [d: string]: number }>({});
  const [calendarLoading, setCalendarLoading] = useState(false);

  const fetchSummary = useCallback(async () => {
    try {
      const [sumRes, listRes] = await Promise.allSettled([
        api.get('/api/health-plan/checkin-stats-summary'),
        api.get('/api/health-plan/checkin-items'),
      ]);
      const sumData: any =
        sumRes.status === 'fulfilled' ? ((sumRes.value as any).data || sumRes.value) : {};
      const listData: any =
        listRes.status === 'fulfilled' ? ((listRes.value as any).data || listRes.value) : {};
      setSummary({
        streak_days: sumData.streak_days ?? 0,
        total_checkins: sumData.total_checkins ?? 0,
        overall_completion_rate: sumData.overall_completion_rate ?? 0,
        plans: sumData.plans || [],
      });
      setItems((listData.items || []).map((i: any) => ({ id: i.id, name: i.name })));
    } catch {
      showToast('加载失败', 'fail');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCalendar = useCallback(async (y: number, m: number) => {
    setCalendarLoading(true);
    try {
      const res: any = await api.get(`/api/health-plan/checkin-calendar?year=${y}&month=${m}`);
      const data = res.data || res;
      const map: { [d: string]: number } = {};
      (data.days || []).forEach((it: any) => {
        map[it.date] = it.count || 0;
      });
      setCalendarDays(map);
    } catch {
      setCalendarDays({});
    } finally {
      setCalendarLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchCalendar(year, month);
  }, [year, month, fetchCalendar]);

  const changeMonth = (delta: number) => {
    let y = year;
    let m = month + delta;
    if (m < 1) {
      m = 12;
      y -= 1;
    }
    if (m > 12) {
      m = 1;
      y += 1;
    }
    // 不允许查看未来超过本月
    const nowY = new Date().getFullYear();
    const nowM = new Date().getMonth() + 1;
    if (y > nowY || (y === nowY && m > nowM)) return;
    setYear(y);
    setMonth(m);
  };

  const handleDayClick = async (dateStr: string) => {
    // 仅允许补打最近 3 天（不含今天）且无打卡记录
    const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    if (dateStr === todayStr) {
      Toast.show({ content: '请到主页执行今日打卡' });
      return;
    }
    if (calendarDays[dateStr]) {
      Toast.show({ content: `这天已有 ${calendarDays[dateStr]} 次打卡` });
      return;
    }
    if (dateStr > todayStr) return;

    const d1 = new Date(dateStr);
    const diffDays = Math.floor((today.getTime() - d1.getTime()) / 86400000);
    if (diffDays < 1 || diffDays > 3) {
      Toast.show({ content: '只能补最近 3 天内（不含今天）的卡' });
      return;
    }
    if (!items || items.length === 0) {
      Toast.show({ content: '暂无可补打的计划' });
      return;
    }

    // 弹出选择计划
    const target = await new Promise<CheckinItem | null>((resolve) => {
      Dialog.show({
        title: `补打 ${dateStr}`,
        content: (
          <div className="py-2">
            <div className="text-sm text-gray-500 mb-3">选择要补打的计划：</div>
            {items.map((it) => (
              <div
                key={it.id}
                className="py-2 border-b border-gray-100 text-sm cursor-pointer"
                onClick={() => {
                  resolve(it);
                  Dialog.clear();
                }}
              >
                {it.name}
              </div>
            ))}
          </div>
        ),
        closeOnAction: true,
        actions: [{ key: 'cancel', text: '取消' }],
        onAction: () => resolve(null),
      });
    });
    if (!target) return;
    try {
      await api.post(`/api/health-plan/checkin-items/${target.id}/makeup`, { date: dateStr });
      showToast('补卡成功', 'success');
      fetchCalendar(year, month);
      fetchSummary();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || '补卡失败';
      showToast(String(msg), 'fail');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>打卡成果</GreenNavBar>
        <div
          className="flex items-center justify-center"
          style={{ height: 'calc(100vh - 45px)' }}
        >
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  // 计算月历
  const firstDate = new Date(year, month - 1, 1);
  const firstDay = firstDate.getDay(); // 0 周日 ~ 6 周六
  const daysInMonth = new Date(year, month, 0).getDate();
  const cells: ({ dateStr: string; day: number } | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ dateStr: `${year}-${pad(month)}-${pad(d)}`, day: d });
  }

  const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

  return (
    <div className="min-h-screen bg-gray-50 pb-10" data-testid="health-plan-result-v1">
      <GreenNavBar>打卡成果</GreenNavBar>

      {/* 三个核心数字 */}
      <div
        className="px-4 py-5"
        style={{ background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)' }}
      >
        <div className="flex items-center justify-around text-white text-center">
          <div>
            <div className="text-3xl font-bold">{summary?.streak_days ?? 0}</div>
            <div className="text-xs opacity-80 mt-1">连续天数</div>
          </div>
          <div style={{ width: 1, height: 36, background: 'rgba(255,255,255,0.25)' }} />
          <div>
            <div className="text-3xl font-bold">{summary?.total_checkins ?? 0}</div>
            <div className="text-xs opacity-80 mt-1">累计打卡</div>
          </div>
          <div style={{ width: 1, height: 36, background: 'rgba(255,255,255,0.25)' }} />
          <div>
            <div className="text-3xl font-bold">
              {Math.round(summary?.overall_completion_rate ?? 0)}%
            </div>
            <div className="text-xs opacity-80 mt-1">完成率</div>
          </div>
        </div>
      </div>

      {/* 月历视图 */}
      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex items-center justify-between mb-3">
            <LeftOutline
              fontSize={18}
              className="cursor-pointer"
              color="#6366F1"
              onClick={() => changeMonth(-1)}
            />
            <div className="text-base font-bold">
              {year} 年 {month} 月
            </div>
            <RightOutline
              fontSize={18}
              className="cursor-pointer"
              color="#6366F1"
              onClick={() => changeMonth(1)}
            />
          </div>

          <div className="grid grid-cols-7 text-center text-xs text-gray-400 mb-2">
            {['日', '一', '二', '三', '四', '五', '六'].map((w) => (
              <div key={w}>{w}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {cells.map((c, i) => {
              if (!c) return <div key={i} />;
              const cnt = calendarDays[c.dateStr] || 0;
              const isToday = c.dateStr === todayStr;
              const diffDays = Math.floor(
                (today.getTime() - new Date(c.dateStr).getTime()) / 86400000,
              );
              const canMakeup = !cnt && diffDays >= 1 && diffDays <= 3;
              return (
                <div
                  key={i}
                  onClick={() => handleDayClick(c.dateStr)}
                  className="aspect-square flex items-center justify-center rounded-lg text-sm cursor-pointer"
                  style={{
                    background: cnt
                      ? 'linear-gradient(135deg, #6366F1, #8B5CF6)'
                      : isToday
                      ? '#EEF2FF'
                      : canMakeup
                      ? '#FFF7ED'
                      : 'transparent',
                    color: cnt ? '#fff' : isToday ? '#6366F1' : '#1F2937',
                    fontWeight: cnt || isToday ? 600 : 400,
                    border: canMakeup ? '1px dashed #F59E0B' : 'none',
                  }}
                  data-testid={`cal-${c.dateStr}`}
                >
                  {c.day}
                </div>
              );
            })}
          </div>
          {calendarLoading && (
            <div className="text-center text-xs text-gray-400 mt-2">加载中...</div>
          )}
          <div className="text-xs text-gray-400 mt-3 flex flex-wrap gap-3">
            <span>
              <span
                className="inline-block w-3 h-3 rounded mr-1 align-middle"
                style={{ background: 'linear-gradient(135deg, #6366F1, #8B5CF6)' }}
              />
              已打卡
            </span>
            <span>
              <span
                className="inline-block w-3 h-3 rounded mr-1 align-middle"
                style={{ background: '#FFF7ED', border: '1px dashed #F59E0B' }}
              />
              可补卡（最近3天）
            </span>
          </div>
        </Card>

        {/* 各计划完成率 */}
        <Card style={{ borderRadius: 12 }}>
          <div className="text-base font-bold mb-3">各计划完成率</div>
          {(summary?.plans || []).length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-4">暂无数据</div>
          ) : (
            (summary?.plans || []).map((p, idx) => (
              <div key={p.id} className="mb-4 last:mb-0">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center">
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white mr-2"
                      style={{ background: RANK_COLORS[idx % RANK_COLORS.length] }}
                    >
                      {idx + 1}
                    </span>
                    <span className="text-sm">{p.name}</span>
                  </div>
                  <span
                    className="text-sm font-medium"
                    style={{ color: RANK_COLORS[idx % RANK_COLORS.length] }}
                  >
                    {Math.round(p.completion_rate)}%
                  </span>
                </div>
                <ProgressBar
                  percent={Math.min(100, p.completion_rate)}
                  style={{
                    '--track-width': '6px',
                    '--fill-color': RANK_COLORS[idx % RANK_COLORS.length],
                  }}
                />
                <div className="text-xs text-gray-400 mt-1">
                  已打 {p.done} / 应打 {p.expected}
                </div>
              </div>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}
