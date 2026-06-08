'use client';

/**
 * [PRD-MED-HISTORY-V1] 可复用日历组件
 *
 * 用于用药提醒历史打卡记录页面的月视图日历。
 * 展示月份切换箭头、星期表头、日期格子，右下角显示打卡状态小圆点。
 *
 * Props:
 *  - year, month: 当前查看的年月
 *  - days: 后端返回的 CalendarDay[] 数组
 *  - selectedDate: 当前选中的日期 YYYY-MM-DD
 *  - onSelectDate: 日期点击回调
 *  - onPrevMonth / onNextMonth: 月份切换回调
 */

import React from 'react';

type DayStatus = 'fully_done' | 'partial' | 'missed' | 'no_plan';

export interface CalendarDay {
  date: string;
  status: DayStatus;
}

interface CalendarProps {
  year: number;
  month: number;
  days: CalendarDay[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
}

const GREEN = '#22c55e';
const ORANGE = '#FF8A3D';
const RED = '#EF4444';
const BLUE = '#4A9EE0';
const TEXT = '#111827';
const SUB = '#6B7280';

const WEEKDAY_CN = ['日', '一', '二', '三', '四', '五', '六'];

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay();
}

function dayStatusDotColor(status: DayStatus): string {
  switch (status) {
    case 'fully_done':
      return GREEN;
    case 'partial':
      return ORANGE;
    case 'missed':
      return RED;
    default:
      return 'transparent';
  }
}

export default function Calendar({
  year,
  month,
  days,
  selectedDate,
  onSelectDate,
  onPrevMonth,
  onNextMonth,
}: CalendarProps) {
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const daysInMonth = getDaysInMonth(year, month);
  const firstDow = getFirstDayOfWeek(year, month);
  const cells: (CalendarDay | null)[] = [];

  for (let i = 0; i < firstDow; i++) {
    cells.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayData = days.find((cd) => cd.date === dateStr);
    cells.push(dayData || { date: dateStr, status: 'no_plan' as DayStatus });
  }

  const isToday = (dateStr: string) => dateStr === todayStr;
  const isSelected = (dateStr: string) => dateStr === selectedDate;
  const isFuture = (dateStr: string) => dateStr > todayStr;

  return (
    <div>
      {/* 月份切换 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 24,
          margin: '0 16px 12px',
        }}
      >
        <button
          onClick={onPrevMonth}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 24,
            color: TEXT,
            cursor: 'pointer',
            padding: '4px 12px',
            lineHeight: 1,
          }}
          aria-label="上一月"
        >
          ‹
        </button>
        <span style={{ fontSize: 18, fontWeight: 700, color: TEXT }}>
          {year}年 {month}月
        </span>
        <button
          onClick={onNextMonth}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 24,
            color: TEXT,
            cursor: 'pointer',
            padding: '4px 12px',
            lineHeight: 1,
          }}
          aria-label="下一月"
        >
          ›
        </button>
      </div>

      {/* 日历网格 */}
      <div
        style={{
          margin: '0 16px',
          background: '#fff',
          borderRadius: 14,
          padding: '12px 8px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}
      >
        {/* 星期头 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            marginBottom: 4,
          }}
        >
          {WEEKDAY_CN.map((w) => (
            <div
              key={w}
              style={{
                textAlign: 'center',
                fontSize: 12,
                color: SUB,
                fontWeight: 600,
                padding: '6px 0',
              }}
            >
              {w}
            </div>
          ))}
        </div>

        {/* 日期格子 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: 2,
          }}
        >
          {cells.map((cell, idx) => {
            if (!cell) {
              return <div key={`empty-${idx}`} />;
            }
            const sel = isSelected(cell.date);
            const fut = isFuture(cell.date);
            const tdy = isToday(cell.date);
            const dotColor = dayStatusDotColor(cell.status);

            return (
              <div
                key={cell.date}
                onClick={() => !fut && onSelectDate(cell.date)}
                style={{
                  position: 'relative',
                  textAlign: 'center',
                  padding: '8px 0 6px',
                  borderRadius: 8,
                  cursor: fut ? 'default' : 'pointer',
                  background: sel ? BLUE : tdy ? '#E8F4FD' : 'transparent',
                  opacity: fut ? 0.4 : 1,
                  minHeight: 44,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  userSelect: 'none',
                }}
              >
                <span
                  style={{
                    fontSize: 16,
                    fontWeight: tdy || sel ? 700 : 400,
                    color: sel ? '#fff' : tdy ? BLUE : TEXT,
                    lineHeight: 1.2,
                  }}
                >
                  {parseInt(cell.date.slice(-2), 10)}
                </span>
                {cell.status !== 'no_plan' && (
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 3,
                      background: dotColor,
                      marginTop: 2,
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
