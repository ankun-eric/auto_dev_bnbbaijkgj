'use client';

/**
 * [PRD-439 F-02] AI 对话首页 - 提醒铃铛悬浮按钮
 *
 * [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19 §2] 铃铛位置 & 拖拽优化（最终版）
 *   - 初始位置：屏幕靠右 + viewport 垂直正中（top: 50%, right: 12px）
 *   - 不再受 banner / topbar 高度影响（initialTop prop 已废弃保留以兼容旧调用方）
 *   - 拖拽：可拖动（长按 200ms 后进入拖拽态，仅垂直方向）
 *   - 持久化：拖动结束后将 (x, y) 写入 localStorage，下次进入页面恢复
 *     key = `bini.ai-home.bell.position`
 *     value = { x: number, y: number, savedAt: number }
 *   - 边界保护：恢复位置时若越界自动收回屏幕安全区内（距边缘至少 8px）
 *   - 点击：触发 onClick（与拖拽互斥）
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
   * 已废弃保留：原本用于初始 top 值（相对视口顶部，单位 px）。
   * [PRD-AI-HOME-OPTIM-FINAL-V1] 本次优化后初始位置改为 viewport 50% 垂直正中 + 靠右，
   * 不再依赖父组件传入 initialTop。保留此 prop 以兼容旧调用方。
   */
  initialTop?: number;
  position?: 'left' | 'right';
}

const LONG_PRESS_MS = 200;
const BELL_SIZE = 36;
const EDGE_MIN = 8;
const STORAGE_KEY = 'bini.ai-home.bell.position';

interface SavedPos {
  x: number; // 距离屏幕右侧的偏移（px），始终为正
  y: number; // 距离屏幕顶部的偏移（px）
  savedAt: number;
}

function loadPos(): SavedPos | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (
      v &&
      typeof v === 'object' &&
      typeof v.x === 'number' &&
      typeof v.y === 'number' &&
      typeof v.savedAt === 'number'
    ) {
      return v as SavedPos;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function savePos(p: SavedPos) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* ignore */
  }
}

/** 把任意候选位置收敛到当前视口安全区内（距边缘至少 EDGE_MIN px） */
function clampToViewport(x: number, y: number): { x: number; y: number } {
  if (typeof window === 'undefined') return { x, y };
  const winH = window.innerHeight;
  const winW = window.innerWidth;
  const safeX = Math.max(EDGE_MIN, Math.min(winW - BELL_SIZE - EDGE_MIN, x));
  const safeY = Math.max(EDGE_MIN + 48, Math.min(winH - BELL_SIZE - EDGE_MIN, y));
  return { x: safeX, y: safeY };
}

export default function ReminderBellButton({
  onClick,
  position = 'right',
}: Props) {
  // 默认右 12px、垂直正中：用 sentinel -1 表示"未初始化"
  const [right, setRight] = useState<number>(12);
  const [top, setTop] = useState<number>(-1);
  const [dragging, setDragging] = useState(false);
  const startYRef = useRef(0);
  const startTopRef = useRef(0);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const longPressRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialAppliedRef = useRef(false);

  // 首次挂载：优先恢复 localStorage，没有则用 viewport 50% 垂直正中
  useEffect(() => {
    if (initialAppliedRef.current) return;
    initialAppliedRef.current = true;
    if (typeof window === 'undefined') return;
    const winH = window.innerHeight;
    const winW = window.innerWidth;
    const saved = loadPos();
    if (saved) {
      // 持久化值是"距右侧"的偏移；转 x（左边距）后做边界保护，再回写
      const xLeft = winW - saved.x - BELL_SIZE;
      const { x: clampedX, y: clampedY } = clampToViewport(xLeft, saved.y);
      setRight(Math.max(EDGE_MIN, winW - clampedX - BELL_SIZE));
      setTop(clampedY);
    } else {
      // 默认：右 12px + viewport 50% 垂直正中
      setRight(12);
      setTop(Math.round(winH / 2 - BELL_SIZE / 2));
    }
  }, []);

  // 窗口尺寸变化（横竖屏切换）：自动收回安全区
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onResize = () => {
      const winW = window.innerWidth;
      const xLeft = winW - right - BELL_SIZE;
      const { x, y } = clampToViewport(xLeft, top);
      setRight(Math.max(EDGE_MIN, winW - x - BELL_SIZE));
      setTop(y);
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
    };
  }, [right, top]);

  const clampY = useCallback((t: number) => {
    if (typeof window === 'undefined') return t;
    const winH = window.innerHeight;
    const minT = EDGE_MIN + 48;
    const maxT = winH - BELL_SIZE - EDGE_MIN;
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

  const persistCurrent = useCallback(
    (nextTop: number) => {
      if (typeof window === 'undefined') return;
      const winW = window.innerWidth;
      // 计算 x（距离屏幕左侧的偏移）→ 转 distFromRight
      const distFromRight = right;
      savePos({
        x: distFromRight,
        y: nextTop,
        savedAt: Date.now(),
      });
    },
    [right],
  );

  const onEnd = (finalTop?: number) => {
    cancelLong();
    const wasDrag = draggingRef.current;
    draggingRef.current = false;
    setDragging(false);
    if (wasDrag && typeof finalTop === 'number') {
      persistCurrent(finalTop);
    }
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
    setTop(clampY(startTopRef.current + dy));
  };

  const handleTouchEnd = () => {
    const wasDrag = draggingRef.current;
    const finalTop = top;
    onEnd(finalTop);
    if (!wasDrag && !movedRef.current) onClick();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    startYRef.current = e.clientY;
    startTopRef.current = top;
    movedRef.current = false;
    cancelLong();
    longPressRef.current = setTimeout(enterDrag, LONG_PRESS_MS);
    let lastTop = top;
    const move = (ev: MouseEvent) => {
      if (!draggingRef.current) {
        if (Math.abs(startYRef.current - ev.clientY) > 8) cancelLong();
        return;
      }
      movedRef.current = true;
      const dy = ev.clientY - startYRef.current;
      lastTop = clampY(startTopRef.current + dy);
      setTop(lastTop);
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      const wasDrag = draggingRef.current;
      onEnd(lastTop);
      if (!wasDrag && !movedRef.current) onClick();
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  // 没有有效 top 时（SSR 或首屏未挂载）暂不渲染，避免闪烁
  if (top < 0) return null;

  const sideStyle: CSSProperties = position === 'left'
    ? { left: 12 }
    : { right };
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
          width: BELL_SIZE,
          height: BELL_SIZE,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 30,
          opacity: 1,
          lineHeight: 1,
          filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.18))',
        }}
        aria-label="提醒铃铛"
      >
        🔔
      </div>
    </div>
  );
}
