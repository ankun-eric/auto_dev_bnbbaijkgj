'use client';

import { useState, useRef, useEffect, useCallback, CSSProperties, ReactNode } from 'react';

/**
 * PRD v1.1 §3.2 健康打卡可拖动组件
 * - 长按 200ms 进入拖动态（仅垂直方向）
 * - 边界：上不超过顶栏底沿 + 8px，下不超过输入框顶沿 - 8px
 * - 位置记忆：本次会话内 sessionStorage 记忆，关闭页面后下次重新进入恢复默认位置
 * - 视觉反馈：拖动态 1.05× 放大 + 阴影加深，松手回弹 1.0× + 常态阴影
 * - 仅支持垂直拖动，左右位置固定（贴右）
 */

interface DraggablePunchCardProps {
  storageKey?: string;
  defaultBottom?: number;
  topOffset?: number;
  bottomOffset?: number;
  onClick?: () => void;
  onDragStart?: (y: number) => void;
  onDragEnd?: (fromY: number, toY: number) => void;
  position?: 'right' | 'left';
  children: ReactNode;
}

const LONG_PRESS_MS = 200;

export default function DraggablePunchCard({
  storageKey = '__h5_punchcard_y__',
  defaultBottom = 120,
  topOffset = 56,
  bottomOffset = 80,
  onClick,
  onDragStart,
  onDragEnd,
  position = 'right',
  children,
}: DraggablePunchCardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startYRef = useRef(0);
  const startBottomRef = useRef(0);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);

  const [bottom, setBottom] = useState<number>(defaultBottom);
  const [dragging, setDragging] = useState(false);
  const [pressing, setPressing] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const v = parseInt(saved, 10);
        if (!Number.isNaN(v) && v >= 0) setBottom(v);
      }
    } catch {}
  }, [storageKey]);

  const clampBottom = useCallback((b: number): number => {
    if (typeof window === 'undefined') return b;
    const winH = window.innerHeight;
    const minBottom = bottomOffset;
    const maxBottom = winH - topOffset - 56;
    if (b < minBottom) return minBottom;
    if (b > maxBottom) return maxBottom;
    return b;
  }, [bottomOffset, topOffset]);

  const cancelLongPress = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  const enterDragMode = useCallback(() => {
    setDragging(true);
    draggingRef.current = true;
    if (onDragStart) onDragStart(bottom);
  }, [bottom, onDragStart]);

  const onMove = useCallback((clientY: number) => {
    if (!draggingRef.current) return;
    movedRef.current = true;
    const dy = startYRef.current - clientY;
    const next = clampBottom(startBottomRef.current + dy);
    setBottom(next);
  }, [clampBottom]);

  const onEnd = useCallback(() => {
    cancelLongPress();
    if (draggingRef.current) {
      const fromY = startBottomRef.current;
      const toY = bottom;
      try {
        if (typeof window !== 'undefined') {
          sessionStorage.setItem(storageKey, String(toY));
        }
      } catch {}
      if (onDragEnd) onDragEnd(fromY, toY);
    }
    draggingRef.current = false;
    setDragging(false);
    setPressing(false);
  }, [bottom, cancelLongPress, onDragEnd, storageKey]);

  const handleTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    startYRef.current = t.clientY;
    startBottomRef.current = bottom;
    movedRef.current = false;
    setPressing(true);
    cancelLongPress();
    longPressTimerRef.current = setTimeout(() => {
      enterDragMode();
    }, LONG_PRESS_MS);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    const t = e.touches[0];
    if (!draggingRef.current) {
      const dy = Math.abs(startYRef.current - t.clientY);
      if (dy > 8) {
        cancelLongPress();
      }
      return;
    }
    e.preventDefault();
    onMove(t.clientY);
  };

  const handleTouchEnd = () => {
    const wasDragging = draggingRef.current;
    onEnd();
    if (!wasDragging && !movedRef.current) {
      onClick && onClick();
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    startYRef.current = e.clientY;
    startBottomRef.current = bottom;
    movedRef.current = false;
    setPressing(true);
    cancelLongPress();
    longPressTimerRef.current = setTimeout(() => {
      enterDragMode();
    }, LONG_PRESS_MS);

    const move = (ev: MouseEvent) => {
      if (!draggingRef.current) {
        if (Math.abs(startYRef.current - ev.clientY) > 8) cancelLongPress();
        return;
      }
      onMove(ev.clientY);
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      const wasDragging = draggingRef.current;
      onEnd();
      if (!wasDragging && !movedRef.current) {
        onClick && onClick();
      }
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  const sideStyle: CSSProperties =
    position === 'left' ? { left: 16 } : { right: 16 };

  const scale = dragging ? 1.05 : 1.0;
  const shadow = dragging
    ? '0 8px 24px rgba(0,0,0,0.25)'
    : '0 2px 12px rgba(0,0,0,0.15)';

  return (
    <div
      ref={containerRef}
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
      data-testid="draggable-punchcard"
      data-dragging={dragging ? '1' : '0'}
    >
      {children}
    </div>
  );
}
