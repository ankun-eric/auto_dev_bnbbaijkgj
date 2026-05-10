'use client';
import React from 'react';

export interface TopBarProps {
  title?: React.ReactNode;
  left?: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

export const TopBar: React.FC<TopBarProps> = ({
  title,
  left,
  right,
  className = '',
  style,
  testId = 'bh-topbar',
}) => {
  return (
    <div
      className={`bh-topbar ${className}`}
      style={style}
      data-testid={testId}
    >
      <div style={{ flex: '0 0 auto', minWidth: 28 }}>{left}</div>
      <div style={{ flex: 1, textAlign: 'center', fontWeight: 600, fontSize: 'var(--font-size-md)' }}>
        {title}
      </div>
      <div style={{ flex: '0 0 auto', minWidth: 28, textAlign: 'right' }}>{right}</div>
    </div>
  );
};
