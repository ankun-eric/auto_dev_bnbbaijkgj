'use client';

/**
 * [PRD-439 F-02] AI 对话首页 - 提醒铃铛悬浮按钮
 *
 * 替代原健康打卡 DraggablePunchCard：
 * - 圆形 🔔 图标 + 红色未处理数字徽标（>0 显示，上限 9+）
 * - 点击后弹出 ReminderDrawer
 * - 复用 DraggablePunchCard 的可拖拽布局思路（仅垂直拖拽）
 */

import { CSSProperties, useState, useRef, useEffect, useCallback } from 'react';

interface Props {
  badgeCount: number;
  onClick: () => void;
  defaultBottom?: number;
  position?: 'left' | 'right';
}

const LONG_PRESS_MS = 200;
const STORAGE_KEY = '__h5_reminder_bell_y__';

export default function ReminderBellButton({
  badgeCount,
  onClick,
  defaultBottom = 120,
  position = 'right',
}: Props) {
  const [bottom, setBottom] = useState(defaultBottom);
  const [dragging, setDragging] = useState(false);
  const startYRef = useRef(0);
  const startBottomRef = useRef(0);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const longPressRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const v = parseInt(saved, 10);
        if (!Number.isNaN(v) && v >= 0) setBottom(v);
      }
    } catch {}
  }, []);

  const clamp = useCallback((b: number) => {
    if (typeof window === 'undefined') return b;
    const winH = window.innerHeight;
    const minB = 80;
    const maxB = winH - 56 - 56;
    return Math.max(minB, Math.min(maxB, b));
  }, []);

  const cancelLong = () => {
    if (longPressRef.current) {
      clearTimeout(longPressRef.current);
      longPressRef.current = null;
    }
  };

  const enterDrag = () => {
    setDragging(true);
    draggingRef.current = true;
  };

  const onEnd = () => {
    cancelLong();
    if (draggingRef.current) {
      try {
        sessionStorage.setItem(STORAGE_KEY, String(bottom));
      } catch {}
    }
    draggingRef.current = false;
    setDragging(false);
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    startYRef.current = t.clientY;
    startBottomRef.current = bottom;
    movedRef.current = false;
    cancelLong();
    longPressRef.current = setTimeout(enterDrag, LONG_PRESS_MS);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    const t = e.touches[0];
    if (!draggingRef.current) {
      if (Math.abs(startYRef.current - t.clientY) > 8) cancelLong();
      return;
    }
    e.preventDefault();
    movedRef.current = true;
    const dy = startYRef.current - t.clientY;
    setBottom(clamp(startBottomRef.current + dy));
  };

  const handleTouchEnd = () => {
    const wasDrag = draggingRef.current;
    onEnd();
    if (!wasDrag && !movedRef.current) onClick();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    startYRef.current = e.clientY;
    startBottomRef.current = bottom;
    movedRef.current = false;
    cancelLong();
    longPressRef.current = setTimeout(enterDrag, LONG_PRESS_MS);
    const move = (ev: MouseEvent) => {
      if (!draggingRef.current) {
        if (Math.abs(startYRef.current - ev.clientY) > 8) cancelLong();
        return;
      }
      movedRef.current = true;
      const dy = startYRef.current - ev.clientY;
      setBottom(clamp(startBottomRef.current + dy));
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      const wasDrag = draggingRef.current;
      onEnd();
      if (!wasDrag && !movedRef.current) onClick();
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  const sideStyle: CSSProperties = position === 'left' ? { left: 16 } : { right: 16 };
  const scale = dragging ? 1.05 : 1.0;
  const shadow = dragging
    ? '0 8px 24px rgba(0,0,0,0.25)'
    : '0 2px 12px rgba(0,0,0,0.18)';

  const showBadge = badgeCount > 0;
  const badgeText = badgeCount > 9 ? '9+' : String(badgeCount);

  return (
    <div
      data-testid="prd439-reminder-bell"
      data-badge={badgeCount}
      className="fixed z-30 select-none"
      style={{
        ...sideStyle,
        bottom,
        transform: `scale(${scale})`,
        transformOrigin: position === 'left' ? 'bottom left' : 'bottom right',
        boxShadow: shadow,
        borderRadius: 9999,
        transition: dragging
          ? 'transform 0.12s ease-out, box-shadow 0.12s ease-out'
          : 'transform 0.18s ease-out, box-shadow 0.18s ease-out',
        touchAction: dragging ? 'none' : 'auto',
        cursor: dragging ? 'grabbing' : 'pointer',
        willChange: 'transform, bottom',
      }}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onMouseDown={handleMouseDown}
    >
      <div
        style={{
          position: 'relative',
          width: 48,
          height: 48,
          borderRadius: 9999,
          background: 'linear-gradient(135deg, #4FACFE 0%, #00C6FB 100%)',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 22,
        }}
      >
        🔔
        {showBadge && (
          <span
            data-testid="prd439-reminder-bell-badge"
            style={{
              position: 'absolute',
              top: -4,
              right: -4,
              minWidth: 18,
              height: 18,
              padding: '0 5px',
              background: '#FF3B30',
              color: '#fff',
              borderRadius: 9999,
              fontSize: 11,
              fontWeight: 600,
              lineHeight: '18px',
              textAlign: 'center',
              boxShadow: '0 0 0 2px #fff',
            }}
          >
            {badgeText}
          </span>
        )}
      </div>
    </div>
  );
}
