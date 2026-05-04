'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { NavBar, Toast, Tag, Empty, DotLoading } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId } from '../mobile-lib';
import DailyOrdersDrawer from './DailyOrdersDrawer';

interface DaySummary {
  date: string;
  count: number;
  morning_count: number;
  afternoon_count: number;
  evening_count: number;
}

interface DailyAppointment {
  id: number;
  order_id: number;
  time_slot: string;
  customer_name: string;
  product_name: string;
  status: string;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

const STATUS_CONFIG: Record<string, { text: string; color: string; bg: string }> = {
  pending: { text: '待确认', color: '#faad14', bg: '#fffbe6' },
  confirmed: { text: '已确认', color: '#1677ff', bg: '#e6f4ff' },
  completed: { text: '已完成', color: '#52c41a', bg: '#f6ffed' },
  cancelled: { text: '已取消', color: '#8c8c8c', bg: '#f5f5f5' },
};

function getDensityColor(count: number): string {
  if (count === 0) return 'transparent';
  if (count <= 2) return '#52c41a';
  if (count <= 5) return '#fa8c16';
  return '#ff4d4f';
}

function getMonthDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const days: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) days.push(null);
  for (let i = 1; i <= daysInMonth; i++) days.push(i);
  return days;
}

export default function CalendarMobilePage() {
  const router = useRouter();
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [month, setMonth] = useState(() => new Date().getMonth());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [monthlySummary, setMonthlySummary] = useState<Record<string, DaySummary>>({});
  const [dailyList, setDailyList] = useState<DailyAppointment[]>([]);
  const [loadingMonthly, setLoadingMonthly] = useState(false);
  const [loadingDaily, setLoadingDaily] = useState(false);

  // PRD「当日订单弹窗」v1.0：H5 端底部抽屉
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerDate, setDrawerDate] = useState<string | null>(null);

  const monthStr = useMemo(() => {
    return `${year}-${String(month + 1).padStart(2, '0')}`;
  }, [year, month]);

  const days = useMemo(() => getMonthDays(year, month), [year, month]);

  const loadMonthly = useCallback(async () => {
    setLoadingMonthly(true);
    try {
      const params: any = { month: monthStr };
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      const res: any = await api.get('/api/merchant/calendar/monthly', { params });
      const map: Record<string, DaySummary> = {};
      (res?.days || res || []).forEach((d: DaySummary) => {
        map[d.date] = d;
      });
      setMonthlySummary(map);
    } catch {
      setMonthlySummary({});
    } finally {
      setLoadingMonthly(false);
    }
  }, [monthStr]);

  const loadDaily = useCallback(async (date: string) => {
    setLoadingDaily(true);
    try {
      const params: any = { date };
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      const res: any = await api.get('/api/merchant/calendar/daily', { params });
      setDailyList(res?.appointments || res?.items || res || []);
    } catch {
      setDailyList([]);
    } finally {
      setLoadingDaily(false);
    }
  }, []);

  useEffect(() => {
    loadMonthly();
  }, [loadMonthly]);

  useEffect(() => {
    if (selectedDate) loadDaily(selectedDate);
  }, [selectedDate, loadDaily]);

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
    setSelectedDate(null);
  };

  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
    setSelectedDate(null);
  };

  const handleDayClick = (day: number) => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    setSelectedDate(dateStr);
    // PRD「当日订单弹窗」v1.0 F-11：仅当当日有订单时弹出底部抽屉
    const summary = monthlySummary[dateStr];
    if (summary && summary.count > 0) {
      setDrawerDate(dateStr);
      setDrawerOpen(true);
      try {
        // eslint-disable-next-line no-console
        console.info('[track] calendar_daily_popup_open', { date: dateStr, order_count: summary.count, terminal: 'h5' });
      } catch {}
    }
  };

  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar onBack={() => router.back()}>预约日历</NavBar>

      {/* Month navigation */}
      <div style={{ background: '#fff', padding: '12px 16px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <span onClick={prevMonth} style={{ fontSize: 20, padding: '4px 12px', cursor: 'pointer', color: '#52c41a' }}>‹</span>
          <span style={{ fontSize: 16, fontWeight: 600 }}>{year}年{month + 1}月</span>
          <span onClick={nextMonth} style={{ fontSize: 20, padding: '4px 12px', cursor: 'pointer', color: '#52c41a' }}>›</span>
        </div>

        {/* Weekday headers */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', textAlign: 'center', marginBottom: 4 }}>
          {WEEKDAYS.map(w => (
            <div key={w} style={{ fontSize: 12, color: '#999', padding: '4px 0' }}>{w}</div>
          ))}
        </div>

        {/* Calendar grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, paddingBottom: 12 }}>
          {days.map((day, idx) => {
            if (day === null) return <div key={`e-${idx}`} />;
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const summary = monthlySummary[dateStr];
            const isToday = dateStr === todayStr;
            const isSelected = dateStr === selectedDate;

            return (
              <div
                key={dateStr}
                onClick={() => handleDayClick(day)}
                style={{
                  textAlign: 'center',
                  padding: '6px 2px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: isSelected ? '#52c41a' : isToday ? '#f6ffed' : 'transparent',
                  border: isToday && !isSelected ? '1px solid #52c41a' : '1px solid transparent',
                }}
              >
                <div style={{
                  fontSize: 14,
                  fontWeight: isToday ? 600 : 400,
                  color: isSelected ? '#fff' : '#333',
                }}>
                  {day}
                </div>
                {summary && summary.count > 0 && (
                  <>
                    <div style={{
                      fontSize: 10,
                      color: isSelected ? 'rgba(255,255,255,0.9)' : '#fa541c',
                      marginTop: 1,
                    }}>
                      {summary.count}单
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 2, marginTop: 2 }}>
                      {[summary.morning_count, summary.afternoon_count, summary.evening_count].map((cnt, i) => (
                        <div
                          key={i}
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: 2,
                            background: getDensityColor(cnt),
                          }}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Density legend */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, paddingBottom: 12, fontSize: 11, color: '#999' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: '#52c41a', display: 'inline-block' }} />低
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: '#fa8c16', display: 'inline-block' }} />中
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: '#ff4d4f', display: 'inline-block' }} />高
          </span>
        </div>
      </div>

      {/* Daily view */}
      {selectedDate && (
        <div style={{ padding: 12 }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10, color: '#333' }}>
            {selectedDate} 预约列表
          </div>

          {loadingDaily ? (
            <div style={{ textAlign: 'center', padding: 32, color: '#999' }}>
              <DotLoading color="primary" />
            </div>
          ) : dailyList.length === 0 ? (
            <Empty description="当天无预约" style={{ padding: 32 }} />
          ) : (
            dailyList.map((item) => {
              const st = STATUS_CONFIG[item.status] || { text: item.status, color: '#999', bg: '#f5f5f5' };
              return (
                <div
                  key={item.id || item.order_id}
                  onClick={() => router.push(`/merchant/m/orders/${item.order_id}`)}
                  style={{
                    background: '#fff',
                    borderRadius: 10,
                    padding: '12px 14px',
                    marginBottom: 10,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 8 }}>
                      {item.product_name || '—'}
                    </div>
                    <span style={{
                      fontSize: 11,
                      padding: '2px 8px',
                      borderRadius: 10,
                      background: st.bg,
                      color: st.color,
                    }}>
                      {st.text}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, color: '#666' }}>
                    <span>👤 {item.customer_name || '—'}</span>
                    <span>🕐 {item.time_slot || '—'}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* PRD「当日订单弹窗」v1.0：H5 端底部抽屉 */}
      <DailyOrdersDrawer
        open={drawerOpen}
        date={drawerDate}
        storeId={getCurrentStoreId() ?? null}
        onClose={() => setDrawerOpen(false)}
        onViewFullOrder={(orderId) => {
          setDrawerOpen(false);
          router.push(`/merchant/m/orders/${orderId}`);
        }}
      />
    </div>
  );
}
