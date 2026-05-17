'use client';

/**
 * [PRD-439 F-02] AI 对话首页 - 提醒铃铛悬浮按钮
 * [PRD-AIHOME-OPTIM-V1 2026-05-17 R1] 视觉调整：
 * - 完全去掉底色 / 背景框 / 渐变背景，仅保留 🔔 图标本身（图标不透明）
 * - 不再使用顶部数字角标（原 PRD-439 的红色数字徽标移除，改为由汉堡图标承担红点提示）
 * - 初始垂直位置改为顶部 banner 区域的垂直正中（由父组件通过 initialTop 传入）
 * - 拖动后的位置 **不持久化**：用户离开 ai-home 再回来时铃铛回到初始位置
 *
 * 仍然保留：
 * - 可拖动（长按 200ms 后进入拖拽态，仅垂直拖动）
 * - 点击触发 onClick（与拖拽互斥）
 * - 右侧贴边定位
 */

import { CSSProperties, useState, useRef, useEffect, useCallback } from 'react';

interface Props {
  /**
   * 已废弃保留：原本用于显示数字角标，本次优化后不再显示数字（红点提示移到汉堡图标）。
   * 保留 prop 以兼容外部调用方，传入任意值都不会影响铃铛视觉。
   */
  badgeCount?: number;
  onClick: () => void;
  /**
   * 初始 top 值（相对视口顶部，单位 px）。
   * 由父组件在挂载时根据 banner 区域的位置计算"垂直正中"传入。
   * 未传入时回退到默认值（约 96px，落在 topbar 之下）。
   */
  initialTop?: number;
  position?: 'left' | 'right';
}

const LONG_PRESS_MS = 200;

export default function ReminderBellButton({
  onClick,
  initialTop,
  position = 'right',
}: Props) {
  const fallbackTop = 96;
  const [top, setTop] = useState<number>(initialTop ?? fallbackTop);
  const [dragging, setDragging] = useState(false);
  const startYRef = useRef(0);
  const startTopRef = useRef(0);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const longPressRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialAppliedRef = useRef(false);

  // 接收 initialTop 异步到位后的复位：只在首次有效值到来时应用一次
  // [PRD-AIHOME-OPTIM-V1 R1] 不读取 sessionStorage，确保每次进入页面都从默认初始位置开始
  useEffect(() => {
    if (initialAppliedRef.current) return;
    if (typeof initialTop === 'number' && initialTop > 0) {
      setTop(initialTop);
      initialAppliedRef.current = true;
    }
  }, [initialTop]);

  const clamp = useCallback((t: number) => {
    if (typeof window === 'undefined') return t;
    const winH = window.innerHeight;
    const minT = 56;
    const maxT = winH - 56 - 48;
    return Math.max(minT, Math.min(maxT, t));
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
    // [PRD-AIHOME-OPTIM-V1 R1] 不持久化位置，离开页面后重进自然复位
    draggingRef.current = false;
    setDragging(false);
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    startYRef.current = t.clientY;
    startTopRef.current = top;
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
    const dy = t.clientY - startYRef.current;
    setTop(clamp(startTopRef.current + dy));
  };

  const handleTouchEnd = () => {
    const wasDrag = draggingRef.current;
    onEnd();
    if (!wasDrag && !movedRef.current) onClick();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    startYRef.current = e.clientY;
    startTopRef.current = top;
    movedRef.current = false;
    cancelLong();
    longPressRef.current = setTimeout(enterDrag, LONG_PRESS_MS);
    const move = (ev: MouseEvent) => {
      if (!draggingRef.current) {
        if (Math.abs(startYRef.current - ev.clientY) > 8) cancelLong();
        return;
      }
      movedRef.current = true;
      const dy = ev.clientY - startYRef.current;
      setTop(clamp(startTopRef.current + dy));
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

  return (
    <div
      data-testid="prd439-reminder-bell"
      className="fixed z-30 select-none"
      style={{
        ...sideStyle,
        top,
        transform: `scale(${scale})`,
        transformOrigin: position === 'left' ? 'top left' : 'top right',
        transition: dragging
          ? 'transform 0.12s ease-out'
          : 'transform 0.18s ease-out',
        touchAction: dragging ? 'none' : 'auto',
        cursor: dragging ? 'grabbing' : 'pointer',
        willChange: 'transform, top',
        // [PRD-AIHOME-OPTIM-V1 R1] 彻底去除底色、背景框与阴影，仅保留 emoji 图标本身
        background: 'transparent',
        border: 'none',
        boxShadow: 'none',
        padding: 0,
      }}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onMouseDown={handleMouseDown}
    >
      <div
        style={{
          width: 36,
          height: 36,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 30,
          // 图标本身完全不透明（仅外层底色去除）
          opacity: 1,
          lineHeight: 1,
          // 给 emoji 一个轻微的投影，避免在浅色背景上看不清楚；不构成"底色/背景框"
          filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.18))',
        }}
        aria-label="提醒铃铛"
      >
        🔔
      </div>
    </div>
  );
}
