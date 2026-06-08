'use client';

/**
 * [PRD-MED-HISTORY-V1] 用药提醒历史打卡记录页面
 *
 * 路由：/ai-home/medication-reminder/history
 *
 * 功能：
 *  - 月份切换 + 日历网格（状态小圆点：绿=全完成/橙=部分/红=漏打/无=无计划）
 *  - 选中日期打卡记录列表（4种卡片视觉状态：已打卡/已补/未打卡-可补/未打卡-不可补）
 *  - 补打卡确认弹窗（仅限近2天内漏打卡可补）
 *  - 默认选中昨天
 *  - 老年友好设计（大字体、大按钮、高对比度）
 *  - 卡片布局与主页 TimelineRow 风格一致
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import GreenNavBar, { PRIMARY_GREEN } from '@/components/GreenNavBar';
import Calendar, { type CalendarDay } from '../components/Calendar';

/* ───── 颜色常量（与主页 TimelineRow 一致） ───── */
const GREEN = '#22c55e';
const ORANGE = '#FF8A3D';
const RED = '#EF4444';
const BLUE = '#4A9EE0';
const GRAY = '#94A3B8';
const TEXT = '#111827';
const SUB = '#6B7280';

const WEEKDAY_CN = ['日', '一', '二', '三', '四', '五', '六'];

/* ───── 类型 ───── */
type RecordStatus = 'done' | 'supplement' | 'missed' | 'expired' | 'not_yet';

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

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const w = WEEKDAY_CN[d.getDay()];
  return `${m}月${day}日 周${w}`;
}

function getTimePeriod(scheduledTime: string): string {
  const hour = parseInt(scheduledTime.split(':')[0], 10);
  if (hour >= 6 && hour < 12) return '早上';
  if (hour >= 12 && hour < 14) return '中午';
  if (hour >= 14 && hour < 18) return '下午';
  return '晚上';
}

function formatCheckInTime(isoStr: string, isSupplement: boolean): string {
  try {
    const d = new Date(isoStr);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    if (isSupplement) {
      const MM = String(d.getMonth() + 1).padStart(2, '0');
      const DD = String(d.getDate()).padStart(2, '0');
      return `${MM}-${DD} ${hh}:${mm}`;
    }
    return `${hh}:${mm}`;
  } catch {
    return isoStr;
  }
}

function getDayStatusLabel(status: string): string {
  switch (status) {
    case 'fully_done': return '全部打卡';
    case 'partial': return '部分打卡';
    case 'missed': return '全部漏打';
    default: return '';
  }
}

/* ───── 页面主组件 ───── */

export default function MedicationHistoryPage() {
  const router = useRouter();
  const today = new Date();

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const [selectedDate, setSelectedDate] = useState<string>(formatDate(yesterday));

  const [viewYear, setViewYear] = useState<number>(yesterday.getFullYear());
  const [viewMonth, setViewMonth] = useState<number>(yesterday.getMonth() + 1);

  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(false);

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

  /* ───── 日期选择 ───── */
  const handleSelectDate = (dateStr: string) => {
    setSelectedDate(dateStr);
  };

  /* ───── 打开补打卡确认弹窗 ───── */
  const handleOpenSupplement = (record: RecordItem) => {
    setSupplementTarget(record);
  };

  /* ───── 确认补打卡 ───── */
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

  const todayStr = formatDate(today);
  const isToday = selectedDate === todayStr;

  const selectedDayData = calendarDays.find((d) => d.date === selectedDate);
  const dayStatusText = selectedDayData ? getDayStatusLabel(selectedDayData.status) : '';

  return (
    <div style={{ minHeight: '100vh', background: '#F4F6F9', paddingBottom: 40 }}>
      {/* 顶栏：天蓝色，与主页一致 */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 60,
          background: PRIMARY_GREEN,
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        <GreenNavBar back={() => router.push('/ai-home/medication-reminder')}>
          历史打卡记录
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
        ⚠ 补打卡仅限最近2天内的记录，超过2天将无法补打
      </div>

      {/* 日历组件 */}
      <Calendar
        year={viewYear}
        month={viewMonth}
        days={calendarDays}
        selectedDate={selectedDate}
        onSelectDate={handleSelectDate}
        onPrevMonth={goPrevMonth}
        onNextMonth={goNextMonth}
      />

      {/* 选中日期标题行 */}
      <div
        style={{
          margin: '16px 16px 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ fontSize: 18, fontWeight: 700, color: TEXT }}>
          📅 {formatDisplayDate(selectedDate)}
        </div>
        {dayStatusText && (
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color:
                selectedDayData?.status === 'fully_done'
                  ? GREEN
                  : selectedDayData?.status === 'partial'
                  ? ORANGE
                  : RED,
            }}
          >
            {dayStatusText}
          </span>
        )}
      </div>

      {/* 记录列表 */}
      <div style={{ margin: '12px 16px 0' }}>
        {loadingRecords ? (
          <div style={{ textAlign: 'center', padding: 30, color: SUB, fontSize: 14 }}>
            加载中…
          </div>
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
                isToday={isToday}
                onSupplement={() => handleOpenSupplement(rec)}
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

/* ───── 打卡记录卡片（4种视觉状态，布局与主页 TimelineRow 一致） ───── */

function RecordCard({
  record,
  isToday,
  onSupplement,
}: {
  record: RecordItem;
  isToday: boolean;
  onSupplement: () => void;
}) {
  const { status, drug_name, dosage, scheduled_time, check_in_time } = record;

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

  const timePeriod = getTimePeriod(scheduled_time);

  const isSupplement = status === 'supplement';
  const isDone = status === 'done';
  const isMissed = status === 'missed';
  const isExpired = status === 'expired';
  const isNotYet = status === 'not_yet';

  const checkInTimeDisplay =
    check_in_time && (isDone || isSupplement)
      ? isSupplement
        ? formatCheckInTime(check_in_time, true)
        : formatCheckInTime(check_in_time, false)
      : null;

  return (
    <div
      style={{
        display: 'flex',
        background: bgColor,
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}
    >
      {/* 左侧色条 — 贯穿整张卡片 */}
      <div
        style={{
          width: 4,
          background: barColor,
          flexShrink: 0,
          borderRadius: '12px 0 0 12px',
        }}
      />

      {/* 内容区：与主页 TimelineRow 一致的三栏布局 */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
          padding: 14,
        }}
      >
        {/* 左栏：时间 + 小圆点 */}
        <div style={{ width: 56, textAlign: 'center', flexShrink: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: TEXT }}>
            {scheduled_time}
          </div>
          <div
            style={{
              display: 'inline-block',
              marginTop: 4,
              width: 8,
              height: 8,
              borderRadius: 4,
              background: barColor,
            }}
          />
        </div>

        {/* 中栏：药品名 + 剂量·时段 + 补打卡时间 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: TEXT }}>
            {drug_name}
          </div>
          <div style={{ fontSize: 12, color: SUB, marginTop: 2 }}>
            {dosage && <span>{dosage} · </span>}
            {timePeriod}
          </div>

          {/* 补打卡时间（仅补打卡时显示，橙色） */}
          {isSupplement && checkInTimeDisplay && (
            <div style={{ fontSize: 11, color: ORANGE, marginTop: 4 }}>
              补打卡 {checkInTimeDisplay}
            </div>
          )}

          {/* 今天未打卡提示 */}
          {isNotYet && isToday && (
            <div style={{ fontSize: 11, color: SUB, marginTop: 4 }}>
              请在主页打卡
            </div>
          )}
        </div>

        {/* 右栏：状态标签 + 打卡时间 / 操作按钮 */}
        <div style={{ flexShrink: 0, textAlign: 'right' }}>
          {/* 状态标签 */}
          <span
            style={{
              display: 'inline-block',
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

          {/* 正常打卡时间（灰字，在标签下方） */}
          {isDone && checkInTimeDisplay && (
            <div style={{ fontSize: 11, color: GRAY, marginTop: 6 }}>
              {checkInTimeDisplay}
            </div>
          )}

          {/* 操作按钮区 */}
          <div style={{ marginTop: 8 }}>
            {/* 已打卡 / 已补 → 绿色完成标识 */}
            {(isDone || isSupplement) && (
              <span
                style={{
                  display: 'inline-block',
                  padding: '6px 12px',
                  color: GREEN,
                  fontSize: 12,
                  fontWeight: 600,
                  border: `1px solid ${GREEN}`,
                  borderRadius: 14,
                  background: '#fff',
                }}
              >
                OK 完成
              </span>
            )}

            {/* 未打卡可补 → 补打卡按钮 */}
            {isMissed && record.can_supplement && (
              <button
                onClick={onSupplement}
                style={{
                  padding: '6px 12px',
                  background: ORANGE,
                  color: '#fff',
                  border: 'none',
                  borderRadius: 14,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                补打卡
              </button>
            )}

            {/* 未打卡超时 → 不可补 */}
            {isExpired && (
              <button
                disabled
                style={{
                  padding: '6px 12px',
                  background: '#E5E7EB',
                  color: GRAY,
                  border: 'none',
                  borderRadius: 14,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'not-allowed',
                }}
              >
                不可补
              </button>
            )}

            {/* 未到时间 + 今天 → 提示 */}
            {isNotYet && isToday && (
              <span
                style={{
                  fontSize: 11,
                  color: SUB,
                }}
              >
                请在主页打卡
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
