'use client';

import { useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';

/* ── mock 数据 & 类型 ── */

interface TimeSlot {
  time: string;
  available: boolean;
}

interface DaySlots {
  morning: TimeSlot[];
  afternoon: TimeSlot[];
  evening: TimeSlot[];
}

function generateMockSlots(): Map<string, DaySlots> {
  const map = new Map<string, DaySlots>();
  const today = new Date();
  for (let d = 0; d < 30; d++) {
    const date = new Date(today);
    date.setDate(today.getDate() + d);
    const key = formatDateKey(date);
    const pastDay = d < 0;
    map.set(key, {
      morning: [
        { time: '08:30', available: !pastDay && d % 3 !== 0 },
        { time: '09:00', available: !pastDay },
        { time: '09:30', available: !pastDay && d % 2 === 0 },
        { time: '10:00', available: !pastDay },
        { time: '10:30', available: !pastDay && d % 4 !== 0 },
      ],
      afternoon: [
        { time: '14:00', available: !pastDay },
        { time: '14:30', available: !pastDay && d % 3 !== 1 },
        { time: '15:00', available: !pastDay && d % 5 !== 0 },
        { time: '15:30', available: !pastDay },
      ],
      evening: [
        { time: '19:00', available: !pastDay && d % 2 === 0 },
        { time: '19:30', available: !pastDay && d % 3 === 0 },
        { time: '20:00', available: false },
      ],
    });
  }
  return map;
}

function formatDateKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

/* ── 组件 ── */

export default function AppointmentPage() {
  const router = useRouter();
  const today = useMemo(() => new Date(), []);
  const todayKey = useMemo(() => formatDateKey(today), [today]);

  const [currentMonth, setCurrentMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState<string>(todayKey);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  const mockData = useMemo(() => generateMockSlots(), []);

  const calendarDays = useMemo(() => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells: (number | null)[] = [];
    for (let i = 0; i < firstDay; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    return cells;
  }, [currentMonth]);

  const daySlots = useMemo(() => mockData.get(selectedDate), [mockData, selectedDate]);

  const isBeforeToday = useCallback((day: number) => {
    const d = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
    const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    return d < t;
  }, [currentMonth, today]);

  const getDateKey = useCallback((day: number) => {
    return formatDateKey(new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day));
  }, [currentMonth]);

  const handlePrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };

  const handleConfirm = () => {
    if (!selectedSlot) return;
    router.back();
  };

  const monthLabel = `${currentMonth.getFullYear()}年${currentMonth.getMonth() + 1}月`;

  const renderSlotSection = (title: string, slots: TimeSlot[]) => (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 8, fontWeight: 500 }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {slots.map((s) => {
          const isSelected = selectedSlot === `${selectedDate}_${s.time}`;
          return (
            <div
              key={s.time}
              onClick={() => s.available && setSelectedSlot(`${selectedDate}_${s.time}`)}
              style={{
                background: isSelected
                  ? 'linear-gradient(135deg, #38BDF8, #0284C7)'
                  : s.available ? '#F8FAFC' : '#F1F5F9',
                color: isSelected ? '#fff' : s.available ? '#374151' : '#CBD5E1',
                borderRadius: 8, padding: '10px 0', textAlign: 'center',
                fontSize: 14, cursor: s.available ? 'pointer' : 'not-allowed',
                textDecoration: s.available ? 'none' : 'line-through',
                fontWeight: isSelected ? 600 : 400,
              }}
            >
              {s.time}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: '100vh', background: '#fff', paddingBottom: 80 }}>
      {/* 顶栏 */}
      <div style={{
        display: 'flex', alignItems: 'center', height: 48, background: '#fff',
        borderBottom: '1px solid #F3F4F6', padding: '0 16px',
        paddingTop: 'env(safe-area-inset-top)',
      }}>
        <div onClick={() => router.back()} style={{ cursor: 'pointer', fontSize: 20, color: '#1F2937' }}>←</div>
        <div style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 700, color: '#1F2937' }}>选择预约时间</div>
        <div style={{ width: 20 }} />
      </div>

      {/* 月历 */}
      <div style={{ padding: '16px 16px 8px' }}>
        {/* 月份切换 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div onClick={handlePrevMonth} style={{ cursor: 'pointer', fontSize: 18, color: '#6B7280', padding: '4px 8px' }}>‹</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#1F2937' }}>{monthLabel}</div>
          <div onClick={handleNextMonth} style={{ cursor: 'pointer', fontSize: 18, color: '#6B7280', padding: '4px 8px' }}>›</div>
        </div>

        {/* 星期头 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', marginBottom: 4 }}>
          {WEEKDAYS.map((w) => (
            <div key={w} style={{ textAlign: 'center', fontSize: 12, color: '#9CA3AF', padding: '4px 0' }}>{w}</div>
          ))}
        </div>

        {/* 日期网格 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
          {calendarDays.map((day, i) => {
            if (day === null) return <div key={`e${i}`} />;
            const key = getDateKey(day);
            const isToday = key === todayKey;
            const isSelected = key === selectedDate;
            const disabled = isBeforeToday(day);
            return (
              <div
                key={i}
                onClick={() => !disabled && setSelectedDate(key)}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  height: 44, cursor: disabled ? 'default' : 'pointer', position: 'relative',
                }}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: isSelected ? 'linear-gradient(135deg, #38BDF8, #0284C7)' : 'transparent',
                  color: isSelected ? '#fff' : disabled ? '#D1D5DB' : '#374151',
                  fontSize: 14, fontWeight: isSelected ? 600 : 400,
                }}>
                  {day}
                </div>
                {isToday && !isSelected && (
                  <div style={{
                    position: 'absolute', bottom: 2, width: 4, height: 4,
                    borderRadius: '50%', background: '#0EA5E9',
                  }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 时段 */}
      <div style={{ padding: '8px 16px', borderTop: '1px solid #F3F4F6' }}>
        {daySlots ? (
          <>
            {renderSlotSection('上午', daySlots.morning)}
            {renderSlotSection('下午', daySlots.afternoon)}
            {renderSlotSection('晚间', daySlots.evening)}
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '32px 0', color: '#9CA3AF', fontSize: 14 }}>
            该日期暂无可用时段
          </div>
        )}
      </div>

      {/* 底部确认栏 */}
      <div style={{
        position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 750, background: '#fff',
        borderTop: '1px solid #E5E7EB',
        padding: '12px 16px calc(12px + env(safe-area-inset-bottom))',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontSize: 14, color: '#0284C7' }}>
          {selectedSlot
            ? `已选：${selectedSlot.replace('_', ' ')}`
            : '请选择时间'}
        </div>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={!selectedSlot}
          style={{
            height: 48, borderRadius: 12, border: 'none', padding: '0 32px',
            background: selectedSlot
              ? 'linear-gradient(135deg, #38BDF8, #0284C7)'
              : '#D1D5DB',
            color: '#fff', fontSize: 15, fontWeight: 600,
            cursor: selectedSlot ? 'pointer' : 'not-allowed',
          }}
        >
          确认预约
        </button>
      </div>
    </div>
  );
}
