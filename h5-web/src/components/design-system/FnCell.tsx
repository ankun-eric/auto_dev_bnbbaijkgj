'use client';
import React from 'react';

export interface FnCellProps {
  icon?: React.ReactNode;
  main: string;
  sub?: string;
  badge?: string;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

/**
 * 功能宫格 — 替代 ai-home 顶部三色硬编码渐变。
 * 视觉来自方案 A：淡天蓝渐变 (--gradient-fn-cell)，深天蓝文字。
 */
export const FnCell: React.FC<FnCellProps> = ({
  icon,
  main,
  sub,
  badge,
  onClick,
  className = '',
  style,
  testId = 'bh-fn-cell',
}) => {
  return (
    <div
      className={`bh-fn-cell ${className}`}
      style={style}
      onClick={onClick}
      data-testid={testId}
      role="button"
      tabIndex={0}
    >
      {icon != null && <span className="bh-fn-cell-icon">{icon}</span>}
      <span className="bh-fn-cell-main">{main}</span>
      {sub && <span className="bh-fn-cell-sub">{sub}</span>}
      {badge && (
        <span
          style={{
            position: 'absolute',
            top: 6,
            right: 6,
            padding: '2px 6px',
            borderRadius: 'var(--radius-full)',
            background: '#0284C7',
            color: '#FFFFFF',
            fontSize: 10,
            lineHeight: 1.2,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  );
};
