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
      style={{
        background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
        borderRadius: '16px 0 16px 16px',
        color: '#FFFFFF',
        fontSize: 15,
        ...style,
      }}
      data-testid={testId}
    >
      {children}
    </div>
  );
};
