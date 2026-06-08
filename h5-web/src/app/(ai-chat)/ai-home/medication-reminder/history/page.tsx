'use client';

/**
 * [PRD-MED-HISTORY-V1] 用药提醒历史打卡记录页面
 *
 * 路由：/ai-home/medication-reminder/history
 *
 * 功能：
 *  - 月份切换 + 日历网格（状态点：绿=全完成/黄=部分/红=漏打/灰=无计划）
 *  - 选中日期打卡记录列表（4种卡片视觉状态）
 *  - 补打卡确认弹窗
 *  - 默认选中昨天
 *  - 老年友好设计（大字体、大按钮、高对比度）
 */
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import GreenNavBar, { PRIMARY_GREEN } from '@/components/GreenNavBar';

/* ───── 颜色常量 ───── */
const GREEN = '#22c55e';
const ORANGE = '#FF8A3D';
const RED = '#EF4444';
const BLUE = '#4A9EE0';
const GRAY = '#94A3B8';
const TEXT = '#111827';
const SUB = '#6B7280';

const WEEKDAY_CN = ['日', '一', '二', '三', '四', '五', '六'];

/* ───── 类型 ───── */
type DayStatus = 'fully_done' | 'partial' | 'missed' | 'no_plan';
type RecordStatus = 'done' | 'supplement' | 'missed' | 'expired' | 'not_yet';

interface CalendarDay {
  date: string;
  status: DayStatus;
}

interface RecordItem {
  plan_id: number;
  drug_name: string;
  dosage: string;
  scheduled_time: string;
  status: RecordStatus;
  check_in_time: string | null;
  check_in_type: string | null;
  can_supplement: boolean;
}
/* ───── 工具函数 ───── */

function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay();
}

function dayStatusColor(status: DayStatus): string {
  switch (status) {
    case 'fully_done': return GREEN;
    case 'partial': return ORANGE;
    case 'missed': return RED;
    default: return '#E5E7EB';
  }
}

function dayStatusText(status: DayStatus): string {
  switch (status) {
    case 'fully_done': return '✓';
    case 'partial': return '△';
    case 'missed': return '✗';
    default: return '';
  }
}

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const w = WEEKDAY_CN[d.getDay()];
  return `${m}月${day}日 周${w}`;
}
export default function MedicationHistoryPage() {
  const router = useRouter();
  const today = new Date();

  // 默认选中昨天
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const [selectedDate, setSelectedDate] = useState<string>(formatDate(yesterday));

  // 当前展示的月份
  const [viewYear, setViewYear] = useState<number>(yesterday.getFullYear());
  const [viewMonth, setViewMonth] = useState<number>(yesterday.getMonth() + 1);

  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(false);

  // 补打卡弹窗
  const [supplementTarget, setSupplementTarget] = useState<RecordItem | null>(null);
  const [supplementLoading, setSupplementLoading] = useState(false);

  /* ───── 加载日历 ───── */
  const loadCalendar = useCallback(async (year: number, month: number) => {
    try {
      const res: any = await api.get('/api/medication/calendar', {
        params: { year, month },
      });
      const data = res.data || res;
      setCalendarDays(data.days || []);
    } catch {
      // 静默失败
    }
  }, []);

  /* ───── 加载选中日期的记录 ───── */
  const loadRecords = useCallback(async (dateStr: string) => {
    setLoadingRecords(true);
    try {
      const res: any = await api.get('/api/medication/records', {
        params: { date: dateStr },
      });
      const data = res.data || res;
      setRecords(data.records || []);
    } catch {
      setRecords([]);
    } finally {
      setLoadingRecords(false);
    }
  }, []);

  useEffect(() => {
    loadCalendar(viewYear, viewMonth);
  }, [viewYear, viewMonth, loadCalendar]);

  useEffect(() => {
    loadRecords(selectedDate);
  }, [selectedDate, loadRecords]);
  /* ───── 月份切换 ───── */
  const goPrevMonth = () => {
    if (viewMonth === 1) {
      setViewYear(viewYear - 1);
      setViewMonth(12);
    } else {
      setViewMonth(viewMonth - 1);
    }
  };

  const goNextMonth = () => {
    if (viewMonth === 12) {
      setViewYear(viewYear + 1);
      setViewMonth(1);
    } else {
      setViewMonth(viewMonth + 1);
    }
  };

  /* ───── 补打卡 ───── */
  const handleSupplement = async () => {
    if (!supplementTarget) return;
    setSupplementLoading(true);
    try {
      await api.post('/api/medication/supplement', {
        plan_id: supplementTarget.plan_id,
        check_in_date: selectedDate,
        scheduled_time: supplementTarget.scheduled_time,
      });
      showToast('补打卡成功');
      setSupplementTarget(null);
      loadRecords(selectedDate);
      loadCalendar(viewYear, viewMonth);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '补打卡失败', 'fail');
    } finally {
      setSupplementLoading(false);
    }
  };

  /* ───── 日历网格渲染 ───── */
  const daysInMonth = getDaysInMonth(viewYear, viewMonth);
  const firstDow = getFirstDayOfWeek(viewYear, viewMonth);
  const cells: (CalendarDay | null)[] = [];

  for (let i = 0; i < firstDow; i++) {
    cells.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${viewYear}-${String(viewMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayData = calendarDays.find((cd) => cd.date === dateStr);
    cells.push(dayData || { date: dateStr, status: 'no_plan' as DayStatus });
  }

  const isToday = (dateStr: string) => dateStr === formatDate(today);
  const isSelected = (dateStr: string) => dateStr === selectedDate;
  const isFuture = (dateStr: string) => dateStr > formatDate(today);
  return (
    <div style={{ minHeight: '100vh', background: '#F4F6F9', paddingBottom: 40 }}>
      {/* 顶栏 */}
      <div style={{ position: 'sticky', top: 0, zIndex: 60, background: PRIMARY_GREEN }}>
        <GreenNavBar back={() => router.push('/ai-home/medication-reminder')}>
          历史打卡
        </GreenNavBar>
      </div>

      {/* 黄色提示条 */}
      <div
        style={{
          margin: '12px 16px',
          padding: '10px 14px',
          borderRadius: 10,
          background: '#FFFDE7',
          border: '1px solid #FBC02D',
          fontSize: 13,
          color: '#795548',
          lineHeight: 1.6,
        }}
      >
        💡 漏打卡可在 2 天内补打卡，超过 2 天将无法补打
      </div>

      {/* 月份切换 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, margin: '0 16px 12px' }}>
        <button
          onClick={goPrevMonth}
          style={{
            background: 'none', border: 'none', fontSize: 22, color: TEXT,
            cursor: 'pointer', padding: '4px 12px',
          }}
        >
          ‹
        </button>
        <span style={{ fontSize: 17, fontWeight: 700, color: TEXT }}>
          {viewYear} 年 {viewMonth} 月
        </span>
        <button
          onClick={goNextMonth}
          style={{
            background: 'none', border: 'none', fontSize: 22, color: TEXT,
            cursor: 'pointer', padding: '4px 12px',
          }}
        >
          ›
        </button>
      </div>

      {/* 日历网格 */}
      <div style={{ margin: '0 16px', background: '#fff', borderRadius: 14, padding: 12 }}>
        {/* 星期头 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', marginBottom: 8 }}>
          {['日', '一', '二', '三', '四', '五', '六'].map((w) => (
            <div
              key={w}
              style={{
                textAlign: 'center',
                fontSize: 12,
                color: SUB,
                fontWeight: 600,
                padding: '4px 0',
              }}
            >
              {w}
            </div>
          ))}
        </div>
        {/* 日期格子 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
          {cells.map((cell, idx) => {
            if (!cell) {
              return <div key={`empty-${idx}`} />;
            }
            const sel = isSelected(cell.date);
            const fut = isFuture(cell.date);
            const tdy = isToday(cell.date);
            const color = dayStatusColor(cell.status);
            return (
              <div
                key={cell.date}
                onClick={() => !fut && setSelectedDate(cell.date)}
                style={{
                  textAlign: 'center',
                  padding: '6px 0',
                  borderRadius: 8,
                  cursor: fut ? 'default' : 'pointer',
                  background: sel ? BLUE : tdy ? '#E8F4FD' : 'transparent',
                  opacity: fut ? 0.4 : 1,
                }}
              >
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: tdy || sel ? 700 : 400,
                    color: sel ? '#fff' : tdy ? BLUE : TEXT,
                  }}
                >
                  {parseInt(cell.date.slice(-2), 10)}
                </div>
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 10,
                    margin: '2px auto 0',
                    background: cell.status === 'no_plan' ? 'transparent' : color,
                    color: '#fff',
                    fontSize: 11,
                    fontWeight: 700,
                    lineHeight: '20px',
                  }}
                >
                  {dayStatusText(cell.status)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {/* 选中日期标题 + 记录列表 */}
      <div style={{ margin: '16px 16px 0' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: TEXT, marginBottom: 10 }}>
          📅 {formatDisplayDate(selectedDate)}
        </div>

        {loadingRecords ? (
          <div style={{ textAlign: 'center', padding: 30, color: SUB, fontSize: 14 }}>加载中…</div>
        ) : records.length === 0 ? (
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 32,
              textAlign: 'center',
              color: SUB,
              fontSize: 14,
            }}
          >
            当天无用药记录
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {records.map((rec, idx) => (
              <RecordCard
                key={`${rec.plan_id}-${rec.scheduled_time}-${idx}`}
                record={rec}
                onSupplement={() => setSupplementTarget(rec)}
              />
            ))}
          </div>
        )}
      </div>

      {/* 补打卡确认弹窗 */}
      {supplementTarget && (
        <Dialog
          visible={!!supplementTarget}
          title="确认补打卡"
          content={
            <div style={{ fontSize: 14, color: TEXT, lineHeight: 1.8 }}>
              <div>药品：{supplementTarget.drug_name}</div>
              <div>日期：{formatDisplayDate(selectedDate)}</div>
              <div>时间：{supplementTarget.scheduled_time}</div>
              <div style={{ marginTop: 8, color: ORANGE }}>
                确认对该时间点进行补打卡？
              </div>
            </div>
          }
          closeOnMaskClick
          onClose={() => setSupplementTarget(null)}
          actions={[
            {
              key: 'cancel',
              text: '取消',
              onClick: () => setSupplementTarget(null),
            },
            {
              key: 'confirm',
              text: supplementLoading ? '提交中…' : '确认补打卡',
              bold: true,
              danger: false,
              style: { background: ORANGE, color: '#fff', border: 'none' },
              onClick: handleSupplement,
            },
          ]}
        />
      )}
    </div>
  );
}
/* ───── 打卡记录卡片（4种视觉状态） ───── */

function RecordCard({
  record,
  onSupplement,
}: {
  record: RecordItem;
  onSupplement: () => void;
}) {
  const { status, drug_name, dosage, scheduled_time, check_in_time, check_in_type } = record;

  const barColor =
    status === 'done'
      ? GREEN
      : status === 'supplement'
      ? ORANGE
      : status === 'missed'
      ? RED
      : status === 'expired'
      ? GRAY
      : GRAY;

  const bgColor = status === 'supplement' ? '#FFFDE7' : '#fff';

  const badgeText =
    status === 'done'
      ? '已打卡'
      : status === 'supplement'
      ? '已补'
      : status === 'missed' || status === 'expired'
      ? '未打卡'
      : '未到时间';

  const badgeBg =
    status === 'done'
      ? '#DCFCE7'
      : status === 'supplement'
      ? '#FFF3E0'
      : status === 'missed' || status === 'expired'
      ? '#FEE2E2'
      : '#F3F4F6';

  const badgeColor =
    status === 'done'
      ? GREEN
      : status === 'supplement'
      ? ORANGE
      : status === 'missed' || status === 'expired'
      ? RED
      : SUB;

  const timeLabel =
    status === 'supplement' && check_in_time
      ? `补打卡 ${formatCheckInTime(check_in_time)}`
      : status === 'done' && check_in_time
      ? `打卡时间 ${formatCheckInTime(check_in_time)}`
      : '';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'stretch',
        background: bgColor,
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}
    >
      {/* 左侧色条 */}
      <div style={{ width: 4, minHeight: '100%', background: barColor, flexShrink: 0 }} />

      {/* 内容区 */}
      <div style={{ flex: 1, padding: '14px 14px 14px 12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: TEXT }}>{drug_name}</div>
            <div style={{ fontSize: 12, color: SUB, marginTop: 3 }}>
              {dosage && <span>{dosage} · </span>}
              {scheduled_time}
            </div>
          </div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: badgeColor,
              background: badgeBg,
              padding: '3px 10px',
              borderRadius: 10,
              whiteSpace: 'nowrap',
            }}
          >
            {badgeText}
          </span>
        </div>

        {timeLabel && (
          <div style={{ fontSize: 11, color: GRAY, marginTop: 6 }}>{timeLabel}</div>
        )}

        {/* 操作按钮 */}
        <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
          {status === 'missed' && record.can_supplement && (
            <button
              onClick={onSupplement}
              style={{
                padding: '7px 16px',
                background: ORANGE,
                color: '#fff',
                border: 'none',
                borderRadius: 18,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              补打卡
            </button>
          )}
          {status === 'expired' && (
            <button
              disabled
              style={{
                padding: '7px 16px',
                background: '#E5E7EB',
                color: GRAY,
                border: 'none',
                borderRadius: 18,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'not-allowed',
              }}
            >
              不可补
            </button>
          )}
          {(status === 'done' || status === 'supplement') && (
            <span
              style={{
                padding: '7px 16px',
                color: GREEN,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              ✓ 完成
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function formatCheckInTime(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${hh}:${mm}`;
  } catch {
    return isoStr;
  }
}
