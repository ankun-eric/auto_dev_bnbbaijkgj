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
      style={{
        background: 'linear-gradient(180deg, #F0F9FF 0%, #DBEAFE 100%)',
        paddingTop: 'env(safe-area-inset-top)',
        ...style,
      }}
      data-testid={testId}
    >
      <div style={{ flex: '0 0 auto', minWidth: 28, color: '#1F2937' }}>{left}</div>
      <div style={{ flex: 1, textAlign: 'center', fontWeight: 600, fontSize: 18, color: '#0C4A6E' }}>
        {title}
      </div>
      <div style={{ flex: '0 0 auto', minWidth: 28, textAlign: 'right', color: '#1F2937' }}>{right}</div>
    </div>
  );
};
