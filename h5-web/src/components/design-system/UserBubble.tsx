'use client';
import React from 'react';

export interface UserBubbleProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

export const UserBubble: React.FC<UserBubbleProps> = ({
  children,
  className = '',
  style,
  testId = 'bh-user-bubble',
}) => {
  return (
    <div
      className={`bh-bubble-user ${className}`}
      style={style}
      data-testid={testId}
    >
      {children}
    </div>
  );
};
