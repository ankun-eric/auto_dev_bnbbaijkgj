'use client';
import React from 'react';

export interface RecommendCardProps {
  icon?: React.ReactNode;
  text: string;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

/**
 * 双色 SVG 推荐卡（屏 ④ 空对话页 × 4 张）。
 * 内部图标推荐使用 SVG 双色描边（fill brand-50, stroke brand-500）。
 */
export const RecommendCard: React.FC<RecommendCardProps> = ({
  icon,
  text,
  onClick,
  className = '',
  style,
  testId = 'bh-recommend-card',
}) => {
  return (
    <div
      className={`bh-recommend-card ${className}`}
      style={style}
      onClick={onClick}
      data-testid={testId}
      role="button"
      tabIndex={0}
    >
      {icon != null && <span className="bh-recommend-card-icon">{icon}</span>}
      <span className="bh-recommend-card-text">{text}</span>
    </div>
  );
};
