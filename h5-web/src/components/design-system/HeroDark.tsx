'use client';
import React from 'react';

export interface HeroDarkProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

export const HeroDark: React.FC<HeroDarkProps> = ({
  children,
  className = '',
  style,
  testId = 'bh-hero-dark',
}) => {
  return (
    <div
      className={`bh-hero-dark ${className}`}
      style={style}
      data-testid={testId}
    >
      {children}
    </div>
  );
};
