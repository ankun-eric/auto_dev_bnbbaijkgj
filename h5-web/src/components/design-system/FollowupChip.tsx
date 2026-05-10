'use client';
import React from 'react';

export interface FollowupChipProps {
  text: string;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

/**
 * 流式追问 chip（屏 ⑨）— 流式插入动画来自 .bh-followup-chip 类。
 */
export const FollowupChip: React.FC<FollowupChipProps> = ({
  text,
  onClick,
  className = '',
  style,
  testId = 'bh-followup-chip',
}) => {
  return (
    <span
      className={`bh-followup-chip ${className}`}
      onClick={onClick}
      style={style}
      data-testid={testId}
    >
      {text}
    </span>
  );
};
