'use client';
import React from 'react';

export interface ThinkingDotsProps {
  className?: string;
  testId?: string;
}

/**
 * 思考态三圆点 — 0.4s/dot 轮播由 .bh-thinking-dots 类驱动。
 */
export const ThinkingDots: React.FC<ThinkingDotsProps> = ({
  className = '',
  testId = 'bh-thinking-dots',
}) => {
  return (
    <span className={`bh-thinking-dots ${className}`} data-testid={testId} aria-label="思考中">
      <span />
      <span />
      <span />
    </span>
  );
};
